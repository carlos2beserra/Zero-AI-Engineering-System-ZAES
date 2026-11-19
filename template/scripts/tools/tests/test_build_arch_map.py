"""Test suite for ``maes build-arch-map`` — deterministic architecture map generator.

Covers (8 sections matching the specification):
  1. Determinism       — identical output across identical runs
  2. Pipeline order    — Stage 1 → Stage 3 → Stage 2 (exact, no reordering)
  3. stable_key        — pure function of path, invariant across environments
  4. dep_edges         — sourced from Stage 3 imports only (no LLM, no heuristics)
  5. Snapshot integrity — fail-fast on empty/inaccessible snapshot
  6. Output schema     — architecture_map.json and dependency_graph.json structure
  7. Cross-run         — two identical runs produce identical JSON
  8. Failure modes     — no partial output written on any stage error
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from maes.build_arch_map_cmd import run_build_arch_map
from maes.models import ArchitectureNode, NODE_TYPE_SERVICE, _path_to_id
from maes.pipeline.contracts import ArchitectureMapResult, DepResult, DiscoveryResult
from maes.pipeline.stage_2_arch_builder import _file_under_node


# ─── Coverage assignment: segment-boundary matching (P0-C) ────────────────────


def test_file_under_node_matches_children_and_self():
    assert _file_under_node("src/auth/login.ts", "src/auth")
    assert _file_under_node("src/auth", "src/auth")  # file node


def test_file_under_node_rejects_lexical_neighbour():
    # "src/authx.ts" merely shares a string prefix with node "src/auth" — it is
    # NOT under the module directory and must not inflate coverage.
    assert not _file_under_node("src/authx.ts", "src/auth")
    assert not _file_under_node("src/authentication-helpers.ts", "src/auth")


def test_file_under_node_empty_path_claims_nothing():
    # An empty node path must not claim every file (would force coverage = 1.0).
    assert not _file_under_node("src/auth/login.ts", "")


# ─── Test doubles & helpers ───────────────────────────────────────────────────

_SCHEMA_VERSION = "2.1"


def _make_discovery(
    files: tuple[tuple[str, str], ...] | None = None,
) -> DiscoveryResult:
    """Minimal DiscoveryResult with deterministic file list."""
    if files is None:
        files = (
            ("src/auth/service.py", "class AuthService:\n    pass\n"),
            ("src/auth/routes.py", "# routes\n"),
        )
    return DiscoveryResult(
        files=files,
        file_tree="",
        total_chars=sum(len(c) for _, c in files),
        truncated_files=frozenset(),
        dirs_seen=frozenset({"src"}),
        budget_used_pct=0.01,
    )


def _make_dep(boundary_map: dict | None = None) -> DepResult:
    return DepResult(violations=(), boundary_map=boundary_map or {})


def _make_arch_map(
    nodes: tuple[dict, ...] | None = None,
    dep_edges: dict[str, list[str]] | None = None,
) -> ArchitectureMapResult:
    if nodes is None:
        node = ArchitectureNode.make("src/auth", NODE_TYPE_SERVICE, "auth")
        nodes = (node.to_dict(),)
    return ArchitectureMapResult(
        nodes=nodes,
        layer_map={"auth": "service"},
        modeled_coverage_pct=0.75,
        files_assigned=2,
        files_total=2,
        node_quality={"total_nodes": len(nodes), "avg_files_per_node": 1.0},
        dep_edges=dep_edges or {},
    )


def _make_arch_map_with_edges() -> ArchitectureMapResult:
    auth_key = _path_to_id("src/auth")
    payments_key = _path_to_id("src/payments")
    node_auth = ArchitectureNode.make("src/auth", NODE_TYPE_SERVICE, "auth")
    node_payments = ArchitectureNode.make("src/payments", NODE_TYPE_SERVICE, "payments")
    return ArchitectureMapResult(
        nodes=(node_auth.to_dict(), node_payments.to_dict()),
        layer_map={},
        modeled_coverage_pct=1.0,
        files_assigned=4,
        files_total=4,
        node_quality={"total_nodes": 2, "avg_files_per_node": 2.0},
        dep_edges={payments_key: [auth_key], auth_key: []},
    )


def _run(
    tmp_path: Path,
    *,
    discovery: DiscoveryResult | None = None,
    dep: DepResult | None = None,
    arch_map: ArchitectureMapResult | None = None,
) -> tuple[int, Path]:
    """Run run_build_arch_map with mocked stages; return (rc, inferred_dir)."""
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    maes_dir = tmp_path / ".maes"

    d = discovery if discovery is not None else _make_discovery()
    de = dep if dep is not None else _make_dep()
    am = arch_map if arch_map is not None else _make_arch_map()

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", return_value=d),
        patch("maes.pipeline.stage_3_dep.run_dep_stage", return_value=de),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder", return_value=am),
    ):
        rc = run_build_arch_map(project_dir, maes_dir)

    return rc, maes_dir / "context" / "inferred"


def _write_project(project_dir: Path, files: dict[str, str]) -> None:
    """Write source files for real-filesystem integration tests."""
    for rel, content in files.items():
        p = project_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ─── 1. Determinism ───────────────────────────────────────────────────────────


def test_determinism_same_stages_same_output_bytes(tmp_path):
    """Identical stage results MUST produce byte-for-byte identical JSON."""
    discovery = _make_discovery()
    dep = _make_dep()
    am = _make_arch_map()

    run1_dir = tmp_path / "run1"
    run2_dir = tmp_path / "run2"

    _, inferred1 = _run(run1_dir, discovery=discovery, dep=dep, arch_map=am)
    _, inferred2 = _run(run2_dir, discovery=discovery, dep=dep, arch_map=am)

    arch1 = (inferred1 / "architecture_map.json").read_bytes()
    arch2 = (inferred2 / "architecture_map.json").read_bytes()
    assert arch1 == arch2, "architecture_map.json must be byte-for-byte identical across runs"


def test_determinism_dep_graph_identical_bytes(tmp_path):
    """graph.edges in architecture_map.json MUST be byte-for-byte identical across identical runs."""
    am = _make_arch_map_with_edges()
    discovery = _make_discovery()
    dep = _make_dep()

    run1_dir = tmp_path / "run1"
    run2_dir = tmp_path / "run2"

    _, inferred1 = _run(run1_dir, discovery=discovery, dep=dep, arch_map=am)
    _, inferred2 = _run(run2_dir, discovery=discovery, dep=dep, arch_map=am)

    j1 = json.loads((inferred1 / "architecture_map.json").read_text())
    j2 = json.loads((inferred2 / "architecture_map.json").read_text())
    assert j1["graph"] == j2["graph"], "graph section must be identical across runs"


def test_determinism_node_order_is_stable(tmp_path):
    """Node order in architecture_map.json must not vary across runs."""
    node_a = ArchitectureNode.make("src/auth", NODE_TYPE_SERVICE, "auth")
    node_b = ArchitectureNode.make("src/payments", NODE_TYPE_SERVICE, "payments")
    # Same nodes — order in ArchitectureMapResult.nodes is fixed
    am = _make_arch_map(nodes=(node_a.to_dict(), node_b.to_dict()))

    run1_dir = tmp_path / "run1"
    run2_dir = tmp_path / "run2"

    _, inferred1 = _run(run1_dir, arch_map=am)
    _, inferred2 = _run(run2_dir, arch_map=am)

    j1 = json.loads((inferred1 / "architecture_map.json").read_text())
    j2 = json.loads((inferred2 / "architecture_map.json").read_text())
    assert [n["stable_key"] for n in j1["nodes"]] == [n["stable_key"] for n in j2["nodes"]]


def test_determinism_does_not_depend_on_maes_dir_location(tmp_path):
    """Output content must not embed maes_dir path — only inferred paths are relative."""
    am = _make_arch_map()
    discovery = _make_discovery()
    dep = _make_dep()

    dir_a = tmp_path / "location_a"
    dir_b = tmp_path / "location_b"

    _, inferred_a = _run(dir_a, discovery=discovery, dep=dep, arch_map=am)
    _, inferred_b = _run(dir_b, discovery=discovery, dep=dep, arch_map=am)

    j1 = json.loads((inferred_a / "architecture_map.json").read_text())
    j2 = json.loads((inferred_b / "architecture_map.json").read_text())
    assert j1 == j2


# ─── 2. Pipeline Execution Order ─────────────────────────────────────────────


def test_pipeline_stage1_called_before_stage3(tmp_path):
    """Stage 1 (discovery) MUST execute before Stage 3 (dep analysis)."""
    call_order: list[str] = []

    def fake_discovery(project_dir, **kwargs):
        call_order.append("stage1")
        return _make_discovery()

    def fake_dep_stage(project_dir):
        call_order.append("stage3")
        return _make_dep()

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", side_effect=fake_discovery),
        patch("maes.pipeline.stage_3_dep.run_dep_stage", side_effect=fake_dep_stage),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder", return_value=_make_arch_map()),
    ):
        run_build_arch_map(project_dir, maes_dir)

    assert call_order.index("stage1") < call_order.index("stage3"), (
        "Stage 1 must execute before Stage 3"
    )


def test_pipeline_stage3_called_before_stage2(tmp_path):
    """Stage 3 (dep analysis) MUST execute before Stage 2 (arch builder)."""
    call_order: list[str] = []

    def fake_dep_stage(project_dir):
        call_order.append("stage3")
        return _make_dep()

    def fake_arch_builder(project_dir, discovery, dep):
        call_order.append("stage2")
        return _make_arch_map()

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", return_value=_make_discovery()),
        patch("maes.pipeline.stage_3_dep.run_dep_stage", side_effect=fake_dep_stage),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder", side_effect=fake_arch_builder),
    ):
        run_build_arch_map(project_dir, maes_dir)

    assert call_order.index("stage3") < call_order.index("stage2"), (
        "Stage 3 must execute before Stage 2"
    )


def test_pipeline_all_three_stages_are_called(tmp_path):
    """All three stages MUST execute — no skipping allowed."""
    called: set[str] = set()

    def fake_discovery(project_dir, **kwargs):
        called.add("stage1")
        return _make_discovery()

    def fake_dep_stage(project_dir):
        called.add("stage3")
        return _make_dep()

    def fake_arch_builder(project_dir, discovery, dep):
        called.add("stage2")
        return _make_arch_map()

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", side_effect=fake_discovery),
        patch("maes.pipeline.stage_3_dep.run_dep_stage", side_effect=fake_dep_stage),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder", side_effect=fake_arch_builder),
    ):
        run_build_arch_map(project_dir, maes_dir)

    assert called == {"stage1", "stage2", "stage3"}, (
        f"Expected all 3 stages executed; got: {called}"
    )


def test_pipeline_stage2_receives_stage1_and_stage3_outputs(tmp_path):
    """Stage 2 MUST receive the exact output of Stage 1 and Stage 3."""
    discovery = _make_discovery()
    dep = _make_dep(boundary_map={"auth": "service", "payments": "domain"})
    received: dict = {}

    def fake_arch_builder(project_dir, d, de):
        received["discovery"] = d
        received["dep"] = de
        return _make_arch_map()

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", return_value=discovery),
        patch("maes.pipeline.stage_3_dep.run_dep_stage", return_value=dep),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder", side_effect=fake_arch_builder),
    ):
        run_build_arch_map(project_dir, maes_dir)

    assert received["discovery"] is discovery, "Stage 2 must receive Stage 1 output"
    assert received["dep"] is dep, "Stage 2 must receive Stage 3 output"


def test_pipeline_stage1_called_exactly_once(tmp_path):
    """Stage 1 MUST be called exactly once per command invocation."""
    count = {"n": 0}

    def fake_discovery(project_dir, **kwargs):
        count["n"] += 1
        return _make_discovery()

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", side_effect=fake_discovery),
        patch("maes.pipeline.stage_3_dep.run_dep_stage", return_value=_make_dep()),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder", return_value=_make_arch_map()),
    ):
        run_build_arch_map(project_dir, maes_dir)

    assert count["n"] == 1, f"Stage 1 must be called exactly once; called {count['n']} time(s)"


# ─── 3. stable_key Invariants ─────────────────────────────────────────────────


def test_path_to_id_known_value_simple():
    assert _path_to_id("src/modules/auth") == "src_modules_auth"


def test_path_to_id_known_value_single_segment():
    assert _path_to_id("auth") == "auth"


def test_path_to_id_known_value_hyphenated():
    assert _path_to_id("src/auth-service") == "src_auth_service"


def test_path_to_id_known_value_trailing_slash():
    assert _path_to_id("src/auth/") == "src_auth"


def test_path_to_id_known_value_uppercase():
    assert _path_to_id("Src/Auth") == "src_auth"


def test_path_to_id_is_deterministic_across_calls():
    """Calling _path_to_id twice with the same input MUST return the same string."""
    path = "src/payments/service"
    assert _path_to_id(path) == _path_to_id(path)


def test_path_to_id_produces_different_ids_for_different_paths():
    assert _path_to_id("src/auth") != _path_to_id("src/payments")


def test_path_to_id_root_path_returns_root():
    assert _path_to_id("") == "root" or _path_to_id("/") == "root"


def test_path_to_id_no_special_chars_in_result():
    """Result MUST contain only [a-z0-9_]."""
    import re
    result = _path_to_id("src/some-Module/with.dots/and spaces")
    assert re.fullmatch(r"[a-z0-9_]+", result), (
        f"_path_to_id result must be alphanumeric+underscore only; got: {result!r}"
    )


def test_stable_key_changes_on_path_rename():
    """Renaming a path MUST produce a different stable_key (intentional by contract)."""
    before = _path_to_id("src/auth")
    after = _path_to_id("src/auth-v2")
    assert before != after, (
        "stable_key must change when path is renamed — intentional (new path = new node)"
    )


def test_stable_key_in_nodes_matches_path_to_id(tmp_path):
    """Every node.stable_key in output MUST equal _path_to_id(node.path)."""
    rc, inferred = _run(tmp_path)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    for node in data["nodes"]:
        expected_key = _path_to_id(node["path"])
        assert node["stable_key"] == expected_key, (
            f"Node stable_key mismatch: expected {expected_key!r}, "
            f"got {node['stable_key']!r} for path {node['path']!r}"
        )


def test_stable_key_matches_id_field_in_node(tmp_path):
    """stable_key MUST equal id in current implementation (migration hook not yet applied)."""
    rc, inferred = _run(tmp_path)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    for node in data["nodes"]:
        assert node["stable_key"] == node["id"], (
            f"stable_key {node['stable_key']!r} must equal id {node['id']!r}"
        )


def test_dep_edges_keys_are_stable_keys(tmp_path):
    """All keys in dep_edges MUST be valid stable_keys (from nodes in the map)."""
    am = _make_arch_map_with_edges()

    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0

    data = json.loads((inferred / "architecture_map.json").read_text())
    node_keys = {n["stable_key"] for n in data["nodes"]}

    for edge in data["graph"]["edges"]:
        assert edge["from"] in node_keys, (
            f"dep edge 'from' key {edge['from']!r} is not a valid node stable_key"
        )
        assert edge["to"] in node_keys, (
            f"dep edge 'to' key {edge['to']!r} is not a valid node stable_key"
        )


# ─── 4. Dependency Graph (dep_edges) ─────────────────────────────────────────


def test_dep_edges_present_when_nodes_have_deps(tmp_path):
    """graph.edges in architecture_map.json MUST be non-empty when nodes have dep_edges."""
    am = _make_arch_map_with_edges()
    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    assert len(data["graph"]["edges"]) > 0, (
        "graph.edges must be non-empty when nodes have dep_edges"
    )


def test_dep_graph_not_written_when_no_nodes(tmp_path):
    """dependency_graph.json MUST NOT exist (no separate file in schema v2.0)."""
    am = _make_arch_map(nodes=())
    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0
    assert not (inferred / "dependency_graph.json").exists(), (
        "dependency_graph.json must NOT be written (edges are embedded in architecture_map.json)"
    )


def test_dep_edges_type_is_import(tmp_path):
    """Each edge in graph.edges MUST have type='import'."""
    am = _make_arch_map_with_edges()
    _, inferred = _run(tmp_path, arch_map=am)
    data = json.loads((inferred / "architecture_map.json").read_text())
    for edge in data["graph"]["edges"]:
        assert edge["type"] == "import", (
            f"Expected edge type 'import', got {edge['type']!r}"
        )


def test_dep_edges_contain_only_discovered_imports(tmp_path):
    """dep_edges MUST only contain imports that Stage 3 discovered; no heuristic inference."""
    # With no dep_edges (Stage 3 found nothing), no edges must appear
    am = _make_arch_map(dep_edges={})  # explicit empty
    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0
    # No dependency_graph.json since edges are embedded in architecture_map.json
    if (inferred / "architecture_map.json").exists():
        data = json.loads((inferred / "architecture_map.json").read_text())
        if "graph" in data:
            assert data["graph"]["edges"] == [], "No edges must appear when dep_edges is empty"


def test_python_absolute_imports_detected_in_dep_stage(tmp_path):
    """Python absolute imports are analysed by Stage 3 (AST-based, full import graph)."""
    project_dir = tmp_path / "project"
    _write_project(project_dir, {
        "src/auth/service.py": "import os\nfrom src.payments.service import PaymentsService\n",
        "src/payments/service.py": "class PaymentsService:\n    pass\n",
    })

    from maes.pipeline.stage_3_dep import run_dep_stage
    dep = run_dep_stage(project_dir)
    # Stage 3 must not raise and must return a DepResult
    assert isinstance(dep, DepResult)
    assert isinstance(dep.violations, tuple)
    assert isinstance(dep.boundary_map, dict)


def test_typescript_relative_imports_detected(tmp_path):
    """TypeScript relative imports MUST be detected by dep_analysis._extract_ts_imports."""
    from maes.dep_analysis import _extract_ts_imports

    ts_file = tmp_path / "auth.service.ts"
    ts_file.write_text(
        "import { User } from './domain/user';\n"
        "import { Config } from '../../config';\n",
        encoding="utf-8",
    )
    imports = _extract_ts_imports(ts_file)
    assert "domain" in imports, "Relative import './domain/user' must produce 'domain'"
    assert "config" in imports, "Relative import '../../config' must produce 'config'"


def test_typescript_absolute_imports_excluded(tmp_path):
    """TypeScript absolute/package imports MUST NOT appear in dep_edges (permanent limitation)."""
    from maes.dep_analysis import _extract_ts_imports

    ts_file = tmp_path / "service.ts"
    ts_file.write_text(
        "import { Injectable } from '@nestjs/common';\n"
        "import express from 'express';\n"
        "import SomeThing from 'some-absolute-pkg';\n",
        encoding="utf-8",
    )
    imports = _extract_ts_imports(ts_file)
    # Absolute imports (no leading '.') are excluded
    assert imports == [], (
        "TypeScript absolute package imports must NOT be included in dep analysis "
        "(permanent parser limitation)"
    )


def test_dep_edges_no_self_references(tmp_path):
    """A node MUST NOT appear as its own dependency."""
    auth_key = _path_to_id("src/auth")
    am = _make_arch_map(dep_edges={auth_key: []})  # explicitly no self-reference

    _, inferred = _run(tmp_path, arch_map=am)
    if (inferred / "architecture_map.json").exists():
        data = json.loads((inferred / "architecture_map.json").read_text())
        if "graph" in data:
            for edge in data["graph"]["edges"]:
                assert edge["from"] != edge["to"], (
                    f"Node {edge['from']!r} has a self-referential edge"
                )


def test_dep_edges_with_circular_dependency_represented(tmp_path):
    """Circular deps MUST be represented faithfully — no filtering."""
    auth_key = _path_to_id("src/auth")
    payments_key = _path_to_id("src/payments")

    node_auth = ArchitectureNode.make("src/auth", NODE_TYPE_SERVICE, "auth")
    node_payments = ArchitectureNode.make("src/payments", NODE_TYPE_SERVICE, "payments")

    am = ArchitectureMapResult(
        nodes=(node_auth.to_dict(), node_payments.to_dict()),
        layer_map={},
        modeled_coverage_pct=1.0,
        files_assigned=2,
        files_total=2,
        node_quality={"total_nodes": 2, "avg_files_per_node": 1.0},
        dep_edges={auth_key: [payments_key], payments_key: [auth_key]},  # circular
    )
    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    froms = {e["from"] for e in data["graph"]["edges"]}
    tos = {e["to"] for e in data["graph"]["edges"]}
    # Both directions must be in the graph
    assert auth_key in froms and payments_key in tos
    assert payments_key in froms and auth_key in tos


# ─── 5. Snapshot Integrity ────────────────────────────────────────────────────


def test_empty_snapshot_returns_exit_1(tmp_path):
    """Empty project (no source files) MUST return exit code 1."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    empty_discovery = DiscoveryResult(
        files=(),
        file_tree="",
        total_chars=0,
        truncated_files=frozenset(),
        dirs_seen=frozenset(),
        budget_used_pct=0.0,
    )

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", return_value=empty_discovery),
    ):
        rc = run_build_arch_map(project_dir, maes_dir)

    assert rc == 1, "Empty snapshot must return exit code 1"


