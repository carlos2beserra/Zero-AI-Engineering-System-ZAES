#!/usr/bin/env python3
"""MAES Compiler — build(), validate(), emit().

Public API:
  build(maes_dir)          → State          # merge + deduplicate (canonical by construction)
  validate(state, config)  → list[str]      # 3 invariant checks
  emit(maes_dir, state)    → None           # write synthesis/ + compat artifacts

Derived projections (on-demand, never persisted as primary state):
  derive_hot_context(assertions, cap)  → list[dict]
  derive_guards(assertions)            → list[dict]
  detect_conflicts(assertions)         → list[ConflictRecord]
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from .sampling_policy import has_population_semantics

from .models import (
    CONFIDENCE_RANK,
    LAYER_NAMES,
    _VALID_CONFIDENCE,
    _VALID_TYPES,
    Assertion,
    AssertionType,
    ConflictRecord,
    Domain,
    Module,
    RuntimeContext,
    StackContext,
    State,
    polarity,
)

# ─── File name constants ─────────────────────────────────────────────────────

_ARCH_MAP_FILENAME = "architecture_map.json"
_STACK_FILENAME = "stack.json"

# ─── TTL parsing (pure) ───────────────────────────────────────────────────────

_TTL_FALLBACK_DAYS = 730


def _parse_ttl_days(ttl: str) -> int:
    if not ttl:
        return _TTL_FALLBACK_DAYS
    m = re.match(r"^(\d+)d$", ttl.strip().lower())
    return int(m.group(1)) if m else _TTL_FALLBACK_DAYS


def staleness_score(assertion: Assertion, today: date) -> float:
    """Pure TTL-based staleness. 0.0 = fresh, 1.0 = fully expired."""
    ttl_days = _parse_ttl_days(assertion.ttl)
    try:
        verified = date.fromisoformat(assertion.last_verified)
    except (ValueError, TypeError):
        return 1.0
    age_days = max(0, (today - verified).days)
    return min(1.0, age_days / ttl_days)


# ─── Path extraction (for normalize) ─────────────────────────────────────────

_PATH_RE = re.compile(
    r"`([^`]*/[^`]*)`"
    r'|"([^"]*/[^"]*)"'
    r"|\*\*/[\w\-\.]+/?\*\*?"
    r"|(?:src|db|lib|app)/[\w\-/]+(?:/\*\*?)?"
    r"|(?:\.maes|\.claude|\.cursor|\.github)/[\w\-\./\*]+"
)

_NEVER_GUARD_PATHS = frozenset({
    ".maes/context/human",
    "context/human",
})


def _extract_paths(claim: str) -> list[str]:
    paths: list[str] = []
    for m in _PATH_RE.finditer(claim):
        p = m.group(1) or m.group(2) or m.group()
        if " " in p or len(p) > 100 or not p.strip():
            continue
        if "/" in p or "*" in p:
            if not any(p.startswith(ex) for ex in _NEVER_GUARD_PATHS):
                paths.append(p)
    return list(dict.fromkeys(paths))[:5]


# ─── Type classification (for human assertions from markdown) ─────────────────

_COMPLIANCE_TYPE_KW = frozenset({"compliance", "gdpr", "lgpd", "pci", "hipaa", "soc2",
                                   "audit", "regulat", "data protection"})
_CONTRACT_IMPL_KW = frozenset({
    "facade obrigatória", "camada intermediária obrigatória", "behavior_contract",
    "nunca bypassa", "obrigatório usar", "contrato de implementação",
    "boundary obrigatório", "sempre usar", "mandatory facade",
})
_CONSTRAINT_KW = frozenset({"nunca", "never", "obrigatório", "proibido", "forbidden",
                              "required", "must not", "deve sempre", "não deve",
                              "cannot", "não pode", "block", "bloquear",
                              "negar acesso", "recusar"})
_RATIONALE_KW = frozenset({"rationale", "decided", "escolhemos",
                             "adotamos", "substituído por", "porque optamos",
                             "optamos por", "decidimos por"})


def _classify_type(claim: str) -> AssertionType:
    lower = claim.lower()
    if any(kw in lower for kw in _COMPLIANCE_TYPE_KW):
        return "COMPLIANCE"
    if any(kw in lower for kw in _CONTRACT_IMPL_KW):
        return "CONTRACT"
    if any(kw in lower for kw in _CONSTRAINT_KW):
        return "CONSTRAINT"
    if any(kw in lower for kw in _RATIONALE_KW):
        return "RATIONALE"
    return "PATTERN"


# Layer classification keywords
_COMPLIANCE_LAYER_KW = frozenset({"gdpr", "lgpd", "pci", "hipaa", "soc2", "compliance",
                                    "regulat", "audit_log", "data protection"})
_SECURITY_KW = frozenset({"security", "auth", "authentication", "authorization", "token",
                           "credential", "encrypt", "tls", "ssl", "vulnerability",
                           "injection", "xss", "csrf"})
_CONTRACT_KW = frozenset({"contract", "sla", "external consumer", "webhook",
                           "api consumer", "breaking change", "contrato"})
_ARCHITECTURE_KW = frozenset({"architecture", "boundary", "module boundary",
                               "circular dep", "coupling", "dependency injection",
                               "arquitetura", "fronteira"})
_DOMAIN_KW = frozenset({"business rule", "domain", "invariant", "state machine",
                         "workflow", "elegibilidade", "saldo", "balance",
                         "regra de negócio", "domínio"})


def _classify_layer(claim: str, atype: str, source_type: str, explicit: int | None) -> int:
    if explicit is not None and source_type == "human":
        return max(1, min(7, explicit))
    lower = claim.lower()
    if atype == "COMPLIANCE" or any(kw in lower for kw in _COMPLIANCE_LAYER_KW):
        return 1
    if any(kw in lower for kw in _SECURITY_KW):
        return 2
    if any(kw in lower for kw in _CONTRACT_KW):
        return 3
    if any(kw in lower for kw in _ARCHITECTURE_KW):
        return 4
    if atype == "CONSTRAINT" and source_type == "human":
        return 5
    if any(kw in lower for kw in _DOMAIN_KW):
        return 5
    if source_type == "human":
        return 6
    return 7


# ─── Human context parsing ────────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    try:
        import yaml
    except ImportError:
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    try:
        fm = yaml.safe_load(parts[1]) or {}
        return fm, parts[2].strip()
    except Exception:
        return {}, content


def _strip_html_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


_TEMPLATE_PLACEHOLDERS = re.compile(
    r"^\[ex:|^\[exemplo|^\[preencher|^\[descreva|^\[adicione",
    re.IGNORECASE,
)


def _is_placeholder(text: str) -> bool:
    stripped = text.strip()
    return (
        (stripped.startswith("[") and stripped.endswith("]"))
        or bool(_TEMPLATE_PLACEHOLDERS.match(stripped))
    )


# Unresolved-placeholder markers (P0-A hardening). A human seed bullet bearing one
# of these is a *task* ("confirm or delete"), not confirmed knowledge — it must NOT
# become an assertion, regardless of the file's frontmatter confidence.
#
# Match ONLY structural markers, never bare content words: a naive case-insensitive
# substring match on TODO/VALIDAR/CONFIRMAR/REVISAR is catastrophic in pt-BR
# ("Todo usuário deve…", "deve validar o CPF"). The maes-analyze agent emits the
# structured form `- [INFERRED] … — confirme ou remova após revisão`, caught here by
# the bracket tag AND the review phrase.
_BRACKET_TAG = re.compile(r"^\s*\[(?:INFERRED|ASSUMED|TODO|FIXME)\]", re.IGNORECASE)
# Case-SENSITIVE on purpose: the code marker is uppercase "TODO"/"FIXME". Matching
# case-insensitively would eat the pt-BR word "Todo"/"todo" ("every/all") that begins
# countless legitimate rules (e.g. "Todo usuário deve ter MFA").
_LEADING_TODO = re.compile(r"^\s*(?:TODO|FIXME)\b[:\s]")
_REVIEW_PHRASES = re.compile(
    r"confirme ou remova|confirmar ou remover|review required",
    re.IGNORECASE,
)


def _has_unresolved_marker(text: str) -> bool:
    return bool(
        _BRACKET_TAG.match(text)
        or _LEADING_TODO.match(text)
        or _REVIEW_PHRASES.search(text)
    )


def _extract_bullet_points(text: str) -> list[str]:
    bullets = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "+ ")):
            claim = stripped[2:].strip()
            if claim.startswith(("- ", "* ", "+ ")):
                claim = claim[2:].strip()
            if len(claim) > 10 and not _is_placeholder(claim):
                bullets.append(claim)
        elif re.match(r"^\d+\.\s", stripped):
            claim = re.sub(r"^\d+\.\s+", "", stripped).strip()
            if len(claim) > 10 and not _is_placeholder(claim):
                bullets.append(claim)
    return bullets


def _extract_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if current_title or current_lines:
                sections.append((current_title, "\n".join(current_lines)))
            current_title = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_title or current_lines:
        sections.append((current_title, "\n".join(current_lines)))
    return sections


def _resolve_human_confidence(frontmatter: dict, md_file_name: str) -> str:
    """Provenance: absent confidence defaults to the human-channel intent
    (explicit). A value that is PRESENT but invalid must NOT be promoted to
    explicit — that silently turns a human's mistyped uncertainty marker (e.g.
    "inferred", "low") into a hard claim. Downgrade + warn."""
    if "confidence" not in frontmatter:
        return "explicit"
    confidence_raw = str(frontmatter.get("confidence"))
    if confidence_raw in _VALID_CONFIDENCE:
        return confidence_raw
    print(
        f"WARNING: human assertion in {md_file_name} has invalid "
        f"confidence='{confidence_raw}'. Downgrading to inferred-medium.",
        file=sys.stderr,
    )
    return "inferred-medium"


def _human_assertions_from_file(md_file: Path, today: str) -> list[Assertion]:
    try:
        content = md_file.read_text(encoding="utf-8")
    except OSError:
        return []
    frontmatter, body = _parse_frontmatter(content)
    body = _strip_html_comments(body)

    layer_raw = frontmatter.get("layer", 6)
    layer = int(layer_raw) if isinstance(layer_raw, (int, float)) else 6
    ttl = str(frontmatter.get("ttl", "90d"))
    owner = str(frontmatter.get("owner", ""))
    last_verified = str(frontmatter.get("last_verified", "")) or today
    confidence = _resolve_human_confidence(frontmatter, md_file.name)
    source = f"human/{md_file.name}"

    assertions: list[Assertion] = []
    for _section_title, section_content in _extract_sections(body):
        for bullet in _extract_bullet_points(section_content):
            claim = bullet.strip()[:2000]
            if _has_unresolved_marker(claim):
                print(
                    f"WARNING: dropping unresolved-placeholder bullet in "
                    f"{md_file.name}: {claim[:80]!r}",
                    file=sys.stderr,
                )
                continue
            atype = _classify_type(claim)
            actual_layer = _classify_layer(claim, atype, "human", layer)
            assertions.append(Assertion(
                id=Assertion.make_id(claim),
                claim=claim,
                type=atype,
                layer=actual_layer,
                subject=None,
                paths=_extract_paths(claim),
                confidence=confidence,
                source=source,
                ttl=ttl,
                last_verified=last_verified,
                owner=owner,
            ))
    return assertions


def _parse_human_assertions(human_dir: Path) -> list[Assertion]:
    today = date.today().isoformat()
    assertions: list[Assertion] = []
    for md_file in sorted(human_dir.glob("*.md")):
        assertions.extend(_human_assertions_from_file(md_file, today))
    return assertions


# ─── Inferred context parsing ─────────────────────────────────────────────────

def _load_json(path: Path) -> dict | list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _parse_inferred_assertions(inferred_dir: Path) -> list[Assertion]:
    """Read inferred/assertions.json (canonical format only — MAES v2).

    Returns an empty list if the file does not exist yet (e.g. right after
    ``maes init`` before ``maes analyze`` has been run).  A warning is printed
    so the user knows they need to run ``maes analyze`` for full context.
    """
    canonical_file = inferred_dir / "assertions.json"
    if not canonical_file.exists():
        return []
    return _load_canonical_assertions(canonical_file)


_INFERRED_SOURCE = "inferred/assertions.json"


def _enforce_inferred_provenance(confidence: str, source: object) -> tuple[str, str]:
    """Guard (P0-A2): assertions loaded from the INFERRED channel must never
    carry human/explicit provenance. The canonical builder always emits
    inferred-* + an inferred source; anything else means the file was
    hand-edited or tampered. Downgrade + warn — never fail the pipeline (pilot
    policy). Post-pilot this becomes a hard error in --validate.
    """
    if confidence == "explicit":
        print(
            "WARNING: inferred assertion contains confidence=explicit. "
            "Downgrading to inferred-medium.",
            file=sys.stderr,
        )
        confidence = "inferred-medium"
    src = source if isinstance(source, str) else _INFERRED_SOURCE
    if src.startswith("human/"):
        print(
            f"WARNING: inferred assertion declares source='{src}'. "
            f"Normalizing to {_INFERRED_SOURCE}.",
            file=sys.stderr,
        )
        src = _INFERRED_SOURCE
    return confidence, src


def _load_canonical_assertions(path: Path) -> list[Assertion]:
    """Load assertions from new canonical assertions.json format."""
    data = _load_json(path)
    if not isinstance(data, list):
        return []
    assertions = []
    for item in data:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim", "")).strip()
        if not claim:
            continue
        confidence = item.get("confidence", "inferred-medium")
        if confidence not in _VALID_CONFIDENCE:
            confidence = "inferred-medium"
        confidence, source = _enforce_inferred_provenance(
            confidence, item.get("source", _INFERRED_SOURCE)
        )
        atype = item.get("type", "PATTERN")
        if atype not in _VALID_TYPES:
            atype = "PATTERN"
        layer = item.get("layer", 7)
        if not isinstance(layer, int) or not (1 <= layer <= 7):
            layer = 7
        assertions.append(Assertion(
            id=item.get("id") or Assertion.make_id(claim),
            claim=claim,
            type=atype,
            layer=layer,
            subject=item.get("subject"),
            paths=item.get("paths", []),
            confidence=confidence,
            source=source,
            ttl=item.get("ttl", "90d"),
            last_verified=item.get("last_verified", "") or date.today().isoformat(),
            owner=item.get("owner", ""),
            merge_history=item.get("merge_history", []),
            code_examples=item.get("code_examples", []),
            evidence=item.get("evidence"),
            scope_type=item.get("scope_type", "global"),
            node_id=item.get("node_id"),
        ))
    return assertions


def _parse_modules_from_data(data: dict) -> list[Module]:
    modules = []
    for item in data.get("modules", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        domain = str(item.get("domain", "")).strip() or "general"
        paths = [str(p) for p in item.get("paths", []) if p]
        modules.append(Module(
            id=item.get("id") or Module.make_id(name),
            name=name,
            domain=domain,
            paths=paths,
        ))
    return modules


def _derive_domains(modules: list[Module], data: dict) -> list[Domain]:
    domains = []
    seen_names: set[str] = set()
    # Add explicitly declared domains
    for item in data.get("domains", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if name and name not in seen_names:
            domains.append(Domain(name=name))
            seen_names.add(name)
    # Derive domains from modules (ensure all module.domain values are registered)
    for m in modules:
        if m.domain not in seen_names:
            domains.append(Domain(name=m.domain))
            seen_names.add(m.domain)
    return domains


def _parse_inferred_model(inferred_dir: Path) -> tuple[list[Module], list[Domain]]:
    """Read model.json for modules and domains, if it exists."""
    model_file = inferred_dir / "model.json"
    if not model_file.exists():
        return [], []
    data = _load_json(model_file)
    if not isinstance(data, dict):
        return [], []
    modules = _parse_modules_from_data(data)
    return modules, _derive_domains(modules, data)


def _parse_inferred_arch_map(inferred_dir: Path) -> "list":
    """Read architecture_map.json → list[ArchitectureNode]. Returns [] if absent."""
    from .models import ArchitectureNode
    arch_file = inferred_dir / _ARCH_MAP_FILENAME
    if not arch_file.exists():
        return []
    data = _load_json(arch_file)
    if not isinstance(data, dict):
        return []
    nodes = []
    for n in data.get("nodes", []):
        if not isinstance(n, dict) or not n.get("path"):
            continue
        nodes.append(ArchitectureNode(
            id=n.get("id", ""),
            stable_key=n.get("stable_key", n.get("id", "")),
            name=n.get("name", ""),
            path=n.get("path", ""),
            type=n.get("type", "Service"),
            domain=n.get("domain", ""),
            domain_confidence=float(n.get("domain_confidence", 0.5)),
            visibility=n.get("visibility", "obvious"),
            entry_points=list(n.get("entry_points", [])),
            dependencies=list(n.get("dependencies", [])),
            file_count=int(n.get("file_count", 0)),
        ))
    return nodes


# ─── Stack normalization (C2) ────────────────────────────────────────────────
#
# inferred/stack.json contains an unstructured dict from the analyzer LLM.
# Observed shapes in the wild:
#   {languages: [...], frameworks: [...]}
#   {backend: {language, framework, runtime}, frontend: {...}}
#   {primary_language: "...", frameworks: [...]}
#   {language: "...", runtime: "..."}
# _normalize_stack collapses all known shapes to a fixed StackContext schema.
# Unknown fields are silently ignored. Missing fields become empty tuples.
# Strings are deduplicated and sorted for determinism. Returns an empty
# StackContext when input is unusable (so adapters omit the section).

_STACK_LANGUAGE_KEYS = ("languages", "language", "primary_language", "langs")
_STACK_FRAMEWORK_KEYS = ("frameworks", "framework", "libraries", "libs")
_STACK_RUNTIME_KEYS = ("runtimes", "runtime", "platforms", "platform")
_STACK_PKG_MGR_KEYS = ("package_managers", "package_manager", "pkg_managers", "pm")
_STACK_NESTED_KEYS = ("backend", "frontend", "mobile", "infra", "infrastructure", "build")


def _coerce_str_list(value) -> list[str]:
    """Coerce str | list | None into list[str], dropping empties."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            if isinstance(v, str) and v.strip():
                out.append(v.strip())
        return out
    return []


