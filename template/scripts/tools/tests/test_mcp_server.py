"""Tests for maes.mcp_server — glob matching and guard behavioral tests."""

import json

import pytest
import maes.mcp_server as ms


# ─── _match_guard_path ────────────────────────────────────────────────────────


@pytest.mark.parametrize("file_path,pattern,expected", [
    # ** catches everything
    ("CLAUDE.md",                              "**",                  True),
    ("src/deep/nested/file.ts",                "**",                  True),
    # src/ prefix with **
    ("src/payments/payment.service.ts",        "src/payments/**",     True),
    ("src/payments/deep/nested/file.ts",       "src/payments/**",     True),
    ("src/auth/service.ts",                    "src/payments/**",     False),
    # **/segment/**
    ("db/migrations/0042.sql",                 "**/migrations/**",    True),
    ("project/db/migrations/add.sql",          "**/migrations/**",    True),
    ("src/migrationservice/logic.ts",          "**/migrations/**",    False),
    # **/*.ext
    ("db/schema.prisma",                       "**/*.prisma",         True),
    ("src/models/user.prisma",                 "**/*.prisma",         True),
    ("src/models/user.ts",                     "**/*.prisma",         False),
    # specific directory globs
    (".cursor/rules/maes-review.md",     ".cursor/rules/**",    True),
    (".cursor/rules/deep/nested.md",           ".cursor/rules/**",    True),
    # **/filename matches at any depth
    ("CLAUDE.md",                              "**/CLAUDE.md",        True),
    ("subdir/CLAUDE.md",                       "**/CLAUDE.md",        True),
    (".windsurfrules",                         "**/.windsurfrules",   True),
    # trailing-slash directory prefix
    (".maes/synthesis/guards.json",            ".maes/synthesis/",    True),
    ("other/guards.json",                      ".maes/synthesis/",    False),
    # broken path with spaces must never match
    ("CLAUDE.md",
     " and any change will be overwritten; context changes must be made in .maes/context/human/ ",
     False),
    # should not cross boundaries
    ("web/app/page.tsx",                       "template/**",         False),
])
def test_match_guard_path(file_path, pattern, expected):
    assert ms._match_guard_path(file_path, pattern) is expected, (
        f"_match_guard_path({file_path!r}, {pattern!r}) should be {expected}"
    )


# ─── _tool_check_guard behavioral tests ──────────────────────────────────────


@pytest.fixture(autouse=True)
def inject_maes_dir(maes_dir_with_guards):
    """Point the MCP server at the test fixture directory for every test in this module."""
    original = ms._maes_dir
    ms._maes_dir = maes_dir_with_guards
    yield
    ms._maes_dir = original


def test_check_guard_synthesis_requires_approval():
    """Fix 3: editing .maes/synthesis/ must trigger REQUIRES_APPROVAL."""
    result = ms._tool_check_guard("edit", ".maes/synthesis/assertions.json")
    assert result.startswith("REQUIRES_APPROVAL")


def test_check_guard_claude_md_requires_approval():
    """Fix 3: editing CLAUDE.md must trigger REQUIRES_APPROVAL."""
    result = ms._tool_check_guard("edit", "CLAUDE.md")
    assert result.startswith("REQUIRES_APPROVAL")


def test_check_guard_cursor_rules_requires_approval():
    """Fix 3: editing .cursor/rules/ must trigger REQUIRES_APPROVAL."""
    result = ms._tool_check_guard("edit", ".cursor/rules/maes-review.md")
    assert result.startswith("REQUIRES_APPROVAL")


def test_check_guard_windsurfrules_requires_approval():
    """Fix 3: editing .windsurfrules must trigger REQUIRES_APPROVAL."""
    result = ms._tool_check_guard("edit", ".windsurfrules")
    assert result.startswith("REQUIRES_APPROVAL")


def test_check_guard_human_context_is_allowed():
    """No false positive: .maes/context/human/ files are safe to edit freely."""
    result = ms._tool_check_guard("edit", ".maes/context/human/decisions.md")
    assert result.startswith("ALLOWED"), (
        ".maes/context/human/ should never be guarded — it is the source of truth"
    )


def test_check_guard_regular_file_is_allowed():
    result = ms._tool_check_guard("edit", "src/utils/helpers.ts")
    assert result.startswith("ALLOWED")


def test_check_guard_contextual_guard_never_blocks():
    """Contextual guards (policy=inform) must appear only as notes, never block."""
    result = ms._tool_check_guard("do_anything", "some/random/file.py")
    assert "BLOCKED" not in result
    # Contextual-only matches yield ALLOWED with informational notes appended
    first_line = result.split("\n")[0]
    assert first_line in ("ALLOWED", "REQUIRES_APPROVAL")


def test_check_guard_subdirectory_synthesis_requires_approval():
    """Guard must match files at any depth inside .maes/synthesis/."""
    result = ms._tool_check_guard("edit", ".maes/synthesis/deep/nested/file.json")
    assert result.startswith("REQUIRES_APPROVAL")


# ─── PR3: _render_arch_map_section ───────────────────────────────────────────


