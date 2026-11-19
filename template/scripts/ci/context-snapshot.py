#!/usr/bin/env python3
"""
MAES Context Snapshot — Registra métricas de síntese em cada release.

Lê .maes/synthesis/ (gerado por maes sync) e gera um manifest com contagens
de assertions, guards e conflitos. Publica métricas no GitHub Step Summary.

Uso:
    python scripts/ci/context-snapshot.py --tag v1.3.0
    python scripts/ci/context-snapshot.py --tag v1.3.0 --dry-run  # preview

Variáveis de ambiente:
    GITHUB_ACTOR         — autor do snapshot (fallback: git config user.name)
    GITHUB_STEP_SUMMARY  — se definida, publica métricas no step summary
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MAES_ROOT     = Path(__file__).parent.parent
SYNTHESIS_DIR = MAES_ROOT / ".maes" / "synthesis"


def git_actor() -> str:
    actor = os.environ.get("GITHUB_ACTOR", "").strip()
    if actor:
        return actor
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, cwd=MAES_ROOT
        )
        return result.stdout.strip() or "desconhecido"
    except (OSError, subprocess.SubprocessError):
        return "desconhecido"


def load_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def collect_metrics() -> dict:
    assertions = load_json(SYNTHESIS_DIR / "assertions.json")
    guards     = load_json(SYNTHESIS_DIR / "guards.json")
    conflicts  = load_json(SYNTHESIS_DIR / "conflicts.json")
    anti_hall  = load_json(SYNTHESIS_DIR / "anti-hallucination.json")

    assertions_list = assertions if isinstance(assertions, list) else []
    guards_list     = guards     if isinstance(guards,     list) else []
    conflicts_list  = conflicts  if isinstance(conflicts,  list) else []
    anti_hall_list  = anti_hall  if isinstance(anti_hall,  list) else []

    unresolved         = [c for c in conflicts_list if isinstance(c, dict) and c.get("status") == "UNRESOLVED"]
    enforcement_guards = [g for g in guards_list    if isinstance(g, dict) and g.get("type") == "enforcement"]
    contextual_guards  = [g for g in guards_list    if isinstance(g, dict) and g.get("type") == "contextual"]

    by_layer: dict[str, int] = {}
    for a in assertions_list:
        layer = str(a.get("layer", "?")) if isinstance(a, dict) else "?"
        by_layer[layer] = by_layer.get(layer, 0) + 1

    return {
        "assertions_total":     len(assertions_list),
        "assertions_by_layer":  by_layer,
        "guards_total":         len(guards_list),
        "guards_enforcement":   len(enforcement_guards),
        "guards_contextual":    len(contextual_guards),
        "conflicts_total":      len(conflicts_list),
        "conflicts_unresolved": len(unresolved),
        "hot_rules":            len(anti_hall_list),
    }


def create_manifest(tag: str) -> dict:
    return {
        "tag":        tag,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": git_actor(),
        "metrics":    collect_metrics(),
    }


def format_step_summary(manifest: dict) -> str:
    m   = manifest["metrics"]
    tag = manifest["tag"]
    lines = [
        f"### MAES Context Snapshot @ {tag}",
        "",
        "| Métrica | Valor |",
        "|---|:---:|",
        f"| Assertions totais | {m['assertions_total']} |",
        f"| Guards (enforcement) | {m['guards_enforcement']} |",
        f"| Guards (contextual) | {m['guards_contextual']} |",
        f"| Conflitos não resolvidos | {m['conflicts_unresolved']} |",
        f"| Hot rules | {m['hot_rules']} |",
    ]
    if m["conflicts_unresolved"] > 0:
        lines += [
            "",
            f"> ⚠️ {m['conflicts_unresolved']} conflito(s) não resolvido(s). "
            "Execute `maes validate` localmente.",
        ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MAES Context Snapshot — métricas de síntese por release",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--tag",     required=True,      help="Tag do release (ex: v1.3.0)")
    parser.add_argument("--dry-run", action="store_true", help="Mostra métricas sem salvar manifest")
    args = parser.parse_args()

    if not re.match(r"^v?\d+\.\d+", args.tag):
        print(f"Erro: tag inválida '{args.tag}'. Use formato semântico (ex: v1.3.0).", file=sys.stderr)
        sys.exit(1)

    if not SYNTHESIS_DIR.exists():
        print(
            f"Erro: {SYNTHESIS_DIR.relative_to(MAES_ROOT)} não encontrado. "
            "Execute `maes sync` antes de gerar o snapshot.",
            file=sys.stderr,
        )
        sys.exit(1)

    manifest = create_manifest(args.tag)
    m = manifest["metrics"]

    if not args.dry_run:
        manifest_path = SYNTHESIS_DIR / f"snapshot-{args.tag}.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Manifest salvo em: {manifest_path.relative_to(MAES_ROOT).as_posix()}")

    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"{mode}Snapshot {args.tag}")
    print(f"  Assertions: {m['assertions_total']}  ({m['conflicts_unresolved']} conflitos não resolvidos)")
    print(f"  Guards:     {m['guards_total']}  ({m['guards_enforcement']} enforcement, {m['guards_contextual']} contextual)")
    print(f"  Hot rules:  {m['hot_rules']}")

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as f:
            f.write(format_step_summary(manifest))

    if m["conflicts_unresolved"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
