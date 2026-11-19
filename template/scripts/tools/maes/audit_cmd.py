#!/usr/bin/env python3
"""maes audit — Operational quality analysis of MAES synthesis and context."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

# ─── Data model ───────────────────────────────────────────────────────────────

Severity = Literal["CRITICAL", "WARNING", "INFO", "OK"]

_SEV_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2, "OK": 3}
_GRADE_HEALTHY = 80
_GRADE_ATTENTION = 60
_HOT_CAP_DEFAULT = 800
_L4_OVERLOAD_THRESHOLD = 25
_L4_OVERLOAD_RATIO = 0.35
_MIN_CLAIM_LEN = 30
_ENFORCEMENT_RATIO_MIN = 0.20
_L2_MIN_ASSERTIONS = 2
_HOT_SATURATION_PCT = 90.0
_L3_STALE_WARN_DAYS = 30
_STALE_CRITICAL_SCORE = 0.8


@dataclass
class Finding:
    id: str
    category: str
    severity: Severity
    title: str
    detail: str
    recommendation: str


# ─── Load helpers ─────────────────────────────────────────────────────────────

def _load_synthesis(maes_dir: Path) -> dict:
    synth: dict = {}
    for name in ("assertions", "guards", "conflicts", "anti-hallucination", "staleness"):
        f = maes_dir / "synthesis" / f"{name}.json"
        default: list | dict = {} if name == "staleness" else []
        if f.exists():
            try:
                synth[name] = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                synth[name] = default
        else:
            synth[name] = default
    return synth


def _load_human_files(maes_dir: Path) -> dict[str, str]:
    human_dir = maes_dir / "context" / "human"
    files: dict[str, str] = {}
    if not human_dir.exists():
        return files
    for f in sorted(human_dir.glob("*.md")):
        try:
            files[f.name] = f.read_text(encoding="utf-8")
        except OSError:
            continue
    return files


def _hot_token_cap(maes_dir: Path) -> int:
    config = maes_dir / "config.yaml"
    if config.exists():
        try:
            import yaml
            data = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
            return int(data.get("compiler", {}).get("hot_token_cap", _HOT_CAP_DEFAULT))
        except Exception:
            pass
    return _HOT_CAP_DEFAULT


def _parse_ttl_days(ttl: str) -> int:
    m = re.match(r"(\d+)d", ttl or "365d")
    return int(m.group(1)) if m else 365


def _stale_score_from_dict(d: dict) -> float:
    """Compute TTL-based staleness score from a synthesis assertion dict."""
    from .compiler import staleness_score as _ss
    from .models import Assertion
    today = date.today()
    a = Assertion(
        id=d.get("id", ""), claim=d.get("claim", ""),
        type=d.get("type", "PATTERN"), layer=d.get("layer", 7),
        subject=d.get("subject"), paths=d.get("paths", []),
        confidence=d.get("confidence", "assumed"), source=d.get("source", ""),
        ttl=d.get("ttl", "730d"), last_verified=d.get("last_verified", ""),
        owner=d.get("owner", ""),
    )
    return _ss(a, today)


def _days_until_stale(assertion: dict) -> int | None:
    lv = assertion.get("last_verified", "")
    if not lv:
        return None
    try:
        last = date.fromisoformat(lv)
        ttl_days = _parse_ttl_days(assertion.get("ttl", "365d"))
        return (last + timedelta(days=ttl_days) - date.today()).days
    except (ValueError, TypeError):
        return None


def _project_name(maes_dir: Path) -> str:
    try:
        import yaml
        cfg = maes_dir / "config.yaml"
        if cfg.exists():
            data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            name = data.get("project", {}).get("name", "")
            if name:
                return name
    except Exception:
        pass
    return maes_dir.parent.name


# ─── Deterministic checks ─────────────────────────────────────────────────────

def _check_conflicts(data: dict) -> list[Finding]:
    conflicts = data.get("conflicts", [])
    unresolved = [c for c in conflicts if c.get("status") == "UNRESOLVED"]
    if unresolved:
        ids = ", ".join(c.get("id", "?") for c in unresolved[:3])
        return [Finding(
            id="conflicts_unresolved",
            category="conflicts",
            severity="CRITICAL",
            title=f"{len(unresolved)} conflito(s) UNRESOLVED",
            detail=f"Conflitos UNRESOLVED bloqueiam CI via `maes validate`. IDs: {ids}",
            recommendation="Resolver os conflitos editando `.maes/context/human/` e rodando `maes sync`",
        )]
    return [Finding(
        id="conflicts_ok", category="conflicts", severity="OK",
        title="Sem conflitos UNRESOLVED",
        detail=f"{len(conflicts)} conflito(s) total, nenhum UNRESOLVED.",
        recommendation="",
    )]


def _check_layer_coverage(data: dict) -> list[Finding]:
    assertions = data.get("assertions", [])
    by_layer: dict[int, int] = {}
    for a in assertions:
        layer = a.get("layer", 7)
        by_layer[layer] = by_layer.get(layer, 0) + 1

    findings: list[Finding] = []
    if by_layer.get(1, 0) == 0:
        findings.append(Finding(
            id="layer_1_empty", category="coverage", severity="CRITICAL",
            title="Layer 1 (compliance) sem assertions",
            detail="Nenhuma assertion de compliance. O hot context não terá regras críticas de nível 1.",
            recommendation="Adicionar assertions de compliance em `.maes/context/human/compliance.md`",
        ))
    if by_layer.get(2, 0) == 0:
        findings.append(Finding(
            id="layer_2_empty", category="coverage", severity="WARNING",
            title="Layer 2 (security) sem assertions",
            detail="Nenhuma assertion de security. Riscos de auth/PII/credentials não estão modelados.",
            recommendation=(
                "Considere adicionar assertions de segurança operacional em compliance.md "
                "com frontmatter `layer: 2`: autenticação, autorização, PII handling, rate limiting.\n"
                "Nota: se suas regras de segurança já estão em Layer 1 (compliance legal/regulatório), "
                "Layer 2 pode legitimamente permanecer vazio — este finding é apenas indicativo."
            ),
        ))
    elif by_layer.get(2, 0) < _L2_MIN_ASSERTIONS:
        findings.append(Finding(
            id="low_l2_coverage", category="coverage", severity="WARNING",
            title=f"Layer 2 (security): apenas {by_layer.get(2, 0)} assertion(s)",
            detail=f"Cobertura de security baixa (mínimo recomendado: {_L2_MIN_ASSERTIONS}).",
            recommendation="Adicionar rules de auth, credential handling, PII e secrets em L2",
        ))
    return findings


def _check_hot_context(data: dict, maes_dir: Path) -> list[Finding]:
    anti_h = data.get("anti-hallucination", [])
    cap = _hot_token_cap(maes_dir)
    tokens_used = sum(max(1, len(r.get("claim", "")) // 4) for r in anti_h)
    saturation = tokens_used / cap * 100 if cap else 0.0

    findings: list[Finding] = []
    if saturation > _HOT_SATURATION_PCT:
        findings.append(Finding(
            id="hot_context_saturated", category="hot_context", severity="WARNING",
            title=f"Hot context próximo da saturação ({saturation:.1f}%)",
            detail=f"{tokens_used}/{cap} tokens usados. A próxima assertion L1-L4 com alta confiança pode exceder o budget.",
            recommendation="Revisar claims do hot context para compressão ou mover assertions menos críticas para warm",
        ))

    layers_in_hot = {r.get("layer", 0) for r in anti_h}
    if anti_h and not layers_in_hot.intersection({1, 2, 3}):
        findings.append(Finding(
            id="hot_no_l1_l3", category="hot_context", severity="WARNING",
            title="Hot context sem assertions L1-L3",
            detail="Todas as regras no hot context são de L4+. Compliance/security/contracts não estão no hot tier.",
            recommendation="Verificar se assertions L1-L3 têm confidence 'explicit' ou 'inferred-high'",
        ))
    return findings


def _check_staleness_risk(data: dict) -> list[Finding]:
    assertions = data.get("assertions", [])
    findings: list[Finding] = []

    critical_stale = [
        a for a in assertions
        if a.get("layer", 7) <= 3
        and _stale_score_from_dict(a) >= _STALE_CRITICAL_SCORE
    ]
    if critical_stale:
        findings.append(Finding(
            id="layer_1_3_stale", category="staleness", severity="CRITICAL",
            title=f"{len(critical_stale)} assertion(s) L1-L3 com staleness crítico",
            detail=f"Assertions com staleness_score ≥ {_STALE_CRITICAL_SCORE} em layers críticos: "
                   + "; ".join(a.get("claim", "")[:50] for a in critical_stale[:2]),
            recommendation="Renovar as assertions ou atualizar `last_verified` após revisão",
        ))

    # L3 assertions that will be stale soon
    l3_assertions = [a for a in assertions if a.get("layer", 7) == 3]
    soon_stale: list[tuple[dict, int]] = []
    for a in l3_assertions:
        days = _days_until_stale(a)
        if days is not None and days < _L3_STALE_WARN_DAYS:
            soon_stale.append((a, days))

    if soon_stale:
        min_days = min(d for _, d in soon_stale)
        stale_date = date.today() + timedelta(days=max(0, min_days))
        findings.append(Finding(
            id="l3_stale_soon", category="staleness", severity="WARNING",
            title=f"{len(soon_stale)} assertion(s) L3 ficará(ão) stale em <{_L3_STALE_WARN_DAYS} dias",
            detail=f"Assertions em L3 (TTL 30d) vencerão por volta de {stale_date.isoformat()}. "
                   f"`maes validate` falhará em CI quando staleness_score ≥ 0.8.",
            recommendation=f"Renovar assertions L3 antes de {stale_date.isoformat()} ou ajustar TTL em `.maes/context/human/integrations.md`",
        ))
    return findings


_MAES_META_TERMS = frozenset({
    "maes", "sync", "compiler", "mcp", "validate", "analyze",
    "ingest", "normalize", "adapter", "anti-hallucination",
    "context add", "context/human", "context/inferred", "synthesis",
})


def _is_meta_maes(claim: str) -> bool:
    lower = claim.lower()
    return any(term in lower for term in _MAES_META_TERMS)


def _check_assertion_quality(data: dict) -> list[Finding]:
    assertions = data.get("assertions", [])
    if not assertions:
        return []

    findings: list[Finding] = []
    total = len(assertions)

    # L4 concentration
    l4_count = sum(1 for a in assertions if a.get("layer", 7) == 4)
    l4_ratio = l4_count / total if total else 0.0
    if l4_count > _L4_OVERLOAD_THRESHOLD and l4_ratio > _L4_OVERLOAD_RATIO:
        findings.append(Finding(
            id="l4_overloaded", category="assertion_quality", severity="WARNING",
            title=f"L4 (architecture) concentra {l4_count}/{total} assertions",
            detail=f"Mais de {_L4_OVERLOAD_THRESHOLD} assertions em L4 indica possível routing drift: "
                   "regras operacionais ou de princípios podem ter sido roteadas incorretamente para decisions.md.",
            recommendation="Revisar assertions L4 e mover regras de processo para L5/L6 via edição de `decisions.md`",
        ))

    # Enforcement density
    enforcement_count = sum(
        1 for a in assertions
        if a.get("type", "") in ("CONSTRAINT", "COMPLIANCE")
    )
    ratio = enforcement_count / total if total else 0.0
    if ratio < _ENFORCEMENT_RATIO_MIN:
        findings.append(Finding(
            id="low_enforcement_density", category="assertion_quality", severity="WARNING",
            title=f"Densidade de enforcement baixa: {enforcement_count}/{total} ({ratio:.0%})",
            detail=f"Apenas {ratio:.0%} das assertions são CONSTRAINT ou COMPLIANCE. "
                   "Predomínio de PATTERN significa que o sistema descreve mais do que constrange.",
            recommendation="Verificar se assertions descritivas deveriam ser reformuladas como CONSTRAINTs com 'nunca/never/obrigatório'",
        ))

    # Weak claims
    weak = [a for a in assertions if len(a.get("claim", "")) < _MIN_CLAIM_LEN]
    if weak:
        findings.append(Finding(
            id="weak_claims", category="assertion_quality", severity="INFO",
            title=f"{len(weak)} assertion(s) com claim muito curto (<{_MIN_CLAIM_LEN} chars)",
            detail="Claims curtos demais podem ser genéricos: " +
                   " | ".join(a.get("claim", "")[:40] for a in weak[:3]),
            recommendation="Expandir claims curtos com contexto específico e consequências",
        ))

    # Meta-MAES ratio
    meta_count = sum(1 for a in assertions if _is_meta_maes(a.get("claim", "")))
    meta_ratio = meta_count / total if total else 0.0
    if meta_ratio > 0.85:
        findings.append(Finding(
            id="high_meta_ratio", category="assertion_quality", severity="INFO",
            title=f"Alto ratio de assertions meta-MAES: {meta_count}/{total} ({meta_ratio:.0%})",
            detail="A maioria das assertions descreve o próprio MAES, não o domínio do projeto. "
                   "Isso é esperado em bootstrap mas limita o valor demonstrável a stakeholders.",
            recommendation="Adicionar assertions de domínio real (regras de negócio, integrações, invariantes do produto)",
        ))

    # Orphaned assertions (no owner)
    orphaned = [a for a in assertions if not a.get("owner", "").strip()]
    if orphaned:
        findings.append(Finding(
            id="orphaned_assertions", category="assertion_quality", severity="INFO",
            title=f"{len(orphaned)} assertion(s) sem owner",
            detail="Assertions sem owner não têm responsável por renovação e governance.",
            recommendation="Definir owner em `.maes/context/human/*.md` frontmatter",
        ))

    return findings


def _check_guard_quality(data: dict) -> list[Finding]:
    guards = data.get("guards", [])
    findings: list[Finding] = []

    global_inform = [
        g for g in guards
        if g.get("paths") == ["**"] and g.get("policy") == "inform"
    ]
    if global_inform:
        findings.append(Finding(
            id="global_inform_guard", category="guards", severity="INFO",
            title=f"{len(global_inform)} guard(s) com policy=inform em escopo global ['**']",
            detail="Guards inform em ['**'] são acionados em TODA operação de edição, gerando ruído.",
            recommendation="Considerar remover ou restringir a paths mais específicos se o claim não tiver paths claros",
        ))

    # Check if key output files are guarded
    all_paths = [p for g in guards for p in g.get("paths", [])]
    guarded_strs = " ".join(all_paths)
    missing: list[str] = []
    for adapter in ("CLAUDE.md", ".windsurfrules"):
        if adapter not in guarded_strs:
            missing.append(adapter)
    if missing:
        findings.append(Finding(
            id="missing_adapter_guards", category="guards", severity="WARNING",
            title=f"Adapter(s) sem guard de enforcement: {', '.join(missing)}",
            detail=f"{', '.join(missing)} são gerados por `maes sync` mas não têm guard protegendo-os de edição direta.",
            recommendation="Adicionar assertion CONSTRAINT com path para esses adapters em decisions.md ou business-rules.md",
        ))

    return findings


def _check_placeholder_fill(human_files: dict[str, str]) -> list[Finding]:
    total_placeholders = 0
    per_file: dict[str, int] = {}
    for fname, content in human_files.items():
        count = content.count("[ex:")
        if count:
            per_file[fname] = count
            total_placeholders += count

    if total_placeholders == 0:
        return []

    file_detail = ", ".join(f"{f}: {n}" for f, n in sorted(per_file.items()))
    return [Finding(
        id="placeholder_templates", category="coverage", severity="INFO",
        title=f"{total_placeholders} entradas placeholder [ex:] em human/*.md",
        detail=f"Templates de exemplo presentes (filtrados pelo compilador — não chegam ao synthesis): {file_detail}. "
               "São ruído visual para editores humanos mas não contaminam o contexto gerado.",
        recommendation="Execute `maes sync --clean` para remover automaticamente",
    )]


def _check_stale_module_paths(maes_dir: Path) -> list[Finding]:
    """Detect model.json where all modules have empty paths — indicates pre-fix analyze data."""
    model_file = maes_dir / "context" / "inferred" / "model.json"
    if not model_file.exists():
        return []
    try:
        data = json.loads(model_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    modules = [m for m in data.get("modules", []) if isinstance(m, dict)]
    if not modules:
        return []
    if any(m.get("paths") for m in modules):
        return []
    return [Finding(
        id="stale_module_paths",
        category="coverage",
        severity="WARNING",
        title=f"Module paths desatualizados — {len(modules)} módulo(s) com paths vazios",
        detail=(
            "Todos os módulos em inferred/model.json possuem paths vazios. "
            "Dados gerados antes do fix de normalização path/paths."
        ),
        recommendation="Invoke the /maes-analyze agent to regenerate model.json with correct paths.",
    )]


def _check_coverage_truncation(maes_dir: Path) -> list[Finding]:
    """Detect files truncated during /maes-analyze agent collection."""
    f = maes_dir / "context" / "inferred" / "coverage.json"
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    truncated = data.get("truncated_files", [])
    if not truncated:
        return []
    return [Finding(
        id="truncated_collection",
        category="coverage",
        severity="WARNING",
        title=f"{len(truncated)} arquivo(s) truncados na coleta do analyze",
        detail="Arquivos críticos amostrados parcialmente: " + ", ".join(truncated[:4]),
        recommendation=(
            "The /maes-analyze agent reached the maximum character budget. "
            "Re-analise o projeto ou aguarde suporte a budget configurável (P1B — deferred)."
        ),
    )]


# ─── Score ────────────────────────────────────────────────────────────────────

def _compute_score(findings: list[Finding]) -> tuple[int, str]:
    score = 100
    for f in findings:
        if f.severity == "CRITICAL":
            score -= 20
        elif f.severity == "WARNING":
            score -= 5
        elif f.severity == "INFO":
            score -= 1
    score = max(0, score)
    if score >= _GRADE_HEALTHY:
        grade = "HEALTHY"
    elif score >= _GRADE_ATTENTION:
        grade = "NEEDS_ATTENTION"
    else:
        grade = "CRITICAL"
    return score, grade


# ─── Rendering ────────────────────────────────────────────────────────────────

def _sev_icon(sev: Severity, color: bool = True) -> str:
    if sev == "CRITICAL":
        return "\033[31m✗\033[0m" if color else "✗"
    if sev == "WARNING":
        return "\033[33m✗\033[0m" if color else "✗"
    if sev == "INFO":
        return "\033[36m·\033[0m" if color else "·"
    return "\033[32m✓\033[0m" if color else "✓"


def _sev_label(sev: Severity) -> str:
    return f"[{sev}]"


def _grade_color(grade: str, text: str, color: bool) -> str:
    if not color:
        return text
    if grade == "HEALTHY":
        return f"\033[32m{text}\033[0m"
    if grade == "NEEDS_ATTENTION":
        return f"\033[33m{text}\033[0m"
    return f"\033[31m{text}\033[0m"


def _bold(text: str, color: bool) -> str:
    return f"\033[1m{text}\033[0m" if color else text


_CATEGORY_LABELS = {
    "conflicts": "Conflitos",
    "coverage": "Cobertura",
    "hot_context": "Hot Context",
    "staleness": "Risco de Staleness",
    "assertion_quality": "Qualidade das Assertions",
    "guards": "Guards",
}

_SECTION_ORDER = [
    "conflicts", "coverage", "hot_context", "staleness",
    "assertion_quality", "guards",
]


def _format_finding_line(f: Finding, verbose: bool, color: bool) -> list[str]:
    lines: list[str] = []
    icon = _sev_icon(f.severity, color)
    sev_label = "" if f.severity == "OK" else f"  {_sev_label(f.severity):<12}"
    lines.append(f"  {icon}{sev_label} {f.title}")
    if verbose and f.detail:
        for detail_line in f.detail.splitlines():
            lines.append(f"             {detail_line}")
    return lines


def _format_findings_by_category(
    by_cat: dict[str, list[Finding]], verbose: bool, color: bool
) -> list[str]:
    thin = "─" * 54
    lines: list[str] = []
    for cat in _SECTION_ORDER:
        cat_findings = by_cat.get(cat, [])
        if not cat_findings:
            continue
        label = _CATEGORY_LABELS.get(cat, cat.replace("_", " ").title())
        lines.append(_bold(f"── {label} ", color) + thin[len(label) + 4:])
        for f in sorted(cat_findings, key=lambda x: _SEV_ORDER[x.severity]):
            if f.severity == "OK" and not verbose:
                continue
            lines.extend(_format_finding_line(f, verbose, color))
        lines.append("")
    return lines


def _format_recommended_actions(findings: list[Finding], color: bool) -> list[str]:
    thin = "─" * 54
    actions = [f for f in findings if f.severity in ("CRITICAL", "WARNING")]
    actions.sort(key=lambda x: (_SEV_ORDER[x.severity], x.id))
    if not actions:
        return []
    lines = [_bold("── Ações Recomendadas ", color) + thin[22:]]
    for i, f in enumerate(actions, 1):
        lines.append(f"  {i}. {_sev_label(f.severity):<12} {f.recommendation}")
    lines.append("")
    return lines


def _render_report(
    findings: list[Finding],
    score: int,
    grade: str,
    data: dict,
    maes_dir: Path,
    verbose: bool,
    color: bool,
) -> str:
    assertions = data.get("assertions", [])
    guards = data.get("guards", [])
    anti_h = data.get("anti-hallucination", [])
    cap = _hot_token_cap(maes_dir)
    tokens_used = sum(max(1, len(r.get("claim", "")) // 4) for r in anti_h)
    project = _project_name(maes_dir)
    today = date.today().isoformat()

    sep = "═" * 54
    lines: list[str] = [
        _bold(f"MAES Audit Report — {project}", color),
        sep,
        f"Gerado: {today} | Score: {score}/100 | {_grade_color(grade, f'{grade} ({score}/100)', color)}",
        f"Assertions: {len(assertions)} | Guards: {len(guards)} | Hot context: {tokens_used}/{cap} tokens",
        "",
    ]

    by_cat: dict[str, list[Finding]] = {}
    for f in findings:
        by_cat.setdefault(f.category, []).append(f)

    lines.extend(_format_findings_by_category(by_cat, verbose, color))
    lines.extend(_format_recommended_actions(findings, color))

    return "\n".join(lines)


def _render_json(
    findings: list[Finding],
    score: int,
    grade: str,
    data: dict,
    maes_dir: Path,
) -> str:
    assertions = data.get("assertions", [])
    guards = data.get("guards", [])
    anti_h = data.get("anti-hallucination", [])
    cap = _hot_token_cap(maes_dir)
    tokens_used = sum(max(1, len(r.get("claim", "")) // 4) for r in anti_h)

    counts = {"CRITICAL": 0, "WARNING": 0, "INFO": 0}
    for f in findings:
        if f.severity in counts:
            counts[f.severity] += 1

    report = {
        "generated_at": date.today().isoformat(),
        "project": _project_name(maes_dir),
        "score": score,
        "grade": grade,
        "summary": {
            "assertions_total": len(assertions),
            "guards_total": len(guards),
            "conflicts_unresolved": sum(
                1 for c in data.get("conflicts", []) if c.get("status") == "UNRESOLVED"
            ),
            "hot_context_tokens_used": tokens_used,
            "hot_context_cap": cap,
            "hot_context_saturation_pct": round(tokens_used / cap * 100, 1) if cap else 0.0,
            "findings_critical": counts["CRITICAL"],
            "findings_warning": counts["WARNING"],
            "findings_info": counts["INFO"],
        },
        "findings": [
            {
                "id": f.id,
                "category": f.category,
                "severity": f.severity,
                "title": f.title,
                "detail": f.detail,
                "recommendation": f.recommendation,
            }
            for f in sorted(findings, key=lambda x: (_SEV_ORDER[x.severity], x.category, x.id))
            if f.severity != "OK"
        ],
        "recommended_actions": [
            f.recommendation
            for f in sorted(findings, key=lambda x: _SEV_ORDER[x.severity])
            if f.severity in ("CRITICAL", "WARNING") and f.recommendation
        ],
        "generated_by": "maes audit v1",
    }
    return json.dumps(report, ensure_ascii=False, indent=2)


# ─── Output files ─────────────────────────────────────────────────────────────

def _write_outputs(maes_dir: Path, md_text: str, json_text: str) -> tuple[Path, Path]:
    audit_dir = maes_dir / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    md_path = audit_dir / "latest-report.md"
    json_path = audit_dir / "latest-report.json"
    md_path.write_text(md_text, encoding="utf-8")
    json_path.write_text(json_text, encoding="utf-8")
    return md_path, json_path


# ─── Entry point ──────────────────────────────────────────────────────────────

def run_audit(
    maes_dir: Path,
    verbose: bool = False,
    fail_on_warning: bool = False,
    output_format: str = "both",
) -> int:
    synth_dir = maes_dir / "synthesis"
    if not (synth_dir / "assertions.json").exists():
        print("✗ Synthesis não encontrada. Rode `maes sync` primeiro.", file=sys.stderr)
        return 1

    print("MAES Audit", file=sys.stderr)
    print("─" * 54, file=sys.stderr)

    data = _load_synthesis(maes_dir)
    human_files = _load_human_files(maes_dir)

    print("  Rodando checks determinísticos...", file=sys.stderr)
    findings: list[Finding] = []
    findings += _check_conflicts(data)
    findings += _check_layer_coverage(data)
    findings += _check_hot_context(data, maes_dir)
    findings += _check_staleness_risk(data)
    findings += _check_assertion_quality(data)
    findings += _check_guard_quality(data)
    findings += _check_placeholder_fill(human_files)
    findings += _check_stale_module_paths(maes_dir)
    findings += _check_coverage_truncation(maes_dir)

    score, grade = _compute_score(findings)

    # Strip ANSI for markdown file
    md_text = _render_report(findings, score, grade, data, maes_dir, verbose=True, color=False)
    json_text = _render_json(findings, score, grade, data, maes_dir)

    # Terminal output
    if output_format in ("text", "both"):
        terminal_text = _render_report(findings, score, grade, data, maes_dir, verbose, color=True)
        print(terminal_text)
    if output_format == "json":
        print(json_text)

    # Write files
    md_path, json_path = _write_outputs(maes_dir, md_text, json_text)
    if output_format != "json":
        print(f"\nRelatório salvo em: {md_path}")
        print(f"Relatório salvo em: {json_path}")

    # Exit code
    has_critical = any(f.severity == "CRITICAL" for f in findings)
    has_warning = fail_on_warning and any(f.severity == "WARNING" for f in findings)
    return 1 if (has_critical or has_warning) else 0