def _collect_stack_field(raw: dict, keys: tuple[str, ...]) -> list[str]:
    """Pull values from any of the named keys at the top level."""
    out: list[str] = []
    for key in keys:
        if key in raw:
            out.extend(_coerce_str_list(raw[key]))
    return out


def _normalize_stack(raw) -> StackContext:
    """Normalize raw stack dict from inferred/stack.json into a fixed schema."""
    if not isinstance(raw, dict) or not raw:
        return StackContext()

    languages: list[str] = []
    frameworks: list[str] = []
    runtimes: list[str] = []
    package_managers: list[str] = []

    # Top-level keys
    languages.extend(_collect_stack_field(raw, _STACK_LANGUAGE_KEYS))
    frameworks.extend(_collect_stack_field(raw, _STACK_FRAMEWORK_KEYS))
    runtimes.extend(_collect_stack_field(raw, _STACK_RUNTIME_KEYS))
    package_managers.extend(_collect_stack_field(raw, _STACK_PKG_MGR_KEYS))

    # Nested keys (backend/frontend/etc) — recurse one level
    for nested_key in _STACK_NESTED_KEYS:
        nested = raw.get(nested_key)
        if isinstance(nested, dict):
            languages.extend(_collect_stack_field(nested, _STACK_LANGUAGE_KEYS))
            frameworks.extend(_collect_stack_field(nested, _STACK_FRAMEWORK_KEYS))
            runtimes.extend(_collect_stack_field(nested, _STACK_RUNTIME_KEYS))
            package_managers.extend(_collect_stack_field(nested, _STACK_PKG_MGR_KEYS))

    def _dedup(items: list[str]) -> tuple[str, ...]:
        seen: dict[str, None] = {}
        for x in items:
            seen.setdefault(x, None)
        return tuple(sorted(seen))

    return StackContext(
        languages=_dedup(languages),
        frameworks=_dedup(frameworks),
        runtimes=_dedup(runtimes),
        package_managers=_dedup(package_managers),
    )


