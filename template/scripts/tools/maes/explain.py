#!/usr/bin/env python3
"""maes explain — Context Observability: audit every system decision."""

from __future__ import annotations

import json
from pathlib import Path

from .models import LAYER_NAMES


# ─── Load synthesis ────────────────────────────────────────────────────────────

def _load_synthesis(maes_dir: Path) -> dict:
    synth = {}
    for name in ("assertions", "guards", "conflicts", "anti-hallucination", "staleness"):
        f = maes_dir / "synthesis" / f"{name}.json"
        if f.exists():
            try:
                synth[name] = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                synth[name] = [] if name != "staleness" else {}
        else:
            synth[name] = [] if name != "staleness" else {}
    return synth


def _load_agents(maes_dir: Path) -> list[dict]:
    agents_dir = maes_dir / "agents"
    if not agents_dir.exists():
        return []
    try:
        import yaml
    except ImportError:
        return []
    agents = []
    for f in sorted(agents_dir.glob("*.agent.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            agents.append(data)
        except Exception:
            continue
    return agents


# ─── Formatting helpers ────────────────────────────────────────────────────────

def _hr() -> str:
    return "─" * 60


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


def _yellow(text: str) -> str:
    return f"\033[33m{text}\033[0m"


def _red(text: str) -> str:
    return f"\033[31m{text}\033[0m"


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m"


def _cyan(text: str) -> str:
    return f"\033[36m{text}\033[0m"


# ─── maes explain status ──────────────────────────────────────────────────────

def _print_conflicts_section(unresolved: list, resolved: list) -> None:
    total = len(unresolved) + len(resolved)
    print(f"\n{_bold('Conflicts')}: {total} total")
    if unresolved:
        print(_red(f"  ✗ {len(unresolved)} UNRESOLVED — blocking CI"))
        for c in unresolved[:5]:
            print(f"    {c['id']}: {c['reason'][:80]}")
    else:
        print(_green("  ✓ No unresolved conflicts"))
    if resolved:
        print(f"  ✓ {len(resolved)} resolved automatically")


def _print_staleness_section(stale_critical: list, stale_warn: list) -> None:
    print(f"\n{_bold('Staleness')}")
    if stale_critical:
        print(_red(f"  ✗ {len(stale_critical)} assertions with staleness ≥ 0.6 (not injected)"))
        for a in stale_critical[:3]:
            owner = a.get("owner", "unowned")
            print(f"    [{owner}] {a.get('claim', '')[:70]}")
    elif stale_warn:
        print(_yellow(f"  ⚠ {len(stale_warn)} assertions with staleness ≥ 0.3 (injected with caveat)"))
    else:
        print(_green("  ✓ All assertions fresh"))


def explain_status(maes_dir: Path) -> None:
    synth = _load_synthesis(maes_dir)
    assertions = synth.get("assertions", [])
    conflicts = synth.get("conflicts", [])
    guards = synth.get("guards", [])
    anti_h = synth.get("anti-hallucination", [])

    unresolved = [c for c in conflicts if c.get("status") == "UNRESOLVED"]
    resolved = [c for c in conflicts if c.get("status") == "RESOLVED"]
    stale_critical = [a for a in assertions if _stale_score_from_dict(a) >= 0.6]
    stale_warn = [a for a in assertions if 0.3 <= _stale_score_from_dict(a) < 0.6]

    print(_bold("MAES Status"))
    print(_hr())

    # Assertions breakdown
    by_layer: dict[int, int] = {}
    by_source: dict[str, int] = {"human": 0, "inferred": 0}
    for a in assertions:
        layer = a.get("layer", 7)
        by_layer[layer] = by_layer.get(layer, 0) + 1
        src = "human" if str(a.get("source", "")).startswith("human/") else "inferred"
        by_source[src] = by_source.get(src, 0) + 1

    print(f"\n{_bold('Assertions')}: {len(assertions)} total")
    print(f"  Human: {by_source['human']}  |  Inferred: {by_source['inferred']}")
    for layer in sorted(by_layer):
        layer_name = LAYER_NAMES.get(layer, f"layer-{layer}")
        print(f"  Layer {layer} ({layer_name}): {by_layer[layer]}")

    # Hot context
    print(f"\n{_bold('Hot Context')}: {len(anti_h)} rules")
    hot_tokens = sum(max(1, len(r.get("claim", "")) // 4) for r in anti_h)
    bar = "█" * min(hot_tokens // 40, 20)
    print(f"  ~{hot_tokens} tokens [{bar}] / 800 cap")

    _print_conflicts_section(unresolved, resolved)

    # Guards
    print(f"\n{_bold('Guards')}: {len(guards)} active")
    by_policy: dict[str, int] = {}
    for g in guards:
        p = g.get("policy", "requires-checklist")
        by_policy[p] = by_policy.get(p, 0) + 1
    for policy, count in sorted(by_policy.items()):
        print(f"  {policy}: {count}")

    _print_staleness_section(stale_critical, stale_warn)

    # Adapters
    adapters_dir = maes_dir / "adapters"
    print(f"\n{_bold('Adapters')}")
    for ide in ("claude", "cursor", "roo", "cline"):
        ide_dir = adapters_dir / ide
        exists = ide_dir.exists() and any(ide_dir.rglob("*"))
        status = _green("✓") if exists else _yellow("–")
        print(f"  {status} {ide}")

    sync_file = maes_dir / "synthesis" / "assertions.json"
    if sync_file.exists():
        import datetime
        mtime = sync_file.stat().st_mtime
        dt = datetime.datetime.fromtimestamp(mtime)
        print(f"\n{_bold('Last sync')}: {dt.strftime('%Y-%m-%d %H:%M')}")

    print()


# ─── maes explain guard ───────────────────────────────────────────────────────

def explain_guard(maes_dir: Path, path_pattern: str) -> None:
    synth = _load_synthesis(maes_dir)
    guards = synth.get("guards", [])

    matched = [
        g for g in guards
        if any(path_pattern in p or p in path_pattern for p in g.get("paths", []))
    ]

    if not matched:
        print(_yellow(f"No guards found matching '{path_pattern}'"))
        print("Run `maes explain status` to see all active guards.")
        return

    print(_bold(f"Guards matching '{path_pattern}'"))
    print(_hr())

    for g in matched:
        policy = g.get("policy", "")
        policy_color = _red(policy) if policy == "block" else _yellow(policy)
        print(f"\n{_bold('Guard ID')}: {g['id']}")
        print(f"Policy:   {policy_color}")
        print(f"Paths:    {', '.join(g.get('paths', []))}")
        print(f"Layer:    {g.get('layer', '?')} ({LAYER_NAMES.get(g.get('layer', 7), '')})")
        print(f"Source:   {g.get('source_file', '')}")
        print(f"Owner:    {g.get('owner', 'unowned')}")
        print(f"\n{_bold('Claim')}:")
        print(f"  {g.get('claim', '')}")
        checklist = g.get("checklist", [])
        if checklist:
            print(f"\n{_bold('Checklist before proceeding')}:")
            for item in checklist:
                print(f"  [ ] {item}")
    print()


# ─── maes explain conflict ────────────────────────────────────────────────────

def explain_conflict(maes_dir: Path, conflict_id: str) -> None:
    synth = _load_synthesis(maes_dir)
    conflicts = synth.get("conflicts", [])
    assertions_by_id = {a["id"]: a for a in synth.get("assertions", [])}

    target = next((c for c in conflicts if c.get("id") == conflict_id), None)
    if not target:
        print(_yellow(f"Conflict '{conflict_id}' not found."))
        all_ids = [c.get("id") for c in conflicts]
        if all_ids:
            print(f"Available conflicts: {', '.join(all_ids)}")
        return

    status = target.get("status", "UNKNOWN")
    status_str = _green("RESOLVED") if status == "RESOLVED" else _red("UNRESOLVED")

    print(_bold(f"Conflict {conflict_id}"))
    print(_hr())
    print(f"Status: {status_str}")
    print(f"Reason: {target.get('reason', '')}")
    if target.get("winner"):
        print(f"Winner: {target['winner']}")

    for key in ("assertion_a", "assertion_b"):
        aid = target.get(key, "")
        a = assertions_by_id.get(aid, {})
        label = "A" if key == "assertion_a" else "B"
        marker = "  ← winner" if target.get("winner") == aid else ""
        print(f"\n{_bold(f'Assertion {label}')}{marker}:")
        print(f"  ID:         {aid}")
        print(f"  Claim:      {a.get('claim', aid)[:120]}")
        print(f"  Confidence: {a.get('confidence', '?')}")
        print(f"  Layer:      {a.get('layer', '?')} ({LAYER_NAMES.get(a.get('layer', 7), '')})")
        print(f"  Source:     {a.get('source', '?')}")
    print()


# ─── maes explain context ─────────────────────────────────────────────────────

def _stale_score_from_dict(d: dict) -> float:
    from datetime import date
    from .compiler import staleness_score as _ss
    from .models import Assertion
    a = Assertion(
        id=d.get("id", ""), claim=d.get("claim", ""),
        type=d.get("type", "PATTERN"), layer=d.get("layer", 7),
        subject=d.get("subject"), paths=d.get("paths", []),
        confidence=d.get("confidence", "assumed"), source=d.get("source", ""),
        ttl=d.get("ttl", "730d"), last_verified=d.get("last_verified", ""),
        owner=d.get("owner", ""),
    )
    return _ss(a, date.today())


def _assertion_from_dict(d: dict):
    from .models import Assertion, _VALID_CONFIDENCE, _VALID_TYPES
    confidence = d.get("confidence", "inferred-medium")
    if confidence not in _VALID_CONFIDENCE:
        confidence = "inferred-medium"
    atype = d.get("type", "PATTERN")
    if atype not in _VALID_TYPES:
        atype = "PATTERN"
    layer = d.get("layer", 7)
    if not isinstance(layer, int) or not (1 <= layer <= 7):
        layer = 7
    return Assertion(
        id=d.get("id", ""), claim=d.get("claim", ""),
        type=atype, layer=layer, subject=d.get("subject"),
        paths=d.get("paths", []), confidence=confidence,
        source=d.get("source", ""), ttl=d.get("ttl", "730d"),
        last_verified=d.get("last_verified", ""), owner=d.get("owner", ""),
        merge_history=d.get("merge_history", []), code_examples=d.get("code_examples", []),
    )


def _build_assertions(assertions: list[dict]) -> list:
    return [_assertion_from_dict(a) for a in assertions]


def _print_hot_tier(hot: list) -> None:
    print(f"\n{_bold('HOT TIER')} (always loaded, compliance/security):")
    if hot:
        hot_tokens = sum(max(1, len(r.get("claim", "")) // 4) for r in hot)
        print(f"  ~{hot_tokens} tokens / 800 cap")
        for r in hot[:8]:
            print(f"  ✓ [{LAYER_NAMES.get(r.get('layer', 7), '')}] {r['claim'][:90]}")
        if len(hot) > 8:
            print(f"  ... and {len(hot) - 8} more")
    else:
        print("  (none)")


def _print_warm_tier(warm: list) -> None:
    from datetime import date
    from .compiler import staleness_score as _ss
    today = date.today()
    print(f"\n{_bold('WARM TIER')} (loaded by relevance):")
    if warm:
        warm_tokens = sum(max(1, len(a.claim) // 4) for a in warm)
        print(f"  ~{warm_tokens} tokens used")
        for a in warm[:10]:
            stale = " ⚠️ stale" if _ss(a, today) > 0.6 else ""
            print(f"  ✓ [layer {a.layer}] {a.claim[:90]}{stale}")
        if len(warm) > 10:
            print(f"  ... and {len(warm) - 10} more")
    else:
        print("  (none matched relevance threshold)")


def explain_context(maes_dir: Path, agent_id: str, task: str) -> None:
    synth = _load_synthesis(maes_dir)
    assertions = synth.get("assertions", [])
    anti_h = synth.get("anti-hallucination", [])

    agents = _load_agents(maes_dir)
    agent = next((a for a in agents if a.get("id") == agent_id), None)

    if not agent:
        print(_yellow(f"Agent '{agent_id}' not found."))
        available = [a.get("id") for a in agents]
        if available:
            print(f"Available agents: {', '.join(available)}")
        return

    from .adapters import _assertions_for_agent

    hot, warm = _assertions_for_agent(agent, _build_assertions(assertions), anti_h)

    print(_bold(f"Context for agent '{agent_id}'"))
    if task:
        print(f"Task: {task}")
    print(_hr())

    _print_hot_tier(hot)
    _print_warm_tier(warm)

    # Show what was NOT loaded (cold tier sample — assertions are dicts here)
    warm_ids = {a.id for a in warm}
    cold_examples = [
        a for a in assertions
        if a["id"] not in warm_ids
        and a.get("confidence") not in ("explicit", "inferred-high")
    ][:3]

    if cold_examples:
        print(f"\n{_bold('COLD TIER')} (not loaded — sample):")
        for a in cold_examples:
            print(f"  ✗ [score<threshold or cold] {a['claim'][:90]}")

    print()


# ─── maes explain savings ─────────────────────────────────────────────────────

_CONTEXT_WINDOW = 128_000
_SKIP_DIRS = {
    ".maes", "node_modules", ".git", "dist", "build",
    "__pycache__", ".venv", "venv", ".next", "coverage", ".turbo",
}
_CODE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".java",
    ".rs", ".rb", ".cs", ".md", ".mdx", ".sql", ".yaml", ".yml",
}


def _count_file_tokens(path: Path) -> int:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return max(1, len(content) // 4)
    except OSError:
        return 0


def _is_skipped(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return any(part in _SKIP_DIRS for part in parts)


def _resolve_agent_for_savings(
    agent_id: str | None,
    agents: list[dict],
) -> tuple[dict | None, str | None]:
    if agent_id:
        found = next((a for a in agents if a.get("id") == agent_id), None)
        if not found:
            print(_yellow(f"Agent '{agent_id}' not found."))
            available = [a.get("id") for a in agents]
            if available:
                print(f"Available agents: {', '.join(available)}")
            return None, None
        return found, agent_id
    if agents:
        return agents[0], agents[0].get("id", "default")
    return None, None


def _maes_context_tokens(
    assertions: list[dict],
    anti_h: list[dict],
    agent: dict | None,
) -> tuple[int, int]:
    hot_tokens = sum(max(1, len(r.get("claim", "")) // 4) for r in anti_h)
    if agent is None:
        warm_tokens = sum(max(1, len(a.get("claim", "")) // 4) for a in assertions)
        return hot_tokens, warm_tokens

    from .adapters import _assertions_for_agent
    _, warm_items = _assertions_for_agent(agent, _build_assertions(assertions), anti_h)
    warm_tokens = sum(max(1, len(a.claim) // 4) for a in warm_items)
    return hot_tokens, warm_tokens


def _targeted_baseline(
    assertions: list[dict], project_root: Path
) -> tuple[int, int, bool]:
    patterns: set[str] = {
        p.lstrip("/")
        for a in assertions
        for p in a.get("paths", [])
        if p
    }
    files: set[Path] = set()
    for pattern in patterns:
        try:
            for f in project_root.glob(pattern):
                if f.is_file() and f.suffix in _CODE_EXTS and not _is_skipped(f, project_root):
                    files.add(f)
        except (ValueError, OSError):
            continue
    tokens = sum(_count_file_tokens(f) for f in files)
    return tokens, len(files), bool(patterns and not files)


def _full_codebase_baseline(project_root: Path) -> tuple[int, int]:
    tokens = 0
    count = 0
    for f in project_root.rglob("*"):
        if not f.is_file() or f.suffix not in _CODE_EXTS:
            continue
        if _is_skipped(f, project_root) or f.stat().st_size > 500_000:
            continue
        tokens += _count_file_tokens(f)
        count += 1
    return tokens, count


def _print_savings(
    agent_id: str | None,
    task: str,
    hot_tokens: int,
    warm_tokens: int,
    targeted_tokens: int,
    targeted_count: int,
    targeted_empty: bool,
    full_tokens: int,
    full_count: int,
) -> None:
    maes_total = hot_tokens + warm_tokens

    def pct(n: int) -> str:
        return f"{n / _CONTEXT_WINDOW * 100:.1f}%"

    def fmt(n: int) -> str:
        return f"{n:,}t"

    def ratio_str(baseline: int) -> str:
        if maes_total == 0:
            return "∞"
        r = baseline / maes_total
        return f"{r:.0f}×" if r >= 2 else f"{r:.1f}×"

    W = 30
    task_label = f', task: "{task}"' if task else ""
    agent_label = f"agent: {agent_id}" if agent_id else "todos os agentes"

    print(_bold(f"MAES Context Savings — {agent_label}{task_label}"))
    print(_hr())
    print(f"\n{'Fonte de contexto':<{W}}  {'Tokens':>10}  {'% de 128K':>10}")
    print("─" * 56)
    print(f"{'MAES hot context (L1-3)':<{W}}  {fmt(hot_tokens):>10}  {pct(hot_tokens):>10}")
    print(f"{'MAES warm context (L4-6)':<{W}}  {fmt(warm_tokens):>10}  {pct(warm_tokens):>10}")
    print(f"{'MAES total':<{W}}  {fmt(maes_total):>10}  {pct(maes_total):>10}")
    print()

    if targeted_tokens > 0:
        print(f"{'Baseline: arquivos relevantes':<{W}}  {fmt(targeted_tokens):>10}  {pct(targeted_tokens):>10}"
              f"  ← {targeted_count} arquivos ({_yellow('inclusão manual direcionada')})")
    elif targeted_empty:
        print(f"  {_yellow('Baseline targeted: sem arquivos correspondentes aos paths das assertions')}")

    overflow_note = f"  {_red('⚠ estoura 128K')}" if full_tokens > _CONTEXT_WINDOW else ""
    print(f"{'Baseline: codebase completo':<{W}}  {fmt(full_tokens):>10}  {pct(full_tokens):>10}"
          f"  ← {full_count} arquivos ({_yellow('vibe coding')}){overflow_note}")

    print()
    if maes_total > 0:
        if targeted_tokens > 0:
            print(_green(f"Economia vs inclusão manual:   {ratio_str(targeted_tokens)} menos tokens"))
        if full_tokens > 0:
            print(_green(f"Economia vs codebase completo: {ratio_str(full_tokens)} menos tokens"))

    remaining = _CONTEXT_WINDOW - maes_total
    approx_lines = remaining * 4 // 80
    print(f"\nContext budget usado:  {maes_total:,} / {_CONTEXT_WINDOW:,} tokens  ({maes_total / _CONTEXT_WINDOW * 100:.1f}%)")
    print(f"Sobra para o código:  {remaining:,} tokens  (~{approx_lines:,} linhas)")
    print()


def explain_savings(maes_dir: Path, agent_id: str | None, task: str) -> None:
    synth = _load_synthesis(maes_dir)
    assertions = synth.get("assertions", [])
    anti_h = synth.get("anti-hallucination", [])

    if not assertions and not anti_h:
        print(_yellow("No synthesis found. Run `maes sync` first."))
        return

    agent, resolved_id = _resolve_agent_for_savings(agent_id, _load_agents(maes_dir))
    if agent_id and agent is None:
        return

    hot_tokens, warm_tokens = _maes_context_tokens(assertions, anti_h, agent)
    targeted_tokens, targeted_count, targeted_empty = _targeted_baseline(assertions, maes_dir.parent)
    full_tokens, full_count = _full_codebase_baseline(maes_dir.parent)

    _print_savings(
        resolved_id, task,
        hot_tokens, warm_tokens,
        targeted_tokens, targeted_count, targeted_empty,
        full_tokens, full_count,
    )