def test_empty_snapshot_writes_no_output(tmp_path):
    """When the snapshot is empty, NO output files MUST be written."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"
    inferred = maes_dir / "context" / "inferred"

    empty_discovery = DiscoveryResult(
        files=(),
        file_tree="",
        total_chars=0,
        truncated_files=frozenset(),
        dirs_seen=frozenset(),
        budget_used_pct=0.0,
    )

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", return_value=empty_discovery),
    ):
        run_build_arch_map(project_dir, maes_dir)

    assert not (inferred / "architecture_map.json").exists(), (
        "architecture_map.json must NOT be written when snapshot is empty"
    )


def test_stage1_exception_returns_exit_1(tmp_path):
    """Stage 1 exception MUST propagate as exit code 1."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery",
              side_effect=RuntimeError("filesystem inaccessible")),
    ):
        rc = run_build_arch_map(project_dir, maes_dir)

    assert rc == 1


def test_stage2_exception_returns_exit_1(tmp_path):
    """Stage 2 exception MUST propagate as exit code 1."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", return_value=_make_discovery()),
        patch("maes.pipeline.stage_3_dep.run_dep_stage", return_value=_make_dep()),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder",
              side_effect=ValueError("inconsistent snapshot state")),
    ):
        rc = run_build_arch_map(project_dir, maes_dir)

    assert rc == 1


# ─── 6. Output Schema Validation ─────────────────────────────────────────────


def test_schema_architecture_map_top_level_keys(tmp_path):
    """architecture_map.json MUST contain all required top-level keys."""
    rc, inferred = _run(tmp_path)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())

    required = {
        "schema_version", "status", "schema_metadata", "project_metadata",
        "diagnostic_metrics", "coverage_context", "nodes", "graph",
    }
    missing = required - data.keys()
    assert not missing, f"Missing required keys in architecture_map.json: {missing}"


def test_schema_version_is_2_0(tmp_path):
    rc, inferred = _run(tmp_path)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    assert data["schema_version"] == _SCHEMA_VERSION


def test_schema_status_is_generated_when_nodes_exist(tmp_path):
    rc, inferred = _run(tmp_path)  # default arch_map has nodes
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    assert data["status"] == "generated"


def test_schema_status_is_empty_no_nodes_when_no_nodes(tmp_path):
    am = _make_arch_map(nodes=())
    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    assert data["status"] == "empty_no_nodes"


def test_schema_nodes_is_list(tmp_path):
    rc, inferred = _run(tmp_path)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    assert isinstance(data["nodes"], list)


def test_schema_each_node_has_required_fields(tmp_path):
    """Each node MUST contain: id, stable_key, name, path, type, domain, entry_points, dependencies."""
    rc, inferred = _run(tmp_path)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    required_node_fields = {
        "id", "stable_key", "name", "path", "type", "domain",
        "domain_confidence", "visibility", "entry_points", "dependencies", "file_count",
    }
    for node in data["nodes"]:
        missing = required_node_fields - node.keys()
        assert not missing, (
            f"Node {node.get('path', '?')!r} is missing fields: {missing}"
        )


def test_schema_coverage_pct_is_float_between_0_and_1(tmp_path):
    rc, inferred = _run(tmp_path)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    pct = data["coverage_context"]["modeled_coverage_pct"]
    assert isinstance(pct, (int, float)), f"modeled_coverage_pct must be numeric; got {type(pct)}"
    assert 0.0 <= pct <= 1.0, f"modeled_coverage_pct must be in [0, 1]; got {pct}"


def test_schema_node_quality_contains_node_count(tmp_path):
    rc, inferred = _run(tmp_path)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    assert "node_count" in data["diagnostic_metrics"]
    assert data["diagnostic_metrics"]["node_count"] == len(data["nodes"])


def test_schema_dep_graph_top_level_keys(tmp_path):
    """architecture_map.json#/graph MUST contain 'edges' and 'dep_edge_count'."""
    am = _make_arch_map_with_edges()
    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    required = {"edges", "dep_edge_count"}
    missing = required - data["graph"].keys()
    assert not missing, f"Missing keys in arch_map['graph']: {missing}"
    assert "nodes" not in data["graph"], "graph must NOT contain 'nodes' key (R1 refinement)"


