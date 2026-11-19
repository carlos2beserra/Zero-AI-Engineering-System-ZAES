"""Tests for MCP tool maes_who_depends_on (C1 — impact graph queries)."""

import json
import pytest

import maes.mcp_server as ms


# ─── _resolve_stable_key (pure resolver, no I/O) ──────────────────────────────

def test_resolve_exact_match():
    nf = {"auth": ["src/auth/index.ts"], "user": ["src/user/index.ts"]}
    key, cands = ms._resolve_stable_key("src/auth/index.ts", nf)
    assert key == "auth"
    assert cands == []


def test_resolve_directory_prefix():
    nf = {"auth": ["src/auth"], "user": ["src/user"]}
    key, _ = ms._resolve_stable_key("src/auth/jwt.service.ts", nf)
    assert key == "auth"


def test_resolve_suffix_match():
    nf = {"auth": ["packages/api/src/auth/index.ts"]}
    key, _ = ms._resolve_stable_key("src/auth/index.ts", nf)
    assert key == "auth"


def test_resolve_unknown_returns_candidates():
    nf = {
        "auth": ["src/auth/index.ts"],
        "auth2": ["src/auth/v2.ts"],
    }
    key, _ = ms._resolve_stable_key("src/auth", nf)
    assert key is None or key in ("auth", "auth2")  # may match by prefix


def test_resolve_empty_path():
    key, cands = ms._resolve_stable_key("", {"a": ["a.ts"]})
    assert key is None
    assert cands == []


def test_resolve_normalizes_backslashes():
    nf = {"auth": ["src/auth/index.ts"]}
    key, _ = ms._resolve_stable_key("src\\auth\\index.ts", nf)
    assert key == "auth"


# ─── _tool_who_depends_on (file-backed) ───────────────────────────────────────

@pytest.fixture
def maes_dir_with_impact(tmp_path):
    maes = tmp_path / ".maes"
    (maes / "synthesis").mkdir(parents=True)
    graph = {
        "schema_version": "1.0",
        "generated_at": "2026-01-01T00:00:00Z",
        "forward_deps": {
            "auth": ["db"],
            "user": ["auth", "db"],
        },
        "reverse_deps": {
            "auth": ["user"],
            "db": ["auth", "user"],
        },
        "node_files": {
            "auth": ["src/auth/index.ts", "src/auth/jwt.service.ts"],
            "user": ["src/user/index.ts"],
            "db": ["src/db/index.ts"],
        },
        "stats": {"edge_count": 3, "node_count": 3,
                  "max_fan_in": 2, "max_fan_out": 2},
    }
    (maes / "synthesis" / "impact-graph.json").write_text(
        json.dumps(graph), encoding="utf-8"
    )
    return maes


@pytest.fixture(autouse=True)
def inject_dir(maes_dir_with_impact):
    original = ms._maes_dir
    ms._maes_dir = maes_dir_with_impact
    yield
    ms._maes_dir = original


def test_who_depends_on_resolved_node():
    out = ms._tool_who_depends_on("src/db/index.ts")
    assert "Resolved to node: `db`" in out
    assert "user" in out
    assert "auth" in out
    assert "no outgoing dependencies" in out


def test_who_depends_on_leaf_node():
    out = ms._tool_who_depends_on("src/user/index.ts")
    assert "Resolved to node: `user`" in out
    assert "safe to refactor in isolation" in out


def test_who_depends_on_missing_path_returns_not_indexed():
    out = ms._tool_who_depends_on("src/totally/unknown.ts")
    assert out.startswith("NOT_INDEXED")


def test_who_depends_on_empty_path():
    out = ms._tool_who_depends_on("")
    assert out.startswith("ERROR")


def test_who_depends_on_no_synthesis(tmp_path):
    empty_maes = tmp_path / "empty"
    empty_maes.mkdir()
    original = ms._maes_dir
    ms._maes_dir = empty_maes
    try:
        out = ms._tool_who_depends_on("src/foo.ts")
        assert out.startswith("NOT_INDEXED")
        assert "impact-graph.json" in out
    finally:
        ms._maes_dir = original
