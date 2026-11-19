#!/usr/bin/env python3
"""MAES MCP Server — exposes compiled context as MCP tools (stdio transport).

Tools:
  maes_get_agent_context   get hot+warm context for an agent and task
  maes_check_guard         check if an action on a path is ALLOWED/BLOCKED
  maes_list_agents         list available MAES agents
  maes_who_depends_on      query impact graph for a file/directory path

The server reads from .maes/synthesis/ (pre-compiled by maes sync).
No API key required at runtime — synthesis must exist before starting.

Claude Desktop config (~/.claude/claude_desktop_config.json):
  {
    "mcpServers": {
      "maes": {
        "command": "python",
        "args": ["/path/to/maes.py", "serve", "--project-dir", "/your/project"]
      }
    }
  }

Cursor settings.json:
  {
    "mcpServers": {
      "maes": {
        "command": "python",
        "args": ["/path/to/maes.py", "serve"],
        "cwd": "/your/project"
      }
    }
  }
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

# Module-level dir — set by run() before server starts
_maes_dir: Path | None = None

_ASSERTIONS_JSON = "assertions.json"
_GUARDS_JSON = "guards.json"
_IMPACT_GRAPH_JSON = "impact-graph.json"


# ─── Data loading ─────────────────────────────────────────────────────────────

def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


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


def _assertion_from_dict(d: dict):
    """Reconstruct an Assertion from a synthesis JSON dict."""
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
        id=d.get("id", ""),
        claim=d.get("claim", ""),
        type=atype,
        layer=layer,
        subject=d.get("subject"),
        paths=d.get("paths", []),
        confidence=confidence,
        source=d.get("source", ""),
        ttl=d.get("ttl", "730d"),
        last_verified=d.get("last_verified", ""),
        owner=d.get("owner", ""),
        merge_history=d.get("merge_history", []),
        code_examples=d.get("code_examples", []),
    )


# ─── Glob path matching ───────────────────────────────────────────────────────

def _match_guard_path(file_path: str, pattern: str) -> bool:
    if pattern == "**":
        return True
    if pattern.endswith("/") and "**" not in pattern and "*" not in pattern:
        return file_path.startswith(pattern)
    if "**" not in pattern:
        regex = re.escape(pattern).replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
        return bool(re.fullmatch(regex, file_path))
    regex = re.escape(pattern)
    regex = regex.replace(re.escape("**"), "\x00")
    regex = regex.replace(re.escape("*"), "[^/]*")
    regex = regex.replace(re.escape("?"), "[^/]")
    regex = regex.replace("\x00", ".*")
    if re.fullmatch(regex, file_path):
        return True
    if pattern.startswith("**/"):
        return _match_guard_path(file_path, pattern[3:])
    return False


# ─── Tool implementations ──────────────────────────────────────────────────────

def _assertion_lines(a, today: date) -> list[str]:
    from .compiler import staleness_score
    stale = "  ⚠️ may be stale" if staleness_score(a, today) > 0.6 else ""
    result = [f"- {a.claim}{stale}"]
    examples = a.code_examples or []
    if examples and examples[0].get("wrong") and examples[0].get("correct"):
        ex = examples[0]
        result.append(f"\n  ```\n  # ❌ {ex['wrong']}\n  # ✅ {ex['correct']}\n  ```")
    return result


def _render_warm_tier(warm: list, today: date) -> list[str]:
    from .models import LAYER_NAMES
    by_layer: dict[int, list] = {}
    for a in warm:
        by_layer.setdefault(a.layer, []).append(a)
    lines: list[str] = ["## Project Context", ""]
    for layer in sorted(by_layer):
        layer_name = LAYER_NAMES.get(layer, f"layer-{layer}")
        lines.append(f"### {layer_name.title()}")
        for a in by_layer[layer]:
            lines += _assertion_lines(a, today)
        lines.append("")
    return lines


def _render_arch_map_section(synth_dir: Path) -> list[str]:
    """Return markdown lines for the Architecture Map section, or [] if unavailable."""
    arch_file = synth_dir / "architecture_map.json"
    if not arch_file.exists():
        return []
    try:
        data = json.loads(arch_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    nodes = data.get("nodes", [])
    if not nodes:
        return []
    lines = ["## Architecture Map", "",
             "| Module | Path | Type | Entry Points |",
             "|--------|------|------|-------------|"]
    for node in nodes:
        ep = ", ".join(node.get("entry_points", [])[:2]) or "—"
        lines.append(
            f"| {node.get('name', '')} | {node.get('path', '')} "
            f"| {node.get('type', '')} | {ep} |"
        )
    lines.append("")
    return lines


def _render_context_output(
    hot: list,
    warm: list,
    agent: dict,
    task_description: str,
    synth_dir: "Path | None" = None,
) -> str:
    if not hot and not warm:
        agent_id = agent.get("id", "")
        return (
            f"No context found for agent '{agent_id}'.\n"
            "The synthesis may be empty — run `maes sync` to compile."
        )

    today = date.today()
    lines: list[str] = []

    if hot:
        lines += ["## Critical Rules (always apply)", ""]
        for rule in hot:
            lines.append(f"- {rule.get('claim', '')}")
        lines.append("")

    if warm:
        lines += _render_warm_tier(warm, today)

    if synth_dir is not None:
        lines += _render_arch_map_section(synth_dir)

    name = agent.get("name", agent.get("id", ""))
    header = [f"# {name} — MAES Context", ""]
    if task_description:
        header.append(f"> Task: {task_description}")
        header.append("")

    return "\n".join(header + lines).rstrip() + "\n"


def _tool_get_agent_context(agent_id: str, task_description: str) -> str:
    assert _maes_dir is not None
    synth_dir = _maes_dir / "synthesis"

    if not (synth_dir / _ASSERTIONS_JSON).exists():
        return (
            "Synthesis not found — run `maes sync` first.\n"
            f"Expected: {synth_dir / _ASSERTIONS_JSON}"
        )

    assertions_raw: list[dict] = _load_json(synth_dir / _ASSERTIONS_JSON, [])
    anti_h: list[dict] = _load_json(synth_dir / "anti-hallucination.json", [])

    agents = _load_agents(_maes_dir)
    agent = next((a for a in agents if a.get("id") == agent_id), None)

    if not agent:
        available = sorted(a.get("id", "") for a in agents if a.get("id"))
        return (
            f"Agent '{agent_id}' not found.\n"
            f"Available agents: {', '.join(available) or 'none — run maes init'}\n\n"
            "Use `maes_list_agents` to see details."
        )

    assertions = [_assertion_from_dict(d) for d in assertions_raw]

    from .adapters import _assertions_for_agent
    hot, warm = _assertions_for_agent(
        agent, assertions, anti_h,
        warm_token_budget=4000,
        task=task_description,
    )

    return _render_context_output(hot, warm, agent, task_description, synth_dir=synth_dir)


def _collect_guard_matches(guards: list[dict], path: str) -> tuple[list[dict], list[dict]]:
    matched_enforcement: list[dict] = []
    matched_contextual: list[dict] = []
    for g in guards:
        is_enforcement = g.get("guard_type") == "enforcement"
        for gpath in g.get("paths", []):
            if _match_guard_path(path, gpath):
                if is_enforcement:
                    matched_enforcement.append(g)
                else:
                    matched_contextual.append(g)
                break
    return matched_enforcement, matched_contextual


def _render_blocked_block(blocking: list[dict], action: str, path: str) -> list[str]:
    lines: list[str] = ["BLOCKED", ""]
    lines.append(f"Action `{action}` on `{path}` is blocked by {len(blocking)} guard(s):")
    lines.append("")
    for g in blocking:
        lines.append(f"**{g.get('claim', '')[:120]}**")
        lines.append(f"  - Layer: {g.get('layer', '?')}")
        lines.append(f"  - Source: {g.get('source_file', 'unknown')}")
        lines.append(f"  - Owner: {g.get('owner', 'unowned')}")
        lines.append("")
    lines.append("Escalate to the guard owner before proceeding.")
    return lines


def _render_approval_block(approving: list[dict], action: str, path: str) -> list[str]:
    lines: list[str] = ["REQUIRES_APPROVAL", ""]
    lines.append(f"Action `{action}` on `{path}` requires approval checklist:")
    lines.append("")
    for g in approving:
        lines.append(f"**{g.get('claim', '')[:120]}**")
        checklist = g.get("checklist", [])
        for item in checklist:
            lines.append(f"  [ ] {item}")
        if checklist:
            lines.append("")
    return lines


def _render_guard_verdict(
    blocking: list[dict],
    approving: list[dict],
    matched_enforcement: list[dict],
    matched_contextual: list[dict],
    action: str,
    path: str,
) -> list[str]:
    if blocking:
        lines = _render_blocked_block(blocking, action, path)
    elif approving:
        lines = _render_approval_block(approving, action, path)
    else:
        lines = ["ALLOWED", ""]
        if not matched_enforcement and not matched_contextual:
            lines.append(f"No guards match path `{path}`.")
        else:
            lines.append(f"No blocking guards for `{path}`.")

    if matched_contextual:
        lines += ["", "---", "**Contextual notes** (informational — no action required):", ""]
        for g in matched_contextual[:3]:
            layer = g.get("layer", "?")
            lines.append(f"- [layer {layer}] {g.get('claim', '')[:120]}")

    return lines


def _tool_check_guard(action: str, path: str) -> str:
    assert _maes_dir is not None
    synth_dir = _maes_dir / "synthesis"

    if not (synth_dir / _GUARDS_JSON).exists():
        return "ALLOWED\n\nNo synthesis found — run `maes sync` to compile guards."

    guards: list[dict] = _load_json(synth_dir / _GUARDS_JSON, [])
    matched_enforcement, matched_contextual = _collect_guard_matches(guards, path)

    blocking = [g for g in matched_enforcement if g.get("policy") == "block"]
    approving = [g for g in matched_enforcement
                 if g.get("policy") in ("requires-approval", "requires-checklist")]

    lines = _render_guard_verdict(blocking, approving, matched_enforcement, matched_contextual, action, path)
    return "\n".join(lines)


def _tool_list_agents() -> str:
    assert _maes_dir is not None

    agents = _load_agents(_maes_dir)

    if not agents:
        return (
            "No agents found.\n"
            "Run `maes init` to scaffold the default 6 agents, or add "
            "*.agent.yaml files to .maes/agents/."
        )

    synth_dir = _maes_dir / "synthesis"
    total_assertions = len(_load_json(synth_dir / _ASSERTIONS_JSON, []))
    total_guards = len(_load_json(synth_dir / _GUARDS_JSON, []))

    lines = [
        "## MAES Agents",
        "",
        f"Synthesis: {total_assertions} assertions, {total_guards} guards",
        "",
    ]

    for ag in agents:
        ag_id = ag.get("id", "")
        name = ag.get("name", ag_id)
        description = ag.get("description", "")
        paths = ag.get("scope", {}).get("paths", [])
        scope_str = ", ".join(f"`{p}`" for p in paths[:3]) if paths else "global"
        domains = ag.get("domains", [])

        lines.append(f"### {name}")
        lines.append(f"ID: `{ag_id}` | Scope: {scope_str}")
        if domains:
            lines.append(f"Domains: {', '.join(domains)}")
        if description:
            lines.append(description)
        lines.append("")

    lines += [
        "---",
        "Use `maes_get_agent_context` with an agent ID to get compiled context.",
        "Use `maes_check_guard` to verify an action is allowed before executing.",
    ]

    return "\n".join(lines)


# ─── maes_who_depends_on (C1 — impact graph queries) ──────────────────────────
#
# Resolves a file path to its owning architecture node (via node_files index)
# and returns forward/reverse dependency lists. When the path doesn't map to
# any node, returns a "not indexed" message with candidate suggestions instead
# of failing — agents should fall back to grep-based inspection in that case.

_MAX_RESOLVE_CANDIDATES = 5


def _classify_path_match(query: str, fn: str) -> str | None:
    if fn == query:
        return "exact"
    if query.startswith(fn + "/"):
        return "prefix"
    if fn.endswith("/" + query) or fn.endswith(query):
        return "suffix"
    return None


def _bucket_path_matches(norm: str, node_files: dict[str, list[str]]) -> tuple[list[str], list[str], list[str]]:
    exact: list[str] = []
    prefix: list[str] = []
    suffix: list[str] = []
    buckets = {"exact": exact, "prefix": prefix, "suffix": suffix}
    for key, files in node_files.items():
        for f in files:
            kind = _classify_path_match(norm, f.replace("\\", "/").strip("/"))
            if kind:
                buckets[kind].append(key)
    return exact, prefix, suffix


def _collect_candidates(*buckets: list[str]) -> list[str]:
    out: list[str] = []
    for bucket in buckets:
        for k in bucket:
            if k not in out:
                out.append(k)
            if len(out) >= _MAX_RESOLVE_CANDIDATES:
                return out
    return out


def _resolve_stable_key(path: str, node_files: dict[str, list[str]]) -> tuple[str | None, list[str]]:
    """Resolve a path to a stable_key. Returns (key_or_none, candidate_keys).

    Match strategy:
      1. Exact match against any indexed file path.
      2. Prefix match: indexed path is a directory prefix of the query.
      3. Suffix match: query is a suffix of an indexed file path.
    Returns up to 5 candidates when no unique resolution found.
    """
    norm = path.replace("\\", "/").strip("/")
    if not norm:
        return None, []

    exact, prefix, suffix = _bucket_path_matches(norm, node_files)

    if exact:
        return exact[0], []
    if len(prefix) == 1:
        return prefix[0], []
    if len(suffix) == 1:
        return suffix[0], []
    return None, _collect_candidates(exact, prefix, suffix)


_MAX_DEPS_RENDERED = 20


def _format_dep_section(title: str, keys: list[str], none_text: str) -> list[str]:
    lines = [f"### {title} ({len(keys)} nodes)"]
    if not keys:
        lines.append(none_text)
        return lines
    for k in keys[:_MAX_DEPS_RENDERED]:
        lines.append(f"- `{k}`")
    if len(keys) > _MAX_DEPS_RENDERED:
        lines.append(f"- _… {len(keys) - _MAX_DEPS_RENDERED} more_")
    return lines


def _format_not_indexed(path: str, candidates: list[str]) -> str:
    lines = [
        f"NOT_INDEXED: `{path}`",
        "",
        "This path is not in the architecture map. It may be:",
        "- A file outside MAES discovery scope",
        "- A new file added since last `maes build-arch-map`",
        "- Generated/vendored code excluded from indexing",
    ]
    if candidates:
        lines += ["", "Closest indexed nodes:"]
        for c in candidates:
            lines.append(f"- `{c}`")
    return "\n".join(lines)


def _tool_who_depends_on(path: str) -> str:
    assert _maes_dir is not None
    graph_file = _maes_dir / "synthesis" / _IMPACT_GRAPH_JSON

    if not graph_file.exists():
        return (
            "NOT_INDEXED\n\n"
            "No impact-graph.json found. Run `maes sync` to generate the "
            "dependency index. Architecture map must be built first via "
            "`maes build-arch-map`."
        )

    if not path or not path.strip():
        return "ERROR\n\nMissing required argument: path"

    graph: dict = _load_json(graph_file, {})
    node_files: dict[str, list[str]] = graph.get("node_files", {})
    forward: dict[str, list[str]] = graph.get("forward_deps", {})
    reverse: dict[str, list[str]] = graph.get("reverse_deps", {})

    stable_key, candidates = _resolve_stable_key(path, node_files)
    if stable_key is None:
        return _format_not_indexed(path, candidates)

    files = node_files.get(stable_key, [])
    lines = [
        f"## Impact for `{path}`",
        "",
        "⚠ Dependency edges are EXPERIMENTAL/heuristic (not agent_safe) — "
        "relative-import resolution may misattribute or fabricate edges and alias "
        "imports are not captured. Verify against source before relying on them.",
        "",
        f"Resolved to node: `{stable_key}`",
        f"Files in node: {len(files)}",
        "",
    ]
    lines += _format_dep_section(
        "Depends on", forward.get(stable_key, []),
        "_(no outgoing dependencies)_",
    )
    lines.append("")
    lines += _format_dep_section(
        "Depended by", reverse.get(stable_key, []),
        "_(no incoming dependencies — safe to refactor in isolation)_",
    )
    return "\n".join(lines)


# ─── MCP Server ───────────────────────────────────────────────────────────────

async def run(maes_dir: Path) -> None:
    global _maes_dir
    _maes_dir = maes_dir

    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        import mcp.types as types
    except ImportError:
        raise SystemExit(
            "mcp package not installed.\n"
            "Run: pip install mcp\n"
            "Or: pip install -r template/scripts/requirements.txt"
        )

    server = Server("maes")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="maes_get_agent_context",
                description=(
                    "Get the compiled MAES context (critical rules + project context) "
                    "for a specific agent and task. Call this at the start of any "
                    "non-trivial task to receive compliance rules, architecture "
                    "constraints, and domain knowledge relevant to what you are about "
                    "to do. Returns Markdown."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {
                            "type": "string",
                            "description": (
                                "Agent ID — use maes_list_agents to discover available "
                                "agents. Examples: maes-review, maes-analyze, "
                                "maes-context-add, maes-eval."
                            ),
                        },
                        "task_description": {
                            "type": "string",
                            "description": (
                                "What you are about to do, in plain English. "
                                "This improves which context gets selected. "
                                "Example: 'add soft-delete to payments table'"
                            ),
                        },
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "File paths being worked on. Improves path-scoped "
                                "context scoring. Example: ['src/payments/payments.service.ts']"
                            ),
                        },
                    },
                    "required": ["agent_id"],
                },
            ),
            types.Tool(
                name="maes_check_guard",
                description=(
                    "Check whether an action on a specific file path is ALLOWED, "
                    "REQUIRES_APPROVAL, or BLOCKED by active MAES guards. "
                    "Call before modifying sensitive files (migrations, auth, "
                    "financial logic, shared infrastructure). Returns status + "
                    "explanation + checklist when approval is needed."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": (
                                "What you are about to do. "
                                "Example: 'add deleted_at column' or 'modify JWT middleware'"
                            ),
                        },
                        "path": {
                            "type": "string",
                            "description": (
                                "File path or pattern being modified. "
                                "Example: 'db/migrations/0042.sql' or 'src/auth/jwt.service.ts'"
                            ),
                        },
                        "agent_id": {
                            "type": "string",
                            "description": "Optional: agent context for the check.",
                        },
                    },
                    "required": ["action", "path"],
                },
            ),
            types.Tool(
                name="maes_list_agents",
                description=(
                    "List all available MAES agents with their IDs, scope paths, "
                    "and descriptions. Use this to discover which agent_id to pass "
                    "to maes_get_agent_context."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            types.Tool(
                name="maes_who_depends_on",
                description=(
                    "Return the architecture nodes that depend on (and are "
                    "depended on by) the given file or directory path. Use "
                    "before refactoring or deleting code to understand blast "
                    "radius. Returns NOT_INDEXED with candidates when the path "
                    "is outside the architecture map."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": (
                                "File or directory path to query. "
                                "Example: 'src/auth/jwt.service.ts' or 'src/auth'"
                            ),
                        },
                    },
                    "required": ["path"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str,
        arguments: dict | None,
    ) -> list[types.TextContent]:
        args = arguments or {}
        try:
            if name == "maes_get_agent_context":
                text = _tool_get_agent_context(
                    agent_id=str(args.get("agent_id", "")),
                    task_description=str(args.get("task_description", "")),
                )
            elif name == "maes_check_guard":
                text = _tool_check_guard(
                    action=str(args.get("action", "")),
                    path=str(args.get("path", "")),
                )
            elif name == "maes_list_agents":
                text = _tool_list_agents()
            elif name == "maes_who_depends_on":
                text = _tool_who_depends_on(path=str(args.get("path", "")))
            else:
                text = f"Unknown tool: {name}"
        except Exception as exc:
            text = f"Error executing {name}: {exc}"

        return [types.TextContent(type="text", text=text)]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