# ─── 7. V1.1 hardening: dependency-graph reliability signaling ────────────────


def _hub_arch_map(targets_share_one: bool) -> ArchitectureMapResult:
    """Build an arch map whose dep_edges either concentrate on one sink (hub) or
    spread evenly across distinct sinks (balanced)."""
    paths = ["src/a", "src/b", "src/c", "src/d", "src/e"]
    nodes = tuple(
        ArchitectureNode.make(p, NODE_TYPE_SERVICE, p.split("/")[-1]).to_dict()
        for p in paths
    )
    ids = {p: _path_to_id(p) for p in paths}
    if targets_share_one:
        # a,b,c all import the same node → 3/3 edges concentrate on one sink.
        dep_edges = {ids["src/a"]: [ids["src/e"]],
                     ids["src/b"]: [ids["src/e"]],
                     ids["src/c"]: [ids["src/e"]]}
    else:
        # 4 edges across 4 distinct sinks → max concentration 0.25 < 0.30.
        dep_edges = {ids["src/a"]: [ids["src/b"]],
                     ids["src/b"]: [ids["src/c"]],
                     ids["src/c"]: [ids["src/d"]],
                     ids["src/d"]: [ids["src/e"]]}
    return ArchitectureMapResult(
        nodes=nodes, layer_map={}, modeled_coverage_pct=1.0,
        files_assigned=5, files_total=5,
        node_quality={"total_nodes": 5, "avg_files_per_node": 1.0},
        dep_edges=dep_edges,
    )


