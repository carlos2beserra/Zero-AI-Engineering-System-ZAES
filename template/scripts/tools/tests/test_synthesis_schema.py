"""Schema freeze tests for V1 synthesis artifacts.

These tests pin the exact top-level keys, schema_version values, and field
types of impact-graph.json, placement-map.json, and runtime.json so that
downstream consumers (MCP tools, adapters, IDE integrations) can rely on a
stable contract.
"""

import json

from maes.compiler import (
    _build_impact_graph,
    _build_placement_map,
    _IMPACT_SCHEMA_VERSION,
    _PLACEMENT_SCHEMA_VERSION,
)
from maes.models import RuntimeContext


def _write_arch_map(tmp_path, payload):
    p = tmp_path / "architecture_map.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


# ─── impact-graph.json ────────────────────────────────────────────────────────

def test_impact_graph_schema_keys_and_types(tmp_path):
    arch = _write_arch_map(tmp_path, {
        "nodes": [
            {"stable_key": "svc.user", "type": "Service",
             "path": "src/services/user",
             "entry_points": ["src/services/user/svc.py"]},
            {"stable_key": "repo.user", "type": "Repository",
             "path": "src/repos/user"},
        ],
        "graph": {"edges": [
            {"from": "svc.user", "to": "repo.user"},
        ]},
    })
    out = _build_impact_graph(arch)
    assert isinstance(out, dict)
    assert set(out.keys()) == {
        "schema_version", "generated_at", "reliability",
        "forward_deps", "reverse_deps", "node_files", "stats",
    }
    assert out["schema_version"] == _IMPACT_SCHEMA_VERSION == "1.0"
    # V1.1 hardening: dependency edges are heuristic — machine-readable trust flags
    # must travel with the artifact agents actually consume.
    assert out["reliability"] == {
        "authoritative": False,
        "trust_level": "experimental",
        "agent_safe": False,
    }
    assert isinstance(out["generated_at"], str)
    assert out["generated_at"].endswith("Z")

    assert isinstance(out["forward_deps"], dict)
    assert isinstance(out["reverse_deps"], dict)
    assert isinstance(out["node_files"], dict)
    assert out["forward_deps"]["svc.user"] == ["repo.user"]
    assert out["reverse_deps"]["repo.user"] == ["svc.user"]
    assert out["node_files"]["svc.user"] == [
        "src/services/user", "src/services/user/svc.py"
    ]
    assert out["node_files"]["repo.user"] == ["src/repos/user"]

    stats = out["stats"]
    assert set(stats.keys()) == {"edge_count", "node_count",
                                  "max_fan_in", "max_fan_out"}
    for k, v in stats.items():
        assert isinstance(v, int), f"stats.{k} must be int"
    assert stats["edge_count"] == 1
    assert stats["node_count"] == 2


def test_impact_graph_returns_none_for_invalid(tmp_path):
    p = tmp_path / "architecture_map.json"
    p.write_text("[]", encoding="utf-8")  # list, not dict
    assert _build_impact_graph(p) is None


# ─── placement-map.json ───────────────────────────────────────────────────────

def test_placement_map_schema_keys_and_types(tmp_path):
    arch = _write_arch_map(tmp_path, {
        "nodes": [
            {"stable_key": "svc.a", "type": "Service",
             "path": "src/services/a", "file_count": 3},
            {"stable_key": "svc.b", "type": "Service",
             "path": "src/services/b", "file_count": 2},
            {"stable_key": "svc.c", "type": "Service",
             "path": "src/services/c", "file_count": 1},
        ],
        # Artifact and evidence gates are fail-closed (ADR 0009): declare a valid
        # schema and sufficient sampling so this test exercises the payload shape,
        # not one of the refusal paths.
        "schema_version": "2.1",
        "diagnostic_metrics": {"sampling_ratio": 1.0},
    })
    out = _build_placement_map(arch)
    assert isinstance(out, dict)
    assert "schema_version" in out
    assert out["schema_version"] == _PLACEMENT_SCHEMA_VERSION == "1.1"
    assert "generated_at" in out
    assert "placements" in out
    assert isinstance(out["placements"], list)

    pl = out["placements"][0]
    for required in ("category", "path", "confidence",
                     "coverage_pct", "file_count", "total_file_count"):
        assert required in pl, f"missing {required}"
    assert pl["category"] == "Service"
    assert pl["confidence"] in {"high", "medium", "low"}
    assert isinstance(pl["coverage_pct"], (int, float))
    # coverage_pct is contractually a fraction in [0, 1] (see test_placement_map).
    assert 0 <= pl["coverage_pct"] <= 1.0
    assert isinstance(pl["file_count"], int)
    assert isinstance(pl["total_file_count"], int)


def test_placement_map_returns_none_for_invalid(tmp_path):
    p = tmp_path / "architecture_map.json"
    p.write_text("\"oops\"", encoding="utf-8")
    assert _build_placement_map(p) is None


# ─── runtime.json ─────────────────────────────────────────────────────────────

_RUNTIME_REQUIRED_KEYS = {
    "test", "build", "lint", "run", "migrate",
    "test_pattern", "run_module_test",
    "last_verified", "_staleness_warning",
}


def test_runtime_to_dict_schema_keys_empty():
    d = RuntimeContext().to_dict()
    assert set(d.keys()) == _RUNTIME_REQUIRED_KEYS
    # All command fields are strings (empty by default)
    for k in _RUNTIME_REQUIRED_KEYS - {"_staleness_warning"}:
        assert isinstance(d[k], str), f"{k} must be str"
    assert isinstance(d["_staleness_warning"], bool)


def test_runtime_to_dict_schema_keys_populated():
    rt = RuntimeContext(
        test="pytest -q",
        build="pnpm build",
        lint="ruff check .",
        run="pnpm dev",
        migrate="alembic upgrade head",
        test_pattern="pytest -k {pattern}",
        run_module_test="pytest tests/{module}",
        last_verified="2026-06-02",
        staleness_warning=False,
    )
    d = rt.to_dict()
    assert set(d.keys()) == _RUNTIME_REQUIRED_KEYS
    assert d["test"] == "pytest -q"
    assert d["last_verified"] == "2026-06-02"
    assert d["_staleness_warning"] is False