def _parse_inferred_stack(inferred_dir: Path) -> StackContext:
    """Read inferred/stack.json and normalize to StackContext.
    Returns empty StackContext when file absent or unusable."""
    stack_file = inferred_dir / _STACK_FILENAME
    if not stack_file.exists():
        return StackContext()
    raw = _load_json(stack_file)
    return _normalize_stack(raw)


# ─── Runtime context (I4 — staleness-aware command catalog) ───────────────────
#
# context/human/runtime.md frontmatter carries the canonical commands agents
# should run for test/build/lint/run/migrate. We require `last_verified` so
# stale runtime info can be flagged rather than silently consumed.

_RUNTIME_FILENAME = "runtime.md"
_RUNTIME_STALE_THRESHOLD_DAYS = 30
_RUNTIME_FIELDS = (
    "test", "build", "lint", "run", "migrate",
    "test_pattern", "run_module_test",
)


def _is_runtime_stale(last_verified: str, today: date) -> bool:
    """True when last_verified is missing/malformed OR older than threshold."""
    if not last_verified:
        return True
    try:
        d = date.fromisoformat(last_verified)
    except (ValueError, TypeError):
        return True
    return (today - d).days > _RUNTIME_STALE_THRESHOLD_DAYS


def _parse_human_runtime(human_dir: Path, today: date | None = None) -> RuntimeContext:
    """Read context/human/runtime.md frontmatter into RuntimeContext.
    Returns empty RuntimeContext when file absent. When present but with a
    missing/old last_verified, sets staleness_warning=True."""
    if today is None:
        today = date.today()
    runtime_file = human_dir / _RUNTIME_FILENAME
    if not runtime_file.exists():
        return RuntimeContext()
    try:
        content = runtime_file.read_text(encoding="utf-8")
    except OSError:
        return RuntimeContext()
    frontmatter, _body = _parse_frontmatter(content)
    if not isinstance(frontmatter, dict):
        return RuntimeContext()

    fields = {k: str(frontmatter.get(k, "") or "").strip() for k in _RUNTIME_FIELDS}
    last_verified = str(frontmatter.get("last_verified", "") or "").strip()
    stale = _is_runtime_stale(last_verified, today)
    return RuntimeContext(
        **fields,
        last_verified=last_verified,
        staleness_warning=stale,
    )


