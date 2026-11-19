#!/usr/bin/env python3
"""
MAES CLI — Context Infrastructure / Context Compiler

Commands:
    init        Scaffold .maes/ structure in a project
    doctor      System health check (Python, deps, synthesis state)
    sync        Run the compiler pipeline (7 stages) and generate adapters
    validate    Validate synthesis state (exit 1 if UNRESOLVED conflicts)
    explain     Audit any system decision (status|guard|conflict|context)
    build-arch-map  Build deterministic architecture map (Stage 1 → Stage 3 → Stage 2)
    agent       Manage optional agents from the catalogue (list|add|remove)
    version     Show CLI version and project version (upgrade status)
    upgrade     Migrate project .maes/ to current CLI version

Usage:
    maes init
    maes doctor [--project-dir PATH]
    maes sync [--project-dir PATH] [--verbose]
    maes validate [--project-dir PATH]
    maes explain status [--project-dir PATH]
    maes explain guard --path GLOB [--project-dir PATH]
    maes explain conflict --id CONFLICT-ID [--project-dir PATH]
    maes explain context --agent AGENT_ID [--task TASK] [--project-dir PATH]
    maes build-arch-map [--project-dir PATH]
    maes serve [--project-dir PATH]
    maes agent list [--project-dir PATH]
    maes agent add <id> [--skip-sync] [--project-dir PATH]
    maes agent remove <id> [--skip-sync] [--project-dir PATH]
    maes version [--project-dir PATH]
    maes upgrade [--dry-run] [--skip-sync] [--project-dir PATH]

Environment:
    O CLI MAES é 100% determinístico — não requer variáveis de ambiente de LLM.
    As variáveis ANTHROPIC_API_KEY, GITHUB_TOKEN, GEMINI_API_KEY são usadas
    exclusivamente pelos scripts de CI (scripts/ci/) que rodam em GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_MAES_DIR_NAME   = ".maes"
_CONFIG_FILE     = "config.yaml"
_ASSERTIONS_FILE = "assertions.json"
_CONFLICTS_FILE  = "conflicts.json"
_MSG_RUNNING_SYNC = "\nRunning maes sync..."

# Ensure UTF-8 output on Windows (cp1252 default breaks box-drawing chars)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─── Placeholder stripping (used by `maes sync --clean`) ─────────────────────

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


def _filter_ex_bullets(lines: list[str]) -> tuple[list[str], int]:
    filtered: list[str] = []
    count = 0
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("- ", "* ", "+ ")):
            claim = stripped[2:].strip()
            if _is_placeholder(claim):
                count += 1
                continue
        filtered.append(line)
    return filtered, count


def _collapse_blanks(lines: list[str], max_run: int = 2) -> list[str]:
    result: list[str] = []
    blank_run = 0
    for line in lines:
        if line.strip() == "":
            blank_run += 1
            if blank_run <= max_run:
                result.append(line)
        else:
            blank_run = 0
            result.append(line)
    return result


def _strip_placeholders(human_dir: Path) -> dict[str, int]:
    removed: dict[str, int] = {}
    for md_file in sorted(human_dir.glob("*.md")):
        try:
            lines = md_file.read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError:
            continue
        filtered, count = _filter_ex_bullets(lines)
        if count:
            md_file.write_text("".join(_collapse_blanks(filtered)), encoding="utf-8")
            removed[md_file.name] = count
    return removed


# ─── Find .maes/ directory ────────────────────────────────────────────────────

def _find_maes_dir(project_dir: str | None = None) -> Path:
    if project_dir:
        candidate = Path(project_dir) / _MAES_DIR_NAME
        if not candidate.exists():
            print(f"Error: {_MAES_DIR_NAME}/ not found at {candidate}", file=sys.stderr)
            print("Run `maes init` to initialize.", file=sys.stderr)
            sys.exit(1)
        return candidate

    # Walk up from cwd
    current = Path.cwd()
    for _ in range(10):
        candidate = current / _MAES_DIR_NAME
        if candidate.exists():
            return candidate
        if current.parent == current:
            break
        current = current.parent

    print(f"Error: {_MAES_DIR_NAME}/ not found in current directory or any parent.", file=sys.stderr)
    print("Run `maes init` to initialize.", file=sys.stderr)
    sys.exit(1)


# ─── sync command ─────────────────────────────────────────────────────────────

_ADAPTER_ROOT_PATHS: dict[str, list[str]] = {
    "claude": ["CLAUDE.md"],
    "cursor": [".cursor/"],
    "windsurf": [".windsurfrules"],
    "copilot": [".github/copilot-instructions.md"],
}

_GUARDS_FILE = "guards.json"
_GENERATED_GUARD_ID = "guard-maes-generated-files"
_GENERATED_GUARD_CLAIM = (
    "Arquivos em .maes/synthesis/, .maes/adapters/ e adapters raiz (CLAUDE.md, "
    ".cursor/, .windsurfrules, .github/copilot-instructions.md) são gerados por "
    "`maes sync` — nunca editar manualmente; edições são sobrescritas no próximo sync"
)


def _inject_generated_files_guard(synth_dir: Path, ides: list[str]) -> None:
    """Append a synthetic block-guard to guards.json for all MAES-generated files.

    Idempotent: removes the old guard before re-adding so re-running sync is safe.
    Deterministic: guard content depends only on the ides config list.
    """
    guards_path = synth_dir / _GUARDS_FILE
    try:
        guards: list[dict] = json.loads(guards_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        guards = []

    guards = [g for g in guards if g.get("id") != _GENERATED_GUARD_ID]

    paths: list[str] = [".maes/synthesis/", ".maes/adapters/"]
    for ide in ides:
        paths.extend(_ADAPTER_ROOT_PATHS.get(ide, []))

    guards.append({
        "id": _GENERATED_GUARD_ID,
        "claim": _GENERATED_GUARD_CLAIM,
        "paths": sorted(set(paths)),
        "policy": "block",
        "layer": 4,
        "source_file": "maes:sync",
        "checklist": [],
        "owner": "",
        "guard_type": "enforcement",
    })

    guards_path.write_text(json.dumps(guards, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean_human_placeholders(maes_dir: Path, verbose: bool) -> None:
    human_dir = maes_dir / "context" / "human"
    removed = _strip_placeholders(human_dir)
    if removed:
        total = sum(removed.values())
        print(f"  {total} entradas [ex:] removidas de {len(removed)} arquivo(s):")
        for fname, count in removed.items():
            print(f"    {fname}: {count} linha(s) removida(s)")
    elif verbose:
        print("  Nenhuma entrada [ex:] encontrada.")


def _run_sync(maes_dir: Path, verbose: bool = False, clean: bool = False) -> int:
    from .adapters import generate_adapters
    from .compiler import build, detect_conflicts, derive_guards, emit

    if clean:
        _clean_human_placeholders(maes_dir, verbose)

    config = _load_config(maes_dir)
    project_name = config.get("project", {}).get("name", maes_dir.parent.name)
    ides = config.get("adapters", ["claude", "cursor"])

    if verbose:
        print("Stages 1–6 — BUILD (merge + deduplicate)")
    state = build(maes_dir)

    if not state.assertions:
        print("⚠ No assertions found — generating agent stubs from agent YAMLs only.")
        print("  Populate `.maes/context/human/*.md` with project rules to enrich the synthesis.")

    # Derive on-demand projections for reporting
    conflicts = detect_conflicts(state.assertions)
    guards = derive_guards(state.assertions)
    unresolved = [c for c in conflicts if c.status == "UNRESOLVED"]

    if verbose:
        print(f"  {len(state.assertions)} assertions after dedup")
        print(f"  {len(conflicts)} conflicts detected ({len(unresolved)} unresolved)")
        print(f"  {len(guards)} guards derived")

    # Git-aware staleness enrichment (informational only — does not mutate State)
    from .staleness import compute_all as _compute_staleness
    from datetime import date as _date
    staleness_results = _compute_staleness(
        state.assertions, maes_dir.parent, _date.today().isoformat()
    )
    stale_critical = [a for a, score, _ in staleness_results if score >= 0.8 and a.layer <= 3]
    if verbose and stale_critical:
        print(f"  {len(stale_critical)} layer 1-3 assertions stale (score ≥ 0.8)")

    # Write staleness.json (informational — not used by validate())
    synth_dir = maes_dir / "synthesis"
    synth_dir.mkdir(parents=True, exist_ok=True)
    staleness_data = {
        a.id: {"score": score, "last_verified": a.last_verified, "owner": a.owner, "reasons": reasons}
        for a, score, reasons in staleness_results
    }
    (synth_dir / "staleness.json").write_text(
        json.dumps(staleness_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Write canonical synthesis/ files + compat artifacts
    emit(maes_dir, state)
    _inject_generated_files_guard(synth_dir, ides)

    if verbose:
        print("Stage 7 — ADAPTERS")

    adapter_files = generate_adapters(maes_dir, state, project_name, ides)

    # Regenerate the adapter staging dir from scratch so files for agents that
    # no longer exist drop out. .maes/adapters/ is 100% MAES-generated (gitignored)
    # — clearing it lets _copy_adapters_to_root()'s _sync_managed_directory()
    # propagate the removal to the root output dirs on this same sync.
    import shutil
    adapters_staging = maes_dir / "adapters"
    if adapters_staging.exists():
        shutil.rmtree(adapters_staging)

    for rel_path, content in adapter_files.items():
        dest = maes_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    if verbose:
        print(f"  {len(adapter_files)} adapter files written")

    from .quickstart_cmd import _copy_adapters_to_root
    project_dir = maes_dir.parent
    root_copied = _copy_adapters_to_root(maes_dir, project_dir)

    print("\n✓ Sync complete")
    print(f"  Assertions: {len(state.assertions)}")
    print(f"  Guards:     {len(guards)}")
    print(f"  Conflicts:  {len(conflicts)} ({len(unresolved)} unresolved)")
    print(f"  Adapters:   {', '.join(ides)}")
    adapter_names = [p for p in (root_copied or []) if not p.startswith((".github/", "scripts/"))]
    if adapter_names:
        print(f"  Root:       {', '.join(adapter_names)}")

    if stale_critical:
        print(f"\n\033[33m⚠ {len(stale_critical)} assertion(s) stale (score ≥0.8) in layers 1-3 "
              "— `maes validate` will fail\033[0m")
        print("  Run `maes doctor` for details.")

    if unresolved:
        print(f"\n\033[31m✗ {len(unresolved)} UNRESOLVED conflict(s) — "
              "run `maes explain status` to review\033[0m")
        print("  Resolve before deploying. CI will fail on UNRESOLVED conflicts.")
        return 1

    return 0


# ─── validate command ─────────────────────────────────────────────────────────

def _run_validate(maes_dir: Path) -> int:
    from datetime import date
    from .compiler import staleness_score as _stale_score
    from .models import Assertion

    synth_dir = maes_dir / "synthesis"

    if not (synth_dir / _ASSERTIONS_FILE).exists():
        print("✗ Synthesis not found. Run `maes sync` first.", file=sys.stderr)
        return 1

    try:
        conflicts = json.loads((synth_dir / _CONFLICTS_FILE).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        conflicts = []

    unresolved = [c for c in conflicts if c.get("status") == "UNRESOLVED"]

    if unresolved:
        print(f"✗ {len(unresolved)} UNRESOLVED conflict(s):", file=sys.stderr)
        for c in unresolved:
            print(f"  {c['id']}: {c['reason'][:80]}", file=sys.stderr)
        print("\nRun `maes explain conflict --id <ID>` for details.", file=sys.stderr)
        return 1

    # Staleness — severity-tier-aware (TTL-based, no git calls needed)
    # Layers 1-3 (compliance/security/contracts): hard fail
    # Layers 4-5 (architecture/domain): warning only
    # Layers 6-7 (engineering/inferred): advisory, not enforced
    _STALENESS_POLICY = {1: "fail", 2: "fail", 3: "fail",
                         4: "warn", 5: "warn", 6: "advisory", 7: "advisory"}
    _STALE_THRESHOLD = 0.8

    ownership = _load_ownership(maes_dir)
    teams: dict = ownership.get("teams", {})

    try:
        raw_assertions = json.loads((synth_dir / _ASSERTIONS_FILE).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raw_assertions = []

    today = date.today()

    # Reconstruct lightweight Assertion objects for staleness scoring
    def _make_assertion(d: dict) -> Assertion:
        return Assertion(
            id=d.get("id", ""),
            claim=d.get("claim", ""),
            type=d.get("type", "PATTERN"),
            layer=d.get("layer", 7),
            subject=d.get("subject"),
            paths=d.get("paths", []),
            confidence=d.get("confidence", "assumed"),
            source=d.get("source", ""),
            ttl=d.get("ttl", "730d"),
            last_verified=d.get("last_verified", ""),
            owner=d.get("owner", ""),
            merge_history=d.get("merge_history", []),
            code_examples=d.get("code_examples", []),
        )

    stale_fail: list[dict] = []
    stale_warn: list[dict] = []
    for d in raw_assertions:
        a = _make_assertion(d)
        score = _stale_score(a, today)
        if score < _STALE_THRESHOLD:
            continue
        policy = _STALENESS_POLICY.get(a.layer, "advisory")
        enriched = {**d, "_stale_score": score}
        if policy == "fail":
            stale_fail.append(enriched)
        elif policy == "warn":
            stale_warn.append(enriched)

    if stale_fail:
        print(f"✗ CRITICAL: {len(stale_fail)} assertion(s) stale in layers 1-3 "
              "— CI blocked", file=sys.stderr)
        _print_stale_by_owner(stale_fail, teams, stream=sys.stderr)
        return 1

    if stale_warn:
        print(f"⚠ WARN: {len(stale_warn)} assertion(s) stale in layers 4-5 "
              "— review recommended")
        _print_stale_by_owner(stale_warn, teams, stream=sys.stdout)

    print("✓ Validation passed")
    print(f"  {len(raw_assertions)} assertions, 0 unresolved conflicts")
    return 0


def _load_ownership(maes_dir: Path) -> dict:
    ownership_file = maes_dir / "OWNERSHIP.yaml"
    if not ownership_file.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(ownership_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _resolve_contact(owner: str, team_info: dict) -> str:
    contact = team_info.get("contact", "")
    slack   = team_info.get("slack", "")
    if contact:
        return f"  → Contact: {contact}" + (f"  ({slack})" if slack else "")
    if slack:
        return f"  → Contact: {slack}"
    return f"  → Contact: {owner} (add to OWNERSHIP.yaml teams section)"


def _print_stale_by_owner(
    assertions: list[dict],
    teams: dict,
    stream,
) -> None:
    """Group stale assertions by owner, resolve contacts, print actionable output."""
    from collections import defaultdict
    by_owner: dict[str, list[dict]] = defaultdict(list)
    for a in assertions:
        by_owner[a.get("owner", "") or "unowned"].append(a)

    for owner, group in sorted(by_owner.items()):
        contact_str = _resolve_contact(owner, teams.get(owner, {}))

        print(f"\n  [{owner}] — {len(group)} assertion(s)", file=stream)
        print(contact_str, file=stream)
        for a in group[:4]:
            score = a.get("_stale_score", a.get("staleness_score", 0))
            src = a.get("source", "") if isinstance(a.get("source"), str) else ""
            print(f"    · {a.get('claim', '')[:72]}", file=stream)
            print(f"      score {score:.2f} · ttl_check"
                  + (f" · {src}" if src else ""), file=stream)

        # Hint: which file to update
        files = {a.get("source", "") for a in group
                 if isinstance(a.get("source"), str) and a.get("source")}
        files.discard("")
        if files:
            print(f"  → Update: {', '.join(sorted(files))} then run `maes sync`",
                  file=stream)


# ─── doctor command ───────────────────────────────────────────────────────────

def _doctor_system(ok, warn, err) -> None:
    import importlib
    import os
    v = sys.version_info
    if v >= (3, 11):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        err(f"Python {v.major}.{v.minor}.{v.micro} — requires 3.11+")

    for pkg, install in [("anthropic", "anthropic"), ("yaml", "pyyaml")]:
        try:
            ver = getattr(importlib.import_module(pkg), "__version__", "?")
            ok(f"{install} {ver}")
        except ImportError:
            err(f"{install} not installed — pip install {install}")

    try:
        importlib.import_module("mcp")
        ok("mcp installed (maes serve available)")
    except ImportError:
        warn("mcp not installed — maes serve unavailable (pip install mcp)")

    from .llm import PROVIDER_DEFAULTS, _DETECT_ORDER
    provider_found = False
    for p in _DETECT_ORDER:
        key = os.environ.get(PROVIDER_DEFAULTS[p]["env"], "")
        if key:
            masked = key[:8] + "..." + key[-4:]
            ok(f"{PROVIDER_DEFAULTS[p]['env']} set ({masked}) — provider: {p}")
            provider_found = True
    if not provider_found:
        keys = ", ".join(PROVIDER_DEFAULTS[p]["env"] for p in _DETECT_ORDER)
        warn(f"No LLM provider configured — set one of: {keys}")


def _locate_maes_dir(project_dir: Path | None) -> "Path | None":
    if project_dir:
        c = project_dir / _MAES_DIR_NAME
        return c if c.exists() else None
    cur = Path.cwd()
    for _ in range(10):
        c = cur / _MAES_DIR_NAME
        if c.exists():
            return c
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _check_maes_contents(maes_dir: Path, ok, warn, err) -> None:
    if (maes_dir / _CONFIG_FILE).exists():
        ok("config.yaml present")
    else:
        err("config.yaml missing — run `maes init`")

    human_dir = maes_dir / "context" / "human"
    if not human_dir.exists():
        warn("context/human/ not found — run `maes init`")
        return
    filled = [f for f in human_dir.glob("*.md") if f.stat().st_size > 100]
    if filled:
        ok(f"context/human/ populated ({len(filled)} files)")
    else:
        warn("context/human/ files appear empty — populate them manually with your project rules")


def _doctor_find_maes(project_dir: Path | None, ok, warn, err) -> "Path | None":
    maes_dir = _locate_maes_dir(project_dir)
    if maes_dir is None:
        err(f"{_MAES_DIR_NAME}/ not found — run `maes init` to initialize")
        return None
    ok(f"{_MAES_DIR_NAME}/ initialized  ({maes_dir.parent})")
    _check_maes_contents(maes_dir, ok, warn, err)
    return maes_dir


def _report_staleness(assertions: list, ok, warn, err) -> None:
    from datetime import date
    from .compiler import staleness_score as _stale_score
    from .models import Assertion

    today = date.today()

    def _score(d: dict) -> float:
        a = Assertion(
            id=d.get("id", ""), claim=d.get("claim", ""),
            type=d.get("type", "PATTERN"), layer=d.get("layer", 7),
            subject=d.get("subject"), paths=d.get("paths", []),
            confidence=d.get("confidence", "assumed"), source=d.get("source", ""),
            ttl=d.get("ttl", "730d"), last_verified=d.get("last_verified", ""),
            owner=d.get("owner", ""),
        )
        return _stale_score(a, today)

    stale_crit = [a for a in assertions if _score(a) >= 0.8]
    stale_warn = [a for a in assertions if 0.3 <= _score(a) < 0.8]
    if stale_crit:
        err(f"{len(stale_crit)} assertion(s) critically stale (staleness ≥ 0.8) — CI will block")
        for a in stale_crit[:3]:
            print(f"       [{a.get('layer', '?')}] {a.get('claim', '')[:70]}")
    elif stale_warn:
        warn(f"{len(stale_warn)} assertion(s) aging")
    else:
        ok("all assertions fresh")


def _report_hot_tokens(anti_h: list, ok, warn, err) -> None:
    hot_tokens = sum(max(1, len(r.get("claim", "")) // 4) for r in anti_h)
    if hot_tokens > 800:
        err(f"hot context {hot_tokens}t exceeds 800t hard cap — trim compliance/security assertions")
    elif hot_tokens > 640:
        warn(f"hot context {hot_tokens}t / 800t ({hot_tokens * 100 // 800}% — near limit)")
    else:
        ok(f"hot context {hot_tokens}t / 800t ({hot_tokens * 100 // 800}%)")


def _report_sync_date(assertions_path: Path, ok, warn) -> None:
    import os as _os
    from datetime import date, datetime
    try:
        mtime = _os.path.getmtime(assertions_path)
        sync_date = datetime.fromtimestamp(mtime).date()
        days_ago = (date.today() - sync_date).days
        label = "today" if days_ago == 0 else f"{days_ago}d ago"
        if days_ago > 30:
            warn(f"last sync: {sync_date} ({label}) — consider re-running `maes sync`")
        else:
            ok(f"last sync: {sync_date} ({label})")
    except OSError:
        pass


def _doctor_synthesis(synth_dir: Path, assertions_path: Path, ok, warn, err) -> bool:
    if not assertions_path.exists():
        err("synthesis/ not found — run `maes sync`")
        return False

    def _lj(name: str) -> list:
        p = synth_dir / name
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    assertions = _lj(_ASSERTIONS_FILE)
    guards     = _lj(_GUARDS_FILE)
    conflicts  = _lj(_CONFLICTS_FILE)
    anti_h     = _lj("anti-hallucination.json")
    unresolved = [c for c in conflicts if c.get("status") == "UNRESOLVED"]

    ok(f"{len(assertions)} assertions  ·  {len(guards)} guards")
    _report_staleness(assertions, ok, warn, err)

    if unresolved:
        err(f"{len(unresolved)} UNRESOLVED conflict(s) — run `maes explain conflict --id …`")
    else:
        ok("no unresolved conflicts")

    _report_hot_tokens(anti_h, ok, warn, err)
    _report_sync_date(assertions_path, ok, warn)
    return True


def _doctor_adapters(adapters_dir: Path, ok, warn) -> None:
    if adapters_dir.exists():
        names = sorted(d.name for d in adapters_dir.iterdir() if d.is_dir())
        ok(f"{', '.join(names)}")
    else:
        warn("adapters/ not found — run `maes sync`")


def _run_doctor(project_dir: Path | None = None) -> int:
    _G = "\033[32m"   # green
    _Y = "\033[33m"   # yellow
    _R = "\033[31m"   # red
    _B = "\033[1m"    # bold
    _X = "\033[0m"    # reset

    errors: list[str] = []

    def _ok(msg: str)  -> None: print(f"  {_G}✔{_X} {msg}")
    def _warn(msg: str)-> None: print(f"  {_Y}⚠{_X} {msg}")
    def _err(msg: str) -> None:
        errors.append(msg)
        print(f"  {_R}✗{_X} {msg}")

    print(f"\n{_B}MAES Doctor{_X}\n")

    print(f"{_B}System{_X}")
    _doctor_system(_ok, _warn, _err)

    print(f"\n{_B}Project{_X}")
    maes_dir = _doctor_find_maes(project_dir, _ok, _warn, _err)
    if maes_dir is None:
        print()
        return 1

    print(f"\n{_B}Synthesis{_X}")
    synth_dir = maes_dir / "synthesis"
    if not _doctor_synthesis(synth_dir, synth_dir / _ASSERTIONS_FILE, _ok, _warn, _err):
        print()
        return 1

    print(f"\n{_B}Adapters{_X}")
    _doctor_adapters(maes_dir / "adapters", _ok, _warn)

    print(f"\n{_B}Agents{_X}")
    from .doctor_cmd import _check_agent_scope_paths, _check_architecture_map
    _check_agent_scope_paths(maes_dir / "agents", _ok, _warn)

    print(f"\n{_B}Inferred{_X}")
    _check_architecture_map(maes_dir, _ok)

    print()
    if errors:
        print(f"{_R}✗ {len(errors)} issue(s) found.{_X}  Run `maes sync` to recompile.\n")
        return 1
    print(f"{_G}✔ All checks passed.{_X}\n")
    return 0


# ─── Config loading ───────────────────────────────────────────────────────────

def _load_config(maes_dir: Path) -> dict:
    config_file = maes_dir / _CONFIG_FILE
    if not config_file.exists():
        return {}
    try:
        import yaml
        return yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


# ─── Argument parser ──────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maes",
        description="MAES — Context Infrastructure / Context Compiler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    from . import __version__
    parser.add_argument(
        "--version", "-V", action="version", version=f"MAES CLI {__version__}",
        help="Show the MAES CLI version and exit",
    )
    parser.add_argument(
        "--project-dir", "-p", default=None,
        help="Project directory containing .maes/ (default: auto-detect from cwd)"
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # init
    sub.add_parser("init", help="Scaffold .maes/ structure")

    # sync
    sync_p = sub.add_parser("sync", help="Compile context and generate adapters")
    sync_p.add_argument("--verbose", "-v", action="store_true")
    sync_p.add_argument("--clean", action="store_true",
                        help="Strip [ex:] template placeholders from human/*.md files")

    # validate
    sub.add_parser("validate", help="Validate synthesis (exit 1 on errors)")

    # explain
    exp_p = sub.add_parser("explain", help="Audit system decisions")
    exp_sub = exp_p.add_subparsers(dest="explain_cmd", metavar="WHAT")

    exp_sub.add_parser("status", help="Show overall synthesis state")

    guard_p = exp_sub.add_parser("guard", help="Show guard details for a path")
    guard_p.add_argument("--path", required=True, help="Path pattern to look up")

    conflict_p = exp_sub.add_parser("conflict", help="Show conflict details")
    conflict_p.add_argument("--id", required=True, help="Conflict ID (e.g. CONFLICT-002)")

    ctx_p = exp_sub.add_parser("context", help="Show what context would be injected")
    ctx_p.add_argument("--agent", required=True, help="Agent ID")
    ctx_p.add_argument("--task", default="", help="Task description")

    savings_p = exp_sub.add_parser("savings", help="Show token economy vs manual context inclusion")
    savings_p.add_argument("--agent", default=None, help="Agent ID (default: first available)")
    savings_p.add_argument("--task", default="", help="Task description")

    # build-arch-map
    sub.add_parser(
        "build-arch-map",
        help="Build architecture_map.json deterministically (Stage 1 → Stage 3 → Stage 2; zero-LLM)",
    )

    # doctor
    sub.add_parser("doctor", help="System health overview")

    # serve (MCP server)
    serve_p = sub.add_parser("serve", help="Start MAES MCP server (stdio transport)")
    serve_p.add_argument(
        "--print-mcp-config", dest="print_mcp_config",
        nargs="?", const="__all__", metavar="TARGET",
        help="Print MCP config for TARGET (claude-code, vscode/copilot, cursor-project, "
             "continue, windsurf, cursor, claude-desktop). No arg: prints all supported clients.",
    )
    serve_p.add_argument(
        "--write-mcp-config", dest="write_mcp_config",
        nargs="?", const="__all__", metavar="TARGET",
        help="Write MCP config to TARGET (claude-code, vscode/copilot, cursor-project, "
             "continue, windsurf, cursor, claude-desktop). Default (no arg): provisions every "
             "supported client (claude-code, vscode, cursor-project, continue, windsurf).",
    )

    # audit
    audit_p = sub.add_parser("audit", help="Quality analysis of MAES synthesis and context")
    audit_p.add_argument("--verbose", "-v", action="store_true", help="Show all findings including OK")
    audit_p.add_argument("--format", choices=["text", "json", "both"], default="both",
                         help="Output format (default: both — text to stdout + files)")
    audit_p.add_argument("--fail-on-warning", action="store_true",
                         help="Exit 1 on WARNING findings (default: only CRITICAL causes exit 1)")

    # agent
    agent_p = sub.add_parser("agent", help="Manage optional agents from the catalogue")
    agent_sub = agent_p.add_subparsers(dest="agent_cmd", metavar="ACTION")

    agent_sub.add_parser("list", help="List catalogue agents and their activation status")

    agent_add_p = agent_sub.add_parser("add", help="Add an optional agent to this project")
    agent_add_p.add_argument("agent_id", metavar="ID", help="Agent ID (e.g. dev-workflow)")
    agent_add_p.add_argument("--skip-sync", action="store_true",
                             help="Add without running maes sync")

    agent_rem_p = agent_sub.add_parser("remove", help="Remove an optional agent from this project")
    agent_rem_p.add_argument("agent_id", metavar="ID", help="Agent ID to remove")
    agent_rem_p.add_argument("--skip-sync", action="store_true",
                             help="Remove without running maes sync")

    # version
    sub.add_parser("version", help="Show CLI version and project upgrade status")

    # upgrade
    up_p = sub.add_parser("upgrade", help="Migrate project .maes/ to current CLI version")
    up_p.add_argument("--dry-run", action="store_true",
                      help="List migrations without applying them")
    up_p.add_argument("--skip-sync", action="store_true",
                      help="Skip maes sync after migrations (useful in CI scripts)")
    # Accept --project-dir after the subcommand too (as documented), alongside the
    # global form. SUPPRESS so it never clobbers a value given before the subcommand.
    up_p.add_argument("--project-dir", "-p", dest="project_dir",
                      default=argparse.SUPPRESS,
                      help="Project directory containing .maes/ (default: auto-detect from cwd)")

    # inferred-to-canonical
    itc_p = sub.add_parser(
        "inferred-to-canonical",
        help="Translate agent-produced inferred/ files to compiler-expected format",
    )
    itc_p.add_argument(
        "--validate",
        action="store_true",
        help="Dry-run: report coverage and validate compiler contracts without writing files",
    )

    # blueprint — catálogo determinístico de aplicações homologadas
    bp_id_help = "Blueprint ID (e.g. nestjs-api)"
    bp_p = sub.add_parser("blueprint", help="Catálogo de Blueprints (aplicações homologadas)")
    bp_sub = bp_p.add_subparsers(dest="blueprint_cmd", metavar="ACTION")

    bp_sub.add_parser("list", help="Listar Blueprints homologados")

    bp_show_p = bp_sub.add_parser("show", help="Mostrar contrato/resumo de um Blueprint")
    bp_show_p.add_argument("blueprint_id", metavar="ID", help=bp_id_help)

    bp_prompt_p = bp_sub.add_parser("prompt", help="Emitir o contexto operacional (prompt.md) do Blueprint")
    bp_prompt_p.add_argument("blueprint_id", metavar="ID", help=bp_id_help)

    bp_bootstrap_p = bp_sub.add_parser("bootstrap", help="Emitir a receita de bootstrap (Official First) do Blueprint")
    bp_bootstrap_p.add_argument("blueprint_id", metavar="ID", help=bp_id_help)

    bp_seed_p = bp_sub.add_parser("seed", help="Semear context/human/ do Blueprint no projeto (.maes/)")
    bp_seed_p.add_argument("blueprint_id", metavar="ID", help=bp_id_help)

    bp_validate_p = bp_sub.add_parser("validate", help="Validar a integridade de um Blueprint (ou de todos)")
    bp_validate_p.add_argument("blueprint_id", metavar="ID", nargs="?", default=None,
                               help="Blueprint ID (omita para validar todos)")

    return parser


# ─── Main ─────────────────────────────────────────────────────────────────────

def _mcp_server_key(maes_dir: Path) -> str:
    return f"maes-{maes_dir.parent.name}"


# Portability: a project-scoped, committable MCP config must not embed
# machine-specific absolute paths. The command is the bare `maes` (resolved via
# PATH), and project clients launch the server with cwd = project root, so
# `maes serve` finds .maes/ on its own — no --project-dir needed. Global configs
# (one file, many projects, no project cwd) MUST pin --project-dir; they live in
# ~ and are never versioned, so an absolute path there is fine.
_GLOBAL_TARGETS = ("windsurf", "claude-desktop", "cursor")


def _maes_args(maes_dir: Path, target: str) -> list:
    if target in _GLOBAL_TARGETS:
        return ["--project-dir", str(maes_dir.parent), "serve"]
    return ["serve"]


def _mcp_server_entry(maes_dir: Path, target: str) -> dict:
    return {"command": "maes", "args": _maes_args(maes_dir, target)}


def _mcp_server_entry_vscode(maes_dir: Path, target: str) -> dict:
    return {"type": "stdio", "command": "maes", "args": _maes_args(maes_dir, target)}


# Every MCP-capable client MAES ships an adapter for. `--write-mcp-config`
# with no argument provisions all of them. copilot == vscode (GitHub Copilot
# agent mode reads VS Code's .vscode/mcp.json), so it is an accepted alias but
# not duplicated in the default set.
_ALL_TARGETS = ("claude-code", "vscode", "cursor-project", "continue", "windsurf")


def _mcp_server_entry_continue(maes_dir: Path, target: str = "continue") -> dict:
    """Continue uses a YAML LIST of servers, each with an explicit `name`."""
    return {
        "name": _mcp_server_key(maes_dir),
        "command": "maes",
        "args": _maes_args(maes_dir, target),
    }


def _mcp_settings_path(target: str, project_dir: "Path | None" = None) -> "Path":
    import platform as _platform
    import os

    base = project_dir if project_dir is not None else Path.cwd()
    if target == "claude-code":
        # Claude Code reads project-scoped MCP servers from .mcp.json at the
        # project root — NOT from .claude/settings.json (which has no
        # server-definition schema and is silently ignored).
        return base / ".mcp.json"
    if target in ("vscode", "copilot"):
        # VS Code native MCP; GitHub Copilot agent mode reads the same file.
        return base / ".vscode" / "mcp.json"
    if target == "cursor-project":
        return base / ".cursor" / "mcp.json"
    if target == "continue":
        return base / ".continue" / "config.yaml"
    if target == "cursor":
        return Path("~/.cursor/mcp.json").expanduser()
    if target == "windsurf":
        # Windsurf has no project-level config — only this user-global file.
        return Path("~/.codeium/windsurf/mcp_config.json").expanduser()
    # claude-desktop
    _cfg = "claude_desktop_config.json"
    system = _platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / _cfg
    if system == "Windows":
        return Path(os.environ.get("APPDATA", Path.home())) / "Claude" / _cfg
    return Path.home() / ".config" / "claude" / _cfg


def _mcp_config_for(target: str, maes_dir: Path) -> "tuple[dict, str]":
    """Return (config_object, top_level_key) in the shape the target expects."""
    server_key = _mcp_server_key(maes_dir)
    if target in ("vscode", "copilot"):
        return {"servers": {server_key: _mcp_server_entry_vscode(maes_dir, target)}}, "servers"
    if target == "continue":
        return {"mcpServers": [_mcp_server_entry_continue(maes_dir, target)]}, "mcpServers"
    return {"mcpServers": {server_key: _mcp_server_entry(maes_dir, target)}}, "mcpServers"


def _print_mcp_config(maes_dir: Path, target: str) -> None:
    if target == "__all__":
        for t in _ALL_TARGETS:
            _print_mcp_config(maes_dir, t)
            print()
        return
    server_key = _mcp_server_key(maes_dir)
    config, key_name = _mcp_config_for(target, maes_dir)
    if target == "continue":
        import yaml
        print(yaml.safe_dump(config, sort_keys=False, allow_unicode=True).rstrip())
    else:
        print(json.dumps(config, indent=2))
    print(f"\n# Merge the '{server_key}' entry into {key_name} in:")
    print(f"# {_mcp_settings_path(target, maes_dir.parent)}")


def _load_mcp_settings(settings_path: Path, is_yaml: bool) -> "dict | None":
    """Return the parsed settings dict ({} if the file is absent or empty), or
    None on a read/parse error. Backs up an existing file to ``.bak``."""
    import shutil
    import yaml

    if not settings_path.exists():
        return {}
    try:
        with open(settings_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) if is_yaml else json.load(f)
    except (json.JSONDecodeError, OSError, yaml.YAMLError) as exc:
        print(f"Error reading {settings_path}: {exc}", file=sys.stderr)
        return None
    backup = settings_path.with_name(settings_path.name + ".bak")
    shutil.copy2(settings_path, backup)
    print(f"Backup created: {backup}")
    return existing if isinstance(existing, dict) else {}


def _merge_mcp_server_entry(existing: dict, maes_dir: Path, target: str, server_key: str, is_yaml: bool) -> None:
    """Insert (or replace) this project's MCP server entry into ``existing`` in
    the shape the target editor expects, preserving any other config."""
    if target in ("vscode", "copilot"):
        existing.setdefault("servers", {})[server_key] = _mcp_server_entry_vscode(maes_dir, target)
    elif is_yaml:
        # Continue's mcpServers is a LIST keyed by `name`; replace our prior
        # entry (if any) and preserve everyone else's, plus all other config.
        servers = existing.get("mcpServers")
        servers = servers if isinstance(servers, list) else []
        servers = [s for s in servers
                   if not (isinstance(s, dict) and s.get("name") == server_key)]
        servers.append(_mcp_server_entry_continue(maes_dir, target))
        existing["mcpServers"] = servers
    else:
        existing.setdefault("mcpServers", {})[server_key] = _mcp_server_entry(maes_dir, target)


def _dump_mcp_settings(settings_path: Path, existing: dict, is_yaml: bool) -> None:
    import yaml

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w", encoding="utf-8") as f:
        if is_yaml:
            yaml.safe_dump(existing, f, sort_keys=False, allow_unicode=True)
        else:
            json.dump(existing, f, indent=2)
            f.write("\n")


def _print_mcp_reload_hint(maes_dir: Path, target: str, server_key: str) -> None:
    if target == "claude-code":
        # A project .mcp.json server requires explicit approval before Claude
        # Code will launch it. Pre-approve it in the user-private
        # settings.local.json so it loads on reload without a manual prompt
        # (and so `maes sync`, which rewrites settings.json, never clobbers it).
        _enable_project_mcp_server(maes_dir.parent, server_key)
    if target in ("claude-code", "vscode", "copilot", "cursor-project", "continue"):
        print("Reload the editor window (Ctrl+Shift+P → Developer: Reload Window) for the MCP server to appear.")
    elif target == "windsurf":
        print("Restart Windsurf (or refresh the Cascade MCP panel) for the server to appear.")


def _write_mcp_config(maes_dir: Path, target: str) -> int:
    if target == "__all__":
        for t in _ALL_TARGETS:
            ret = _write_mcp_config(maes_dir, t)
            if ret != 0:
                return ret
        return 0

    settings_path = _mcp_settings_path(target, maes_dir.parent)
    server_key = _mcp_server_key(maes_dir)
    is_yaml = target == "continue"

    existing = _load_mcp_settings(settings_path, is_yaml)
    if existing is None:
        return 1

    _merge_mcp_server_entry(existing, maes_dir, target, server_key, is_yaml)
    _dump_mcp_settings(settings_path, existing, is_yaml)

    print(f"Added '{server_key}' to {settings_path}")
    _print_mcp_reload_hint(maes_dir, target, server_key)
    return 0


def _enable_project_mcp_server(project_dir: Path, server_key: str) -> None:
    """Pre-approve a project-scoped (.mcp.json) MCP server for Claude Code by
    adding it to `enabledMcpjsonServers` in .claude/settings.local.json."""
    local_path = project_dir / ".claude" / "settings.local.json"
    data: dict = {}
    if local_path.exists():
        try:
            with open(local_path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}
    enabled = data.setdefault("enabledMcpjsonServers", [])
    if server_key not in enabled:
        enabled.append(server_key)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"Pre-approved '{server_key}' in {local_path}")


def _handle_explain(args, maes_dir: Path, parser: argparse.ArgumentParser) -> None:
    from .explain import (
        explain_status, explain_guard, explain_conflict, explain_context, explain_savings
    )
    what = getattr(args, "explain_cmd", None)
    if not what or what == "status":
        explain_status(maes_dir)
    elif what == "guard":
        explain_guard(maes_dir, args.path)
    elif what == "conflict":
        explain_conflict(maes_dir, args.id)
    elif what == "context":
        explain_context(maes_dir, args.agent, args.task)
    elif what == "savings":
        explain_savings(maes_dir, getattr(args, "agent", None), getattr(args, "task", ""))
    else:
        parser.parse_args(["explain", "--help"])


def _handle_serve(args, maes_dir: Path) -> None:
    if getattr(args, "print_mcp_config", None) is not None:
        _print_mcp_config(maes_dir, args.print_mcp_config or "claude-desktop")
        sys.exit(0)
    if getattr(args, "write_mcp_config", None) is not None:
        sys.exit(_write_mcp_config(maes_dir, args.write_mcp_config or "__all__"))
    from .mcp_server import run as mcp_run
    import asyncio
    asyncio.run(mcp_run(maes_dir))


def _handle_agent(args, maes_dir: Path) -> int:
    from .agent_manager import run_agent_list, run_agent_add, run_agent_remove
    sub = getattr(args, "agent_cmd", None)
    if not sub or sub == "list":
        return run_agent_list(maes_dir)
    if sub == "add":
        ret = run_agent_add(maes_dir, args.agent_id)
        if ret == 0 and not getattr(args, "skip_sync", False):
            print(_MSG_RUNNING_SYNC)
            return _run_sync(maes_dir)
        return ret
    if sub == "remove":
        ret = run_agent_remove(maes_dir, args.agent_id)
        if ret == 0 and not getattr(args, "skip_sync", False):
            print(_MSG_RUNNING_SYNC)
            return _run_sync(maes_dir)
        return ret
    print("Usage: maes agent [list|add|remove]")
    return 1


def _run_maes_command(args, maes_dir: Path, parser) -> None:
    cmd = args.command
    if cmd == "sync":
        sys.exit(_run_sync(maes_dir, verbose=args.verbose, clean=getattr(args, "clean", False)))
    if cmd == "validate":
        sys.exit(_run_validate(maes_dir))
    if cmd == "build-arch-map":
        from .build_arch_map_cmd import run_build_arch_map
        project_dir = maes_dir.parent
        sys.exit(run_build_arch_map(project_dir, maes_dir))
    if cmd == "agent":
        sys.exit(_handle_agent(args, maes_dir))
    if cmd == "explain":
        _handle_explain(args, maes_dir, parser)
    elif cmd == "serve":
        _handle_serve(args, maes_dir)
    elif cmd == "audit":
        from .audit_cmd import run_audit
        sys.exit(run_audit(
            maes_dir,
            verbose=getattr(args, "verbose", False),
            fail_on_warning=getattr(args, "fail_on_warning", False),
            output_format=getattr(args, "format", "both"),
        ))
    elif cmd == "inferred-to-canonical":
        from .inferred_canonical_cmd import run_inferred_to_canonical
        sys.exit(run_inferred_to_canonical(
            maes_dir,
            validate_only=getattr(args, "validate", False),
        ))
    else:
        parser.print_help()
        sys.exit(1)


def _handle_blueprint(args, parser) -> int:
    """Dispatch para `maes blueprint`. list/show/prompt não exigem projeto."""
    from . import blueprint_cmd

    sub_cmd = getattr(args, "blueprint_cmd", None)
    if sub_cmd == "list":
        return blueprint_cmd.cmd_list()
    if sub_cmd == "show":
        return blueprint_cmd.cmd_show(args.blueprint_id)
    if sub_cmd == "prompt":
        return blueprint_cmd.cmd_prompt(args.blueprint_id)
    if sub_cmd == "bootstrap":
        return blueprint_cmd.cmd_bootstrap(args.blueprint_id)
    if sub_cmd == "validate":
        return blueprint_cmd.cmd_validate(args.blueprint_id)
    if sub_cmd == "seed":
        # seed exige projeto — resolve maes_dir sob demanda (pode sair com exit 1)
        maes_dir = _find_maes_dir(args.project_dir)
        return blueprint_cmd.cmd_seed(args.blueprint_id, maes_dir)

    parser.parse_args(["blueprint", "--help"])
    return 1


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # init, doctor don't need .maes/ to exist yet
    if args.command == "init":
        from .init_cmd import run_init
        project_dir = Path(args.project_dir) if args.project_dir else None
        run_init(project_dir)
        return

    if args.command == "doctor":
        project_dir = Path(args.project_dir) if args.project_dir else None
        sys.exit(_run_doctor(project_dir))

    if args.command == "version":
        from .version_cmd import run_version
        sys.exit(run_version(args.project_dir))

    if args.command == "upgrade":
        from .upgrade_cmd import run_upgrade
        project_dir = Path(args.project_dir) if args.project_dir else None
        sys.exit(run_upgrade(
            project_dir,
            dry_run=args.dry_run,
            skip_sync=args.skip_sync,
        ))

    # blueprint: list/show/prompt/validate rodam sem .maes/ (catálogo empacotado);
    # só `seed` exige projeto e resolve maes_dir sob demanda. Roteado ANTES de
    # _find_maes_dir para não exigir projeto no fluxo greenfield.
    if args.command == "blueprint":
        sys.exit(_handle_blueprint(args, parser))

    maes_dir = _find_maes_dir(args.project_dir)
    _run_maes_command(args, maes_dir, parser)


if __name__ == "__main__":
    main()