def test_render_arch_map_section_returns_empty_when_file_absent(tmp_path):
    result = ms._render_arch_map_section(tmp_path)
    assert result == []


def test_render_arch_map_section_returns_empty_when_nodes_list_is_empty(tmp_path):
    import json
    (tmp_path / "architecture_map.json").write_text(json.dumps({"nodes": []}))
    result = ms._render_arch_map_section(tmp_path)
    assert result == []


def test_render_arch_map_section_returns_markdown_table_with_nodes(tmp_path):
    import json
    data = {
        "nodes": [
            {"name": "auth", "path": "src/modules/auth", "type": "Service",
             "entry_points": ["POST /auth/login"]},
        ]
    }
    (tmp_path / "architecture_map.json").write_text(json.dumps(data))
    result = ms._render_arch_map_section(tmp_path)
    full = "\n".join(result)
    assert "## Architecture Map" in full
    assert "auth" in full
    assert "src/modules/auth" in full
    assert "POST /auth/login" in full


def test_render_arch_map_section_truncates_entry_points_to_two(tmp_path):
    import json
    data = {
        "nodes": [
            {"name": "api", "path": "src/api", "type": "Controller",
             "entry_points": ["GET /a", "POST /b", "DELETE /c"]},
        ]
    }
    (tmp_path / "architecture_map.json").write_text(json.dumps(data))
    result = ms._render_arch_map_section(tmp_path)
    full = "\n".join(result)
    assert "GET /a" in full
    assert "POST /b" in full
    assert "DELETE /c" not in full  # only first 2 shown

# --- Regression: list_tools inputSchema descriptions must be strings
# Trailing comma inside a parenthesized multi-line literal turns the
# description into a tuple, which makes the MCP client drop the tool.
def test_list_tools_input_schema_descriptions_are_strings(tmp_path):
    import asyncio, json
    pytest.importorskip("mcp")
    import mcp.server as mcp_server_mod

    ms._maes_dir = tmp_path / ".maes"
    ms._maes_dir.mkdir(exist_ok=True)

    captured = {}

    class _FakeServer:
        def __init__(self, *_a, **_kw): pass
        def list_tools(self):
            def deco(fn):
                captured["list_tools"] = fn
                return fn
            return deco
        def call_tool(self):
            return lambda fn: fn

    import maes.mcp_server as mod
    import mcp.server as mcp_srv
    import mcp.server.stdio as mcp_stdio

    class _DummyStdio:
        async def __aenter__(self): return (None, None)
        async def __aexit__(self, *a): return False

    orig_server = mcp_srv.Server
    orig_stdio = mcp_stdio.stdio_server
    mcp_srv.Server = _FakeServer
    mcp_stdio.stdio_server = lambda: _DummyStdio()
    try:
        async def _abort_run():
            try:
                await asyncio.wait_for(mod.run(tmp_path), timeout=0.2)
            except (asyncio.TimeoutError, Exception):
                pass
        asyncio.run(_abort_run())
    finally:
        mcp_srv.Server = orig_server
        mcp_stdio.stdio_server = orig_stdio

    fn = captured.get("list_tools")
    assert fn is not None, "list_tools handler was not registered"
    tools = asyncio.run(fn())

    for tool in tools:
        # O SDK mcp renomeou os campos de Tool para snake_case mantendo o alias
        # do wire; ler pelo alias vale nas duas versões e é o que o cliente vê.
        schema = tool.model_dump(by_alias=True).get("inputSchema")
        assert isinstance(schema, dict), f"{tool.name}: inputSchema not dict"
        json.dumps(schema)  # must be JSON-serializable
        for prop_name, prop in (schema.get("properties") or {}).items():
            desc = prop.get("description")
            if desc is not None:
                assert isinstance(desc, str), (
                    f"{tool.name}.{prop_name}: description is "
                    f"{type(desc).__name__}, expected str (trailing comma typo?)"
                )


# ─── maes_who_depends_on: experimental-trust warning at the consumer ──────────


def test_mcp_dependency_response_contains_experimental_warning(maes_dir_with_guards):
    """The final consumer (the MCP tool an agent actually calls) MUST surface that
    dependency edges are heuristic/experimental — not only the JSON artifact."""
    synth = maes_dir_with_guards / "synthesis"
    synth.mkdir(parents=True, exist_ok=True)
    (synth / "impact-graph.json").write_text(json.dumps({
        "schema_version": "1.0",
        "reliability": {"authoritative": False, "trust_level": "experimental",
                        "agent_safe": False},
        "forward_deps": {"svc.user": ["repo.user"]},
        "reverse_deps": {"repo.user": ["svc.user"]},
        "node_files": {"svc.user": ["src/services/user"],
                       "repo.user": ["src/repos/user"]},
        "stats": {"edge_count": 1, "node_count": 2, "max_fan_in": 1, "max_fan_out": 1},
    }), encoding="utf-8")

    ms._maes_dir = maes_dir_with_guards
    out = ms._tool_who_depends_on("src/services/user")
    assert "EXPERIMENTAL" in out
    assert "repo.user" in out  # still returns the data, just flagged
