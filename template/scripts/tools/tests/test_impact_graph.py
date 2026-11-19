"""Tests for _build_impact_graph (C1 — derived dependency index)."""

import json
from pathlib import Path

from maes.compiler import _build_impact_graph


def _write(p: Path, payload: object) -> Path:
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_returns_none_for_unreadable(tmp_path):
    p = _write(tmp_path / "arch.json", [])
    assert _build_impact_graph(p) is None


def test_missing_file_yields_empty_graph(tmp_path):
    # _load_json returns {} for missing files; caller (emit) gates on existence
    # so this never happens in practice but should not crash.
    out = _build_impact_graph(tmp_path / "missing.json")
    assert out is not None
    assert out["forward_deps"] == {}
    assert out["stats"]["edge_count"] == 0


def test_basic_forward_and_reverse(tmp_path):
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"stable_key": "auth", "path": "src/auth/index.ts"},
            {"stable_key": "user", "path": "src/user/index.ts"},
            {"stable_key": "db", "path": "src/db/index.ts"},
        ],
        "graph": {"edges": [
            {"from": "auth", "to": "db", "type": "import"},
            {"from": "user", "to": "db", "type": "import"},
            {"from": "user", "to": "auth", "type": "import"},
        ]},
    })
    out = _build_impact_graph(p)
    assert out is not None
    assert out["schema_version"] == "1.0"
    assert out["forward_deps"]["auth"] == ["db"]
    assert out["forward_deps"]["user"] == ["auth", "db"]
    assert out["reverse_deps"]["db"] == ["auth", "user"]
    assert out["reverse_deps"]["auth"] == ["user"]
    assert out["node_files"]["auth"] == ["src/auth/index.ts"]
    assert out["stats"]["edge_count"] == 3
    assert out["stats"]["node_count"] == 3
    assert out["stats"]["max_fan_in"] == 2
    assert out["stats"]["max_fan_out"] == 2


def test_node_files_include_entry_points(tmp_path):
    p = _write(tmp_path / "arch.json", {
        "nodes": [{
            "stable_key": "auth",
            "path": "src/auth",
            "entry_points": ["src/auth/index.ts", "src/auth/api.ts"],
        }],
        "graph": {"edges": []},
    })
    out = _build_impact_graph(p)
    assert out["node_files"]["auth"] == [
        "src/auth", "src/auth/index.ts", "src/auth/api.ts",
    ]


def test_empty_graph(tmp_path):
    p = _write(tmp_path / "arch.json", {"nodes": [], "graph": {"edges": []}})
    out = _build_impact_graph(p)
    assert out["forward_deps"] == {}
    assert out["reverse_deps"] == {}
    assert out["stats"] == {
        "edge_count": 0, "node_count": 0,
        "max_fan_in": 0, "max_fan_out": 0,
    }


def test_skips_malformed_edges(tmp_path):
    p = _write(tmp_path / "arch.json", {
        "nodes": [{"stable_key": "a", "path": "a.ts"}],
        "graph": {"edges": [
            {"from": "a", "to": "b"},
            "garbage",
            {"from": None, "to": "b"},
            {"from": "a"},  # missing to
        ]},
    })
    out = _build_impact_graph(p)
    assert out["forward_deps"] == {"a": ["b"]}
    assert out["stats"]["edge_count"] == 1


def test_determinism_sorted_outputs(tmp_path):
    p = _write(tmp_path / "arch.json", {
        "nodes": [{"stable_key": k, "path": f"{k}.ts"} for k in ("z", "a", "m")],
        "graph": {"edges": [
            {"from": "z", "to": "m"},
            {"from": "z", "to": "a"},
        ]},
    })
    out = _build_impact_graph(p)
    assert list(out["forward_deps"].keys()) == ["z"]
    assert out["forward_deps"]["z"] == ["a", "m"]
    assert list(out["node_files"].keys()) == ["a", "m", "z"]