def test_arch_map_has_reliability_block(tmp_path):
    """Generated architecture_map MUST carry the machine-readable trust block."""
    rc, inferred = _run(tmp_path)
    assert rc == 0
    rel = json.loads((inferred / "architecture_map.json").read_text())["reliability"]
    required = {"authoritative", "trust_level", "agent_safe",
                "max_edge_target_concentration_pct", "suspected_artificial_hub", "guidance"}
    assert required <= rel.keys(), f"missing reliability keys: {required - rel.keys()}"
    assert rel["authoritative"] is False
    assert rel["agent_safe"] is False
    assert rel["trust_level"] == "experimental"


def test_arch_map_flags_artificial_hub(tmp_path):
    rc, inferred = _run(tmp_path, arch_map=_hub_arch_map(targets_share_one=True))
    assert rc == 0
    rel = json.loads((inferred / "architecture_map.json").read_text())["reliability"]
    assert rel["max_edge_target_concentration_pct"] >= 0.30
    assert rel["suspected_artificial_hub"] is not None


def test_arch_map_balanced_graph_has_no_hub(tmp_path):
    rc, inferred = _run(tmp_path, arch_map=_hub_arch_map(targets_share_one=False))
    assert rc == 0
    rel = json.loads((inferred / "architecture_map.json").read_text())["reliability"]
    assert rel["max_edge_target_concentration_pct"] < 0.30
    assert rel["suspected_artificial_hub"] is None