# ─── Merge (human wins over inferred) ────────────────────────────────────────

def _merge(maes_dir: Path) -> State:
    inferred_dir = maes_dir / "context" / "inferred"
    human_dir = maes_dir / "context" / "human"

    modules: list[Module] = []
    domains: list[Domain] = []
    arch_map: list = []
    stack: StackContext = StackContext()
    runtime: RuntimeContext = RuntimeContext()

    if inferred_dir.exists():
        modules, domains = _parse_inferred_model(inferred_dir)
        arch_map = _parse_inferred_arch_map(inferred_dir)
        stack = _parse_inferred_stack(inferred_dir)

    inferred_assertions: list[Assertion] = []
    if inferred_dir.exists():
        inferred_assertions = _parse_inferred_assertions(inferred_dir)

    human_assertions: list[Assertion] = []
    if human_dir.exists():
        human_assertions = _parse_human_assertions(human_dir)
        runtime = _parse_human_runtime(human_dir)

    # Merge: human wins over inferred for same ID
    merged: dict[str, Assertion] = {a.id: a for a in inferred_assertions}
    for a in human_assertions:
        merged[a.id] = a  # human always overwrites inferred

    return State(
        modules=modules,
        domains=domains,
        assertions=list(merged.values()),
        architecture_map=arch_map,
        stack=stack,
        runtime=runtime,
    )


# ─── Deduplicate (Jaccard ≥ 0.85) — canonical by construction ─────────────────

_STOP_WORDS = frozenset({"a", "o", "e", "de", "da", "do", "em", "um", "uma",
                          "the", "is", "to", "of", "and", "or", "in", "for"})


def _keyword_set(text: str) -> frozenset[str]:
    tokens = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return frozenset(t for t in tokens if t not in _STOP_WORDS and len(t) > 2)


def _jaccard(a: str, b: str) -> float:
    ka, kb = _keyword_set(a), _keyword_set(b)
    union = ka | kb
    return len(ka & kb) / len(union) if union else 0.0


