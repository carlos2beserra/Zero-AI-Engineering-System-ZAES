#!/usr/bin/env python3
"""
MAES Governance Report — Dashboard de governança do contexto.

Consolida staleness, tamanho de arquivos e cobertura por squad em um
único relatório de saúde do contexto MAES (.maes/context/human/).

Uso:
    python scripts/governance-report.py                    # markdown para stdout
    python scripts/governance-report.py --output json      # JSON para integração
    python scripts/governance-report.py --archive-decisions # move decisões antigas

Variáveis de ambiente (para GitHub Actions):
    GITHUB_STEP_SUMMARY — se definida, escreve resumo no step summary
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MAES_ROOT   = Path(__file__).parent.parent
CONTEXT_DIR = MAES_ROOT / ".maes" / "context" / "human"

# Thresholds de staleness (dias)
FRESH_MAX = 14
AGING_MAX = 30
STALE_MAX = 60

# Thresholds de tamanho (tokens estimados)
TOO_SMALL = 200
TOO_LARGE = 3000

# Arquivos de contexto obrigatórios por squad
SQUAD_REQUIRED = ["decisions.md", "business-rules.md", "compliance.md"]

# Padrões que indicam template não preenchido
TEMPLATE_PATTERNS = re.compile(
    r"\[[\w\s]+\]",
    re.IGNORECASE,
)


# ─── Coleta de dados ──────────────────────────────────────────────────────────

def git_last_modified(file_path: Path) -> datetime | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", str(file_path)],
            capture_output=True, text=True, cwd=MAES_ROOT
        )
        raw = result.stdout.strip()
        if not raw:
            return None
        return datetime.fromisoformat(raw)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def classify_staleness(age_days: int) -> str:
    if age_days <= FRESH_MAX:
        return "fresh"
    if age_days <= AGING_MAX:
        return "aging"
    if age_days <= STALE_MAX:
        return "stale"
    return "critical"


def staleness_icon(staleness: str) -> str:
    return {"fresh": "✅", "aging": "🟡", "stale": "🟠", "critical": "🔴"}.get(staleness, "❓")


def estimate_tokens(content: str) -> int:
    return max(1, len(content) // 4)


def fill_rate(content: str) -> float:
    lines      = content.splitlines()
    total      = max(1, len(lines))
    unfilled   = sum(1 for line in lines if TEMPLATE_PATTERNS.search(line))
    return round(1 - unfilled / total, 2)


def analyze_file(file_path: Path) -> dict:
    content       = file_path.read_text(encoding="utf-8", errors="replace")
    last_modified = git_last_modified(file_path)
    now           = datetime.now(timezone.utc)
    rel_path      = file_path.relative_to(MAES_ROOT).as_posix()

    if last_modified:
        age_days = (now - last_modified).days
        date_str = last_modified.strftime("%Y-%m-%d")
    else:
        age_days = 0
        date_str = "desconhecido"

    tokens    = estimate_tokens(content)
    staleness = classify_staleness(age_days)
    rate      = fill_rate(content)

    issues = []
    if staleness in ("stale", "critical"):
        issues.append(f"desatualizado ({age_days}d sem modificação)")
    if tokens < TOO_SMALL:
        issues.append(f"muito pequeno (~{tokens} tokens — template não preenchido?)")
    if tokens > TOO_LARGE:
        issues.append(f"muito grande (~{tokens} tokens — considere arquivar conteúdo antigo)")
    if rate < 0.7:
        issues.append(f"fill rate baixo ({rate:.0%} — muitos campos de template)")

    return {
        "file":          rel_path,
        "last_modified": date_str,
        "age_days":      age_days,
        "staleness":     staleness,
        "tokens":        tokens,
        "fill_rate":     rate,
        "issues":        issues,
    }


def scan_context(directory: Path) -> list[dict]:
    return [analyze_file(f) for f in sorted(directory.rglob("*.md"))]


def squad_coverage() -> dict:
    squads     = sorted(CONTEXT_DIR.glob("squad-*/"))
    if not squads:
        return {}

    coverage = {}
    for squad_dir in squads:
        name    = squad_dir.name
        present = [f.name for f in squad_dir.glob("*.md")]
        missing = [r for r in SQUAD_REQUIRED if r not in present]
        coverage[name] = {
            "files":   present,
            "missing": missing,
            "ok":      len(missing) == 0,
        }
    return coverage


def count_decisions(decisions_path: Path) -> int:
    if not decisions_path.exists():
        return 0
    content = decisions_path.read_text(encoding="utf-8")
    return len(re.findall(r"^###\s+\[DEC-\d+\]", content, re.MULTILINE))


# ─── Archiving ────────────────────────────────────────────────────────────────

def archive_old_decisions(decisions_path: Path) -> int:
    if not decisions_path.exists():
        return 0

    content = decisions_path.read_text(encoding="utf-8")

    # Divide o conteúdo em blocos por marcador DEC — evita quantificador relutante
    raw_blocks       = re.split(r"(?=###\s+\[DEC-\d+\])", content)
    blocks           = [b for b in raw_blocks if re.match(r"###\s+\[DEC-\d+\]", b)]
    replaced_pattern = re.compile(r"\*\*Status:\*\*\s+Substitu", re.IGNORECASE)
    to_keep   = []
    to_archive = []

    for block in blocks:
        if replaced_pattern.search(block):
            to_archive.append(block)
        else:
            to_keep.append(block)

    if not to_archive:
        print("Nenhuma decisão substituída encontrada para arquivar.", file=sys.stderr)
        return 0

    archive_path = decisions_path.parent / "decisions-archive.md"

    archive_header = (
        "# Decisions Archive\n\n"
        "> Decisões substituídas, arquivadas automaticamente por "
        "`governance-report.py --archive-decisions`.\n\n---\n\n"
    )

    # Prepara o novo conteúdo de decisions.md antes de qualquer mutação
    header_end = content.find("### [DEC-")
    header     = content[:header_end] if header_end != -1 else ""
    new_content = header + "\n".join(to_keep)

    try:
        # Passo 1: append ao arquivo de arquivo
        # Se falhar aqui, decisions.md permanece intacto — sem perda de dados
        if not archive_path.exists():
            archive_path.write_text(archive_header, encoding="utf-8")
        with archive_path.open("a", encoding="utf-8") as f:
            for block in to_archive:
                f.write(block.strip() + "\n\n---\n\n")

        # Passo 2: reescreve decisions.md via arquivo temporário + rename atômico
        # Se o write falhar, decisions.md permanece intacto (tmp é descartado)
        # Se o rename falhar, decisions.md permanece intacto (tmp é limpo)
        tmp_path = decisions_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(new_content, encoding="utf-8")
            tmp_path.replace(decisions_path)
        except Exception:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    except Exception as exc:
        print(f"Erro ao arquivar decisões: {exc}", file=sys.stderr)
        raise

    print(
        f"{len(to_archive)} decisão(ões) arquivada(s) em {archive_path.name}.",
        file=sys.stderr,
    )
    return len(to_archive)


# ─── Formatação de relatório ──────────────────────────────────────────────────

def _health_icon(stale_count: int, issues_count: int, total: int) -> str:
    if stale_count == 0 and issues_count == 0:
        return "✅"
    if stale_count > total * 0.3:
        return "🔴"
    return "🟡"


def _format_health_section(
    by_staleness: dict, total: int, issues_count: int, decisions_count: int
) -> list[str]:
    stale_count = len(by_staleness["stale"]) + len(by_staleness["critical"])
    icon = _health_icon(stale_count, issues_count, total)
    return [
        f"## {icon} Saúde Geral do Contexto",
        "",
        "| Métrica | Valor |",
        "|---|:---:|",
        f"| Arquivos analisados | {total} |",
        f"| Arquivos ✅ fresh | {len(by_staleness['fresh'])} |",
        f"| Arquivos 🟡 aging | {len(by_staleness['aging'])} |",
        f"| Arquivos 🟠 stale | {len(by_staleness['stale'])} |",
        f"| Arquivos 🔴 critical | {len(by_staleness['critical'])} |",
        f"| Total de issues | {issues_count} |",
        f"| Decisões registradas | {decisions_count} |",
        "",
    ]


def _format_files_section(files: list[dict]) -> list[str]:
    lines = [
        "## Arquivos de Contexto",
        "",
        "| Arquivo | Modificado | Idade | Status | Tokens | Fill |",
        "|---|---|:---:|:---:|:---:|:---:|",
    ]
    for f in files:
        icon  = staleness_icon(f["staleness"])
        fill  = f"{f['fill_rate']:.0%}"
        alert = " ⚠️" if f["issues"] else ""
        lines.append(
            f"| `{f['file']}`{alert} "
            f"| {f['last_modified']} "
            f"| {f['age_days']}d "
            f"| {icon} {f['staleness']} "
            f"| ~{f['tokens']} "
            f"| {fill} |"
        )
    return lines


def _format_issues_section(files: list[dict]) -> list[str]:
    files_with_issues = [f for f in files if f["issues"]]
    if not files_with_issues:
        return []
    lines = ["", "## Issues Detectadas", ""]
    for f in files_with_issues:
        for issue in f["issues"]:
            lines.append(f"- `{f['file']}`: {issue}")
    return lines


def _format_squads_section(squads: dict) -> list[str]:
    if not squads:
        return []
    lines = ["", "## Cobertura por Squad", ""]
    for squad, data in squads.items():
        icon = "✅" if data["ok"] else "⚠️"
        lines.append(f"### {icon} {squad}")
        lines.append(f"Arquivos: {', '.join(data['files']) or 'nenhum'}")
        if data["missing"]:
            lines.append(f"Faltando: {', '.join(data['missing'])}")
        lines.append("")
    return lines


def format_markdown(files: list[dict], squads: dict, decisions_count: int) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    by_staleness = {s: [f for f in files if f["staleness"] == s]
                    for s in ("fresh", "aging", "stale", "critical")}
    total        = len(files)
    issues_count = sum(len(f["issues"]) for f in files)

    lines = [
        "# MAES Governance Report",
        f"> Gerado em {now}",
        "",
    ]
    lines += _format_health_section(by_staleness, total, issues_count, decisions_count)
    lines += _format_files_section(files)
    lines += _format_issues_section(files)
    lines += _format_squads_section(squads)

    if decisions_count > 10:
        lines += [
            "",
            f"> ⚠️ `decisions.md` tem {decisions_count} decisões. "
            "Considere arquivar as antigas: "
            "`python scripts/governance-report.py --archive-decisions`",
        ]

    lines += [
        "",
        "---",
        "_Gerado pelo [MAES Governance Report](scripts/governance-report.py)_",
    ]
    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="MAES Governance Report — dashboard de governança do contexto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output",
        default="markdown",
        choices=["markdown", "json"],
        help="Formato de saída (padrão: markdown)",
    )
    parser.add_argument(
        "--archive-decisions",
        action="store_true",
        help="Move decisões com status 'Substituído' para decisions-archive.md",
    )
    args = parser.parse_args()

    if args.archive_decisions:
        decisions_path = CONTEXT_DIR / "decisions.md"
        archive_old_decisions(decisions_path)
        return

    files           = scan_context(CONTEXT_DIR)
    squads          = squad_coverage()
    decisions_path  = CONTEXT_DIR / "decisions.md"
    decisions_count = count_decisions(decisions_path)

    if args.output == "json":
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "files":        files,
            "squads":       squads,
            "decisions":    decisions_count,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        report = format_markdown(files, squads, decisions_count)
        print(report)

        # Escreve no GitHub Step Summary se disponível
        import os
        step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if step_summary:
            with open(step_summary, "a", encoding="utf-8") as f:
                f.write(report)

    # Exit code 1 se há arquivos critical
    has_critical = any(f["staleness"] == "critical" for f in files)
    sys.exit(1 if has_critical else 0)


if __name__ == "__main__":
    main()