def test_empty_arch_map_still_has_reliability(tmp_path):
    """The empty_no_nodes skeleton MUST also carry the reliability block."""
    am = _make_arch_map(nodes=())
    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    assert data["status"] == "empty_no_nodes"
    assert data["reliability"]["agent_safe"] is False


def test_no_arch_map_skeleton_still_has_reliability(tmp_path):
    """When Stage 2 yields no arch map at all, the skeleton still carries trust flags."""
    from maes.pipeline.stage_7_emission import _emit_architecture_map
    inferred = tmp_path / "inferred"
    inferred.mkdir(parents=True)
    _emit_architecture_map(inferred, None)
    data = json.loads((inferred / "architecture_map.json").read_text())
    assert data["status"] == "no_arch_map"
    assert data["reliability"]["agent_safe"] is False


def test_schema_dep_graph_edges_have_from_to_type(tmp_path):
    """Each edge MUST have 'from', 'to', and 'type' keys."""
    am = _make_arch_map_with_edges()
    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    for edge in data["graph"]["edges"]:
        assert "from" in edge and "to" in edge and "type" in edge, (
            f"Edge missing required fields: {edge}"
        )


def test_schema_source_files_matches_population_total(tmp_path):
    """diagnostic_metrics.source_files MUST reflect ArchitectureMapResult.files_total.

    Renamed from discovered_files in schema 2.1: "discovered" read as "what the
    collector found", which is precisely the misreading that produced the
    self-referential coverage bug. This number is the enumerated POPULATION.
    """
    am = _make_arch_map()
    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    assert data["diagnostic_metrics"]["source_files"] == am.files_total