def _deduplicate(assertions: list[Assertion]) -> list[Assertion]:
    result: list[Assertion] = []
    absorbed: set[str] = set()

    for i, a in enumerate(assertions):
        if a.id in absorbed:
            continue
        group = [a]
        for b in assertions[i + 1:]:
            if b.id in absorbed:
                continue
            if _jaccard(a.claim, b.claim) >= 0.85:
                group.append(b)
                absorbed.add(b.id)
        if len(group) > 1:
            best = max(group, key=lambda x: (
                CONFIDENCE_RANK.get(x.confidence, 0),
                8 - x.layer,
                -len(x.claim),
            ))
            best.merge_history = [g.id for g in group if g.id != best.id]
            result.append(best)
        else:
            result.append(a)

    return sorted(result, key=lambda x: (x.layer, -CONFIDENCE_RANK.get(x.confidence, 0)))


# ─── build() — public: always returns canonical (deduplicated) State ──────────

def build(maes_dir: Path) -> State:
    """Read all context sources, merge (human wins), and deduplicate.

    Invariant: returned State has no semantic duplicates (Canonical Model).
    """
    state = _merge(maes_dir)
    deduped = _deduplicate(state.assertions)
    return State(
        modules=state.modules,
        domains=state.domains,
        assertions=deduped,
        architecture_map=state.architecture_map,
        stack=state.stack,
        runtime=state.runtime,
    )


# ─── validate() — 3 invariant checks ─────────────────────────────────────────

def _validate_coverage(config: dict, domain_names: set[str]) -> list[str]:
    """Invariant 1: critical_domains represented in modules/domains."""
    errors: list[str] = []
    critical_domains: list[str] = config.get("critical_domains", [])
    if not critical_domains:
        critical_domains = list(config.get("compiler", {}).get("critical_domains", []))
    for required in critical_domains:
        if required.lower() not in domain_names:
            errors.append(f"Critical domain missing: '{required}'")
    return errors


def _validate_consistency(state: State, domain_names: set[str]) -> list[str]:
    """Invariant 2: module→domain refs, assertion→subject refs, type/layer range."""
    errors: list[str] = []
    # module.domain references valid domain
    for m in state.modules:
        if m.domain.lower() not in domain_names:
            errors.append(f"Module '{m.name}' references unknown domain '{m.domain}'")
    # assertion.subject references valid module/domain
    module_ids = {m.id for m in state.modules}
    valid_subjects = module_ids | {d.name for d in state.domains} | {d.name.lower() for d in state.domains}
    for a in state.assertions:
        if a.subject and a.subject not in valid_subjects:
            errors.append(f"Assertion {a.id[:8]} → unknown subject '{a.subject}'")
    # Assertion.type and layer range validation
    for a in state.assertions:
        if a.type not in _VALID_TYPES:
            errors.append(f"Assertion {a.id[:8]}: invalid type '{a.type}'")
        if not (1 <= a.layer <= 7):
            errors.append(f"Assertion {a.id[:8]}: layer {a.layer} out of 1–7")
    return errors


def _validate_staleness(state: State, today: date) -> list[str]:
    """Invariant 3 (CI gate): Staleness ≥ 0.8 in layers 1–3."""
    errors: list[str] = []
    for a in state.assertions:
        if a.layer <= 3 and staleness_score(a, today) >= 0.8:
            errors.append(
                f"Stale assertion (layer {a.layer}): {a.id[:8]} "
                f"[{a.claim[:60]}...]"
            )
    return errors


def _validate_conflicts(state: State) -> list[str]:
    """CI gate: detect UNRESOLVED conflicts."""
    errors: list[str] = []
    conflicts = detect_conflicts(state.assertions)
    unresolved = [c for c in conflicts if c.status == "UNRESOLVED"]
    for c in unresolved:
        errors.append(f"UNRESOLVED conflict {c.id}: {c.reason[:80]}")
    return errors


def validate(state: State, config: dict) -> list[str]:
    """Check the 3 runtime invariants. Returns list of errors (empty = valid).

    Invariant 1: Coverage — critical domains represented in modules
    Invariant 2: Consistency — no broken references between entities
    Invariant 3 (CI gate): Staleness ≥ 0.8 in layers 1–3

    Also checks UNRESOLVED conflicts (part of the CI gate).
    """
    today = date.today()
    domain_names = {m.domain.lower() for m in state.modules}
    # Also include explicitly declared domains
    domain_names |= {d.name.lower() for d in state.domains}
    errors: list[str] = []
    errors += _validate_coverage(config, domain_names)
    errors += _validate_consistency(state, domain_names)
    errors += _validate_staleness(state, today)
    errors += _validate_conflicts(state)
    return errors


# ─── Conflict detection (derived on-demand) ───────────────────────────────────

_STRUCTURAL_WORDS = frozenset({
    "usar", "use", "nunca", "never", "deve", "should",
    "injetar", "inject", "injeção", "injection", "injetado",
    "diretamente", "directly", "sempre", "always",
    "obrigatório", "required", "proibido", "forbidden",
    "serviço", "service", "módulo", "module",
    "implementação", "implementation", "código", "code",
    "através", "via", "para", "with", "from", "into",
    "retorna", "return", "returns", "recebe", "receive",
    "método", "method", "classe", "class", "função", "function",
    # Portuguese function words — common across unrelated assertions
    "não", "por", "mas", "que", "ser", "ter", "seu", "sua",
    "antes", "depois", "quando", "onde", "como", "qual", "mais",
    "sendo", "tendo", "está", "são", "foi",
})


def _conflict_subject_overlap(a: Assertion, b: Assertion) -> bool:
    shared = _keyword_set(a.claim) & _keyword_set(b.claim)
    return len(shared) >= 2 and bool(shared - _STRUCTURAL_WORDS)


def _is_conflict_candidate(a: Assertion, b: Assertion, pol_a: int) -> bool:
    if a.layer != b.layer:
        return False
    pol_b = polarity(b.type)
    if pol_b == 0 or pol_a == pol_b:
        return False
    return _conflict_subject_overlap(a, b)


def _make_conflict_record(
    a: Assertion, b: Assertion, conf_a: int, conf_b: int, index: int
) -> ConflictRecord:
    if conf_a != conf_b:
        winner = a.id if conf_a > conf_b else b.id
        return ConflictRecord(
            id=f"CONFLICT-{index:03d}",
            assertion_a=a.id,
            assertion_b=b.id,
            status="RESOLVED",
            reason=f"Higher confidence wins ({a.confidence} vs {b.confidence})",
            winner=winner,
        )
    return ConflictRecord(
        id=f"CONFLICT-{index:03d}",
        assertion_a=a.id,
        assertion_b=b.id,
        status="UNRESOLVED",
        reason=(
            f"Same layer ({LAYER_NAMES.get(a.layer, str(a.layer))}), "
            f"same confidence ({a.confidence}) — requires human resolution"
        ),
    )