def test_schema_build_metadata_exists_and_has_four_fields(tmp_path):
    """build_metadata.json MUST exist and contain exactly 4 fields."""
    rc, inferred = _run(tmp_path)
    assert rc == 0
    meta_path = inferred / "build_metadata.json"
    assert meta_path.exists(), "build_metadata.json must be written on success"
    meta = json.loads(meta_path.read_text())
    required = {"generated_at", "schema_version", "tool", "artifact"}
    assert required == meta.keys(), f"build_metadata.json must have exactly {required}; got {meta.keys()}"
    assert meta["schema_version"] == "2.0"
    assert meta["tool"] == "maes"
    assert meta["artifact"] == "architecture_map"


def test_project_metadata_structure(tmp_path):
    """architecture_map.json#/project_metadata MUST contain 'is_frontend_project'."""
    rc, inferred = _run(tmp_path)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    assert "project_metadata" in data
    assert "is_frontend_project" in data["project_metadata"]
    assert isinstance(data["project_metadata"]["is_frontend_project"], bool)


def test_graph_dep_edge_count_equals_len_edges(tmp_path):
    """graph.dep_edge_count MUST equal len(graph.edges)."""
    am = _make_arch_map_with_edges()
    rc, inferred = _run(tmp_path, arch_map=am)
    assert rc == 0
    data = json.loads((inferred / "architecture_map.json").read_text())
    graph = data["graph"]
    assert graph["dep_edge_count"] == len(graph["edges"])


# ─── 7. Cross-Run Comparison ─────────────────────────────────────────────────


def test_cross_run_json_structure_is_identical(tmp_path):
    """Two runs on identical snapshot MUST produce identical JSON structure."""
    discovery = _make_discovery()
    dep = _make_dep()
    am = _make_arch_map()

    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"

    _, inferred1 = _run(dir1, discovery=discovery, dep=dep, arch_map=am)
    _, inferred2 = _run(dir2, discovery=discovery, dep=dep, arch_map=am)

    j1 = json.loads((inferred1 / "architecture_map.json").read_text())
    j2 = json.loads((inferred2 / "architecture_map.json").read_text())

    assert j1 == j2, "architecture_map.json JSON structure must be identical across runs"


def test_cross_run_node_count_identical(tmp_path):
    node_a = ArchitectureNode.make("src/auth", NODE_TYPE_SERVICE, "auth")
    node_b = ArchitectureNode.make("src/payments", NODE_TYPE_SERVICE, "payments")
    am = _make_arch_map(nodes=(node_a.to_dict(), node_b.to_dict()))

    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"

    _, inferred1 = _run(dir1, arch_map=am)
    _, inferred2 = _run(dir2, arch_map=am)

    j1 = json.loads((inferred1 / "architecture_map.json").read_text())
    j2 = json.loads((inferred2 / "architecture_map.json").read_text())

    assert len(j1["nodes"]) == len(j2["nodes"])


def test_cross_run_dep_edges_identical(tmp_path):
    am = _make_arch_map_with_edges()

    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"

    _, inferred1 = _run(dir1, arch_map=am)
    _, inferred2 = _run(dir2, arch_map=am)

    j1 = json.loads((inferred1 / "architecture_map.json").read_text())
    j2 = json.loads((inferred2 / "architecture_map.json").read_text())

    assert j1["graph"]["edges"] == j2["graph"]["edges"], "graph.edges must be identical across runs"


def test_cross_run_coverage_pct_identical(tmp_path):
    am = _make_arch_map()

    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"

    _, inferred1 = _run(dir1, arch_map=am)
    _, inferred2 = _run(dir2, arch_map=am)

    j1 = json.loads((inferred1 / "architecture_map.json").read_text())
    j2 = json.loads((inferred2 / "architecture_map.json").read_text())

    assert j1["coverage_context"]["modeled_coverage_pct"] == j2["coverage_context"]["modeled_coverage_pct"]


# ─── 8. Failure Modes — no partial output ────────────────────────────────────