def detect_conflicts(assertions: list[Assertion]) -> list[ConflictRecord]:
    conflicts: list[ConflictRecord] = []
    seen: set[frozenset[str]] = set()

    for i, a in enumerate(assertions):
        pol_a = polarity(a.type)
        if pol_a == 0:
            continue
        for b in assertions[i + 1:]:
            pair = frozenset([a.id, b.id])
            if pair in seen or not _is_conflict_candidate(a, b, pol_a):
                continue
            seen.add(pair)
            conf_a = CONFIDENCE_RANK.get(a.confidence, 0)
            conf_b = CONFIDENCE_RANK.get(b.confidence, 0)
            conflicts.append(_make_conflict_record(a, b, conf_a, conf_b, len(conflicts)))

    return conflicts


# ─── Derived projections (on-demand, never stored as primary state) ───────────

def derive_hot_context(assertions: list[Assertion], cap: int = 800) -> list[dict]:
    """Project layers 1–3 assertions into hot-context format within token cap."""
    result: list[dict] = []
    tokens_used = 0
    eligible = [
        a for a in assertions
        if a.layer <= 3
        and a.confidence in ("explicit", "inferred-high")
        and not _has_unresolved_marker(a.claim)
    ]
    for a in eligible:
        estimated = max(1, len(a.claim) // 4)
        if tokens_used + estimated > cap:
            continue
        result.append({
            "claim": a.claim,
            "layer": a.layer,
            "layer_name": LAYER_NAMES.get(a.layer, ""),
            "source": a.source,
            "confidence": a.confidence,
        })
        tokens_used += estimated
    return result


_MIGRATION_KW = frozenset({"migration", "migrate", "migrations", "alembic",
                             "liquibase", "flyway", "prisma migrate"})

_MIGRATION_CHECKLIST = [
    "Análise de downtime foi feita?",
    "Plano de rollback está definido?",
    "Migration inclui script de rollback?",
    "Tabelas afetadas têm volume > 10M rows? (se sim, usar lock-free strategy)",
    "Esta migration inclui data migration separada?",
]


def _infer_checklist(claim: str) -> list[str]:
    lower = claim.lower()
    if any(kw in lower for kw in _MIGRATION_KW):
        return _MIGRATION_CHECKLIST
    return []


def _infer_policy(layer: int) -> str:
    if layer <= 2:
        return "block"
    if layer <= 4:
        return "requires-approval"
    return "requires-checklist"


def _should_emit_guard(a: Assertion) -> bool:
    return a.type in ("CONSTRAINT", "COMPLIANCE", "CONTRACT") and (bool(a.paths) or a.layer <= 3)


def _build_guard_entry(a: Assertion) -> dict:
    has_paths = bool(a.paths)
    return {
        "id": f"guard-{a.id}",
        "claim": a.claim,
        "paths": a.paths if has_paths else ["**"],
        "policy": _infer_policy(a.layer) if has_paths else "inform",
        "layer": a.layer,
        "source_file": a.source,
        "checklist": _infer_checklist(a.claim),
        "owner": a.owner,
        "guard_type": "enforcement" if has_paths else "contextual",
    }


def _dedup_guards_by_paths(guards: list[dict]) -> list[dict]:
    # Deduplicate by path set: keep highest-priority (lowest layer) guard per path set
    best: dict[frozenset, dict] = {}
    for g in guards:
        key = frozenset(g["paths"])
        if key not in best or g["layer"] < best[key]["layer"]:
            best[key] = g
    return [g for g in guards if best[frozenset(g["paths"])] is g]


def derive_guards(assertions: list[Assertion]) -> list[dict]:
    """Project CONSTRAINT/COMPLIANCE/CONTRACT assertions into guard format."""
    guards: list[dict] = []
    seen_claims: set[str] = set()

    for a in assertions:
        if not _should_emit_guard(a):
            continue
        claim_key = a.claim[:60]
        if claim_key in seen_claims:
            continue
        seen_claims.add(claim_key)
        guards.append(_build_guard_entry(a))

    return _dedup_guards_by_paths(guards)


# ─── Impact graph (C1 — path-resolvable dependency index) ─────────────────────
#
# architecture_map.json carries module-level edges keyed by stable_key. Agents
# (and the MCP layer) need to answer "who depends on this file?" — which
# requires both a reverse index AND a path→stable_key resolver. We pre-compute
# both into synthesis/impact-graph.json so MCP tools and adapters can read a
# single file without re-traversing architecture_map.json.

_IMPACT_SCHEMA_VERSION = "1.0"
# 1.1 adds two status values: insufficient_sample and no_observed_convention.
_PLACEMENT_SCHEMA_VERSION = "1.1"


def _build_dep_indices(edges: list) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Return (forward, reverse) adjacency from edge list."""
    forward: dict[str, set[str]] = {}
    reverse: dict[str, set[str]] = {}
    for e in edges:
        if not isinstance(e, dict):
            continue
        src = e.get("from")
        tgt = e.get("to")
        if not src or not tgt:
            continue
        forward.setdefault(src, set()).add(tgt)
        reverse.setdefault(tgt, set()).add(src)
    return forward, reverse


def _node_path_list(n: dict) -> list[str]:
    """Collect primary path + entry_points for a single arch node."""
    paths: list[str] = []
    primary = n.get("path")
    if primary:
        paths.append(primary)
    for ep in n.get("entry_points") or []:
        if ep and ep not in paths:
            paths.append(ep)
    return paths


def _build_node_files(nodes: list) -> dict[str, list[str]]:
    """Return stable_key → [path] index (primary path + entry_points)."""
    out: dict[str, list[str]] = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        key = n.get("stable_key") or n.get("id")
        if not key:
            continue
        paths = _node_path_list(n)
        if paths:
            out[key] = paths
    return out


def _build_impact_graph(arch_map_path: Path) -> dict | None:
    """Build impact-graph.json payload from architecture_map.json on disk.

    Returns None if architecture_map.json is unreadable or empty.
    Schema:
        {
          schema_version, generated_at,
          forward_deps: {stable_key: [stable_key]},
          reverse_deps: {stable_key: [stable_key]},
          node_files:   {stable_key: [path]},
          stats: {edge_count, node_count, max_fan_in, max_fan_out}
        }
    """
    data = _load_json(arch_map_path)
    if not isinstance(data, dict):
        return None

    nodes = data.get("nodes") or []
    edges = (data.get("graph") or {}).get("edges") or []

    forward, reverse = _build_dep_indices(edges)
    node_files = _build_node_files(nodes)

    fan_out = {k: len(v) for k, v in forward.items()}
    fan_in = {k: len(v) for k, v in reverse.items()}

    return {
        "schema_version": _IMPACT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # Edges are derived from architecture_map's heuristic dep graph (relative-import
        # resolution may misattribute/fabricate edges; alias imports are not captured).
        # Machine-readable trust flags — agents act on flags, not prose.
        "reliability": {
            "authoritative": False,
            "trust_level": "experimental",
            "agent_safe": False,
        },
        "forward_deps": {k: sorted(v) for k, v in sorted(forward.items())},
        "reverse_deps": {k: sorted(v) for k, v in sorted(reverse.items())},
        "node_files": {k: node_files[k] for k in sorted(node_files)},
        "stats": {
            "edge_count": sum(len(v) for v in forward.values()),
            "node_count": len(node_files),
            "max_fan_in": max(fan_in.values()) if fan_in else 0,
            "max_fan_out": max(fan_out.values()) if fan_out else 0,
        },
    }


# ─── Code placement map (I5/I6 — convention discovery) ────────────────────────
#
# Agents need to know "where do Services live?" before scaffolding new code.
# We aggregate arch_map nodes by node.type, find the dominant directory prefix
# weighted by file_count, and assign a confidence tier:
#   high   ≥ 80% of files under the prefix → strong convention
#   medium 50–80%                          → soft convention
#   low    < 50%                           → scattered (renders ⚠️ warning)
# Adapters expose only high/medium placements by default; low entries inform
# agents to grep before writing.

_PLACEMENT_PREFIX_DEPTH = 3  # consider up to first 3 path segments
_CONFIDENCE_HIGH = 0.80
_CONFIDENCE_MEDIUM = 0.50
# A convention must be more specific than a single top-level segment. `Service → src`
# (or worse, `Service → <repo dir>`) answers nothing while scoring 100% by
# construction, because every node contributes to the depth-1 bucket.
_MIN_PREFIX_SEGMENTS = 2


def _path_prefix(path: str, depth: int) -> str:
    parts = path.replace("\\", "/").strip("/").split("/")
    return "/".join(parts[:depth]) if parts else ""


def _dominant_prefix(nodes: list[dict]) -> tuple[str, int, int]:
    """Find the path prefix carrying the most files (weighted by file_count).
    Returns (prefix, covered_count, total_count). Empty prefix when no signal."""
    total = 0
    counts: dict[str, int] = {}
    for n in nodes:
        path = n.get("path") or ""
        fc = int(n.get("file_count", 0) or 0)
        if fc <= 0:
            fc = 1  # nodes without file_count still count once
        total += fc
        # Try multiple prefix depths and pick the best later. Dedupe prefixes
        # per node: short paths collapse depths to the same prefix (e.g. a
        # 2-segment path yields the same string at depth 3 and 2), so without
        # this guard a node's file_count would be added to one bucket 2-3×,
        # inflating `covered` above `total` (coverage_pct > 1, file_count >
        # total_file_count).
        seen: set[str] = set()
        for depth in (3, 2, 1):
            pref = _path_prefix(path, depth)
            if pref and pref not in seen:
                seen.add(pref)
                counts[pref] = counts.get(pref, 0) + fc
    if not counts or total == 0:
        return "", 0, total
    # Prefer the most-specific prefix at the highest count
    best_prefix = max(
        counts.items(),
        key=lambda kv: (kv[1], kv[0].count("/")),
    )
    return best_prefix[0], best_prefix[1], total


def _confidence_tier(coverage: float) -> str:
    if coverage >= _CONFIDENCE_HIGH:
        return "high"
    if coverage >= _CONFIDENCE_MEDIUM:
        return "medium"
    return "low"


def _placement_payload(status: str, placements: list[dict]) -> dict:
    return {
        "schema_version": _PLACEMENT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": status,
        "placements": placements,
    }


_ARCH_MAP_SUPPORTED_MAJOR = 2


def _schema_state(data: dict) -> str:
    """Classify an architecture map artifact.

    Returns ok | stale_schema | invalid_artifact | unsupported_schema.

    Four causes must never collapse into one behaviour, because the user's action
    differs in each: a previous-schema artifact must be regenerated, a broken one is
    not trustworthy at all, a future-schema one means the CLI is behind, and an
    up-to-date one is usable. An unknown version must never degrade silently
    (ADR 0009).
    """
    raw = data.get("schema_version")
    if not isinstance(raw, str):
        return "invalid_artifact"
    try:
        major = int(raw.split(".")[0])
    except (ValueError, IndexError):
        return "invalid_artifact"
    if major > _ARCH_MAP_SUPPORTED_MAJOR:
        return "unsupported_schema"
    if not isinstance(data.get("nodes"), list):
        return "invalid_artifact"
    # Structural claims need a topology built over the population, which is exactly
    # what the schema version tells us — not how much content was read.
    if not has_population_semantics(raw):
        return "stale_schema"
    return "ok"


def _universal_prefix(nodes: list[dict]) -> str:
    """Longest path prefix shared by EVERY node in the map ("" when none).

    Used only to detect a prefix that discriminates nothing: when the map holds MORE
    THAN ONE category and a category's dominant prefix equals this, it cannot answer
    "where does a Service live?" because it is where *everything* lives.

    The multi-category condition matters. In a single-category map every node is a
    Service by definition, so the shared prefix IS the answer — discarding it there
    would suppress the correct observation "services live in src/services".

    Structural test, never a comparison against the project directory name: a
    homonymous inner directory would false-positive, and the checkout folder name is
    not architectural information.
    """
    paths = [
        _path_prefix(n.get("path") or "", 99).split("/")
        for n in nodes
        if isinstance(n, dict) and n.get("path")
    ]
    if not paths:
        return ""
    common: list[str] = []
    for segments in zip(*paths):
        if len(set(segments)) != 1:
            break
        common.append(segments[0])
    return "/".join(common)


def _explain_placement_omission(placement: dict) -> None:
    """Explain an omitted Code Placement section instead of letting it vanish.

    A section that simply disappears from CLAUDE.md reads as a bug. The two causes
    need different messages because the user's action differs: a previous-schema
    artifact must be regenerated, while a genuinely small sample is not an error at
    all. Informational only — nothing is corrected and the artifact is unchanged.
    """
    messages = {
        "stale_schema": (
            "  ⚠ Code Placement omitido — o architecture map precisa ser regenerado.\n"
            "    Rode: maes build-arch-map"
        ),
        "invalid_artifact": (
            "  ⚠ Code Placement omitido — architecture_map.json inválido ou "
            "corrompido.\n"
            "    Regenere: maes build-arch-map"
        ),
        "unsupported_schema": (
            "  ⚠ Code Placement omitido — o architecture map foi gerado por uma "
            "versão mais nova do MAES.\n"
            "    Atualize o CLI (pip install -U maes)."
        ),
        "no_observed_convention": (
            "  ⓘ Code Placement omitido — nenhuma convenção de placement observável.\n"
            "    Não é erro: os módulos não seguem um prefixo que distinga categoria."
        ),
    }
    message = messages.get(str(placement.get("status")))
    if message:
        print(message, file=sys.stderr)


def _build_placement_map(arch_map_path: Path) -> dict | None:
    """Build placement-map.json payload from architecture_map.json on disk.

    Returns None if architecture_map.json is unreadable.

    Statuses, each answering a different question (ADR 0009):
      generated              — a convention was observed
      no_observed_convention — observed, and there is none
      stale_schema           — topology built on a sample, not the population
      invalid_artifact       — unreadable/broken structure
      unsupported_schema     — produced by a newer MAES; update the CLI
      empty                  — there was nothing to classify

    The evidence gate is STRUCTURAL, not content-based. A placement conclusion is
    built from node paths, types and file counts — all population-derived — so
    `sampling_ratio` (how much text was read) is the wrong evidence for it. That
    belongs to content-derived claims like entry_points. Gating placement on it
    suppressed valid observations in the field: a 941-file project reads ~3% of its
    content within the budget, yet its topology is complete.
    """
    data = _load_json(arch_map_path)
    if not isinstance(data, dict):
        return None

    # Fail-closed on artifact state: old, broken and future-schema are distinct, and
    # none of them supports a structural claim.
    state = _schema_state(data)
    if state != "ok":
        return _placement_payload(state, [])

    nodes = data.get("nodes") or []
    by_type: dict[str, list[dict]] = {}
    for n in nodes:
        if not isinstance(n, dict):
            continue
        ntype = n.get("type") or "Unknown"
        by_type.setdefault(ntype, []).append(n)

    # Only meaningful when there is something to discriminate between.
    universal = _universal_prefix(nodes) if len(by_type) > 1 else ""

    placements: list[dict] = []
    for category in sorted(by_type):
        group = by_type[category]
        prefix, covered, total = _dominant_prefix(group)
        if not prefix or total == 0:
            continue
        # Non-discriminating prefix → zero information, not a weak signal.
        if universal and prefix == universal:
            continue
        coverage = covered / total
        confidence = _confidence_tier(coverage)
        # A single-segment prefix is never a strong convention, whatever its
        # coverage: every node sharing one root yields 100% by construction.
        if prefix.count("/") + 1 < _MIN_PREFIX_SEGMENTS:
            confidence = "low"
        placements.append({
            "category": category,
            "path": prefix,
            "confidence": confidence,
            "coverage_pct": round(coverage, 3),
            "file_count": covered,
            "total_file_count": total,
        })

    if not placements:
        # There WERE categories but no prefix discriminated: a legitimate and
        # informative observation ("this project has no detectable placement
        # convention"), distinct from having no data.
        status = "no_observed_convention" if by_type else "empty"
        return _placement_payload(status, [])

    return _placement_payload("generated", placements)


# ─── emit() — write synthesis/ (canonical + compat artifacts) ─────────────────

def emit(maes_dir: Path, state: State) -> None:
    """Write synthesis files. Canonical: modules.json, domains.json, assertions.json.
    Compatibility artifacts: conflicts.json, guards.json (derived views for legacy consumers).
    """
    synth_dir = maes_dir / "synthesis"
    synth_dir.mkdir(parents=True, exist_ok=True)

    def _write(name: str, data: object) -> None:
        (synth_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Canonical state — 3 primary files
    _write("modules.json", [m.to_dict() for m in state.modules])
    _write("domains.json", [d.to_dict() for d in state.domains])
    _write("assertions.json", [a.to_dict() for a in state.assertions])

    # Derived: conflicts (for maes validate and explain compat)
    conflicts = detect_conflicts(state.assertions)
    _write("conflicts.json", [c.to_dict() for c in conflicts])

    # Derived: guards (for mcp_server and explain compat)
    _write("guards.json", derive_guards(state.assertions))

    # Derived: hot context (for mcp_server compat — replaces anti-hallucination.json)
    _write("anti-hallucination.json", derive_hot_context(state.assertions))

    # Runtime context (I4 — canonical commands + staleness warning)
    if not state.runtime.is_empty() or state.runtime.last_verified:
        _write("runtime.json", state.runtime.to_dict())

    # Architecture map (pass-through from inferred/ to synthesis/)
    if state.architecture_map:
        arch_map_src = maes_dir / "context" / "inferred" / _ARCH_MAP_FILENAME
        if arch_map_src.exists():
            (synth_dir / _ARCH_MAP_FILENAME).write_bytes(arch_map_src.read_bytes())
            # Derived: impact graph (C1 — path-resolvable dependency index)
            impact = _build_impact_graph(arch_map_src)
            if impact is not None:
                _write("impact-graph.json", impact)
            # Derived: placement map (I5/I6 — convention discovery)
            placement = _build_placement_map(arch_map_src)
            if placement is not None:
                _write("placement-map.json", placement)
                _explain_placement_omission(placement)