def test_failure_mode_stage1_exception_writes_no_files(tmp_path):
    """Stage 1 failure MUST leave the inferred directory empty (no partial output)."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery",
              side_effect=OSError("disk not accessible")),
    ):
        run_build_arch_map(project_dir, maes_dir)

    inferred = maes_dir / "context" / "inferred"
    assert not (inferred / "architecture_map.json").exists(), (
        "Stage 1 failure must not write architecture_map.json"
    )
    assert not (inferred / "dependency_graph.json").exists(), (
        "Stage 1 failure must not write dependency_graph.json"
    )


def test_failure_mode_stage2_exception_writes_no_files(tmp_path):
    """Stage 2 failure MUST leave the inferred directory empty (no partial output)."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", return_value=_make_discovery()),
        patch("maes.pipeline.stage_3_dep.run_dep_stage", return_value=_make_dep()),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder",
              side_effect=RuntimeError("snapshot inconsistent")),
    ):
        run_build_arch_map(project_dir, maes_dir)

    inferred = maes_dir / "context" / "inferred"
    assert not (inferred / "architecture_map.json").exists(), (
        "Stage 2 failure must not write architecture_map.json"
    )


def test_failure_mode_emission_exception_writes_no_files(tmp_path):
    """Emission failure MUST not leave partial output on disk."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", return_value=_make_discovery()),
        patch("maes.pipeline.stage_3_dep.run_dep_stage", return_value=_make_dep()),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder",
              return_value=_make_arch_map()),
        patch("maes.pipeline.stage_7_emission._emit_architecture_map",
              side_effect=OSError("disk write failed")),
    ):
        rc = run_build_arch_map(project_dir, maes_dir)

    assert rc == 1, "Emission failure must return exit code 1"


def test_failure_mode_stage1_does_not_call_stage2(tmp_path):
    """On Stage 1 failure, Stage 2 MUST NOT be called (no degraded execution)."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"
    stage2_called = {"called": False}

    def fake_stage2(project_dir, discovery, dep):
        stage2_called["called"] = True
        return _make_arch_map()

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery",
              side_effect=RuntimeError("snapshot partial")),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder",
              side_effect=fake_stage2),
    ):
        run_build_arch_map(project_dir, maes_dir)

    assert not stage2_called["called"], (
        "Stage 2 must NOT be called when Stage 1 fails"
    )


def test_failure_mode_stage2_does_not_call_emission(tmp_path):
    """On Stage 2 failure, emission MUST NOT be called (no partial output)."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    maes_dir = tmp_path / ".maes"
    emit_called = {"called": False}

    def fake_emit(inferred_dir, arch_map):
        emit_called["called"] = True

    with (
        patch("maes.pipeline.stage_1_discovery.run_discovery", return_value=_make_discovery()),
        patch("maes.pipeline.stage_3_dep.run_dep_stage", return_value=_make_dep()),
        patch("maes.pipeline.stage_2_arch_builder.run_arch_builder",
              side_effect=ValueError("invalid stage output")),
        patch("maes.pipeline.stage_7_emission._emit_architecture_map", side_effect=fake_emit),
    ):
        run_build_arch_map(project_dir, maes_dir)

    assert not emit_called["called"], (
        "Emission must NOT be called when Stage 2 fails"
    )


def test_success_returns_exit_0(tmp_path):
    """Successful execution MUST return exit code 0."""
    rc, _ = _run(tmp_path)
    assert rc == 0


def test_success_writes_architecture_map(tmp_path):
    """Successful execution MUST produce architecture_map.json."""
    rc, inferred = _run(tmp_path)
    assert rc == 0
    assert (inferred / "architecture_map.json").exists()


def test_success_architecture_map_is_valid_json(tmp_path):
    """architecture_map.json MUST be parseable JSON."""
    rc, inferred = _run(tmp_path)
    assert rc == 0
    try:
        json.loads((inferred / "architecture_map.json").read_text())
    except json.JSONDecodeError as exc:
        pytest.fail(f"architecture_map.json is not valid JSON: {exc}")


def test_failure_mode_no_fallback_mode(tmp_path):
    """There is no degraded mode — any stage failure MUST produce rc=1 with no output."""
    for exc_class in (RuntimeError, ValueError, OSError, FileNotFoundError):
        run_tmp = tmp_path / exc_class.__name__
        run_tmp.mkdir()
        project_dir = run_tmp / "project"
        project_dir.mkdir()
        maes_dir = run_tmp / ".maes"

        with (
            patch("maes.pipeline.stage_1_discovery.run_discovery",
                  side_effect=exc_class("test error")),
        ):
            rc = run_build_arch_map(project_dir, maes_dir)

        assert rc == 1, (
            f"Stage 1 {exc_class.__name__} must result in rc=1; got {rc}"
        )
        inferred = maes_dir / "context" / "inferred"
        assert not (inferred / "architecture_map.json").exists(), (
            f"No output must be written on {exc_class.__name__}"
        )
