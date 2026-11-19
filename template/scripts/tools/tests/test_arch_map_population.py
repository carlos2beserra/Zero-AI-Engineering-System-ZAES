"""Architecture map over the real population — coverage, sampling and the funnel.

Integration tests against a real filesystem (no mocked stages), because the bug being
regressed was precisely that every number came from the content sample.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maes.build_arch_map_cmd import run_build_arch_map


def _write(root: Path, rel: str, content: str = "export const a = 1\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _build(project_dir: Path) -> dict:
    maes_dir = project_dir / ".maes"
    rc = run_build_arch_map(project_dir, maes_dir)
    assert rc == 0
    return json.loads(
        (maes_dir / "context" / "inferred" / "architecture_map.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """A shape that survives the collapse rules, so the funnel has something to show.

    Directories need >= _COALESCE_UP_THRESHOLD (3) files to avoid being absorbed into
    their parent — a fixture of 1-2 file directories collapses to a single `src` node
    and would make these assertions vacuous.
    """
    _write(tmp_path, "package.json", json.dumps({"dependencies": {"react": "18"}}))
    for i in range(3):
        for name in ("index.ts", "handler.ts", "types.ts"):
            _write(tmp_path, f"src/services/svc{i}/{name}")
    for i in range(4):
        _write(tmp_path, f"src/ui/View{i}.tsx", "export default () => null\n")
    _write(tmp_path, "src/main.ts")
    return tmp_path


# ─── Coverage is measured against the population, not the sample ──────────────


def test_source_files_is_the_project_population(project: Path):
    data = _build(project)
    metrics = data["diagnostic_metrics"]
    # 3 dirs x 3 files + 4 views + main.ts = 14. package.json is collected but is not
    # part of the POPULATION — the population is the canonical source definition.
    assert metrics["source_files"] == 14


def test_sampled_files_never_exceeds_population(project: Path):
    metrics = _build(project)["diagnostic_metrics"]
    assert 0 <= metrics["sampled_files"] <= metrics["source_files"]


def test_sampling_ratio_is_a_fraction(project: Path):
    data = _build(project)
    ratio = data["diagnostic_metrics"]["sampling_ratio"]
    assert isinstance(ratio, (int, float))
    assert 0.0 <= ratio <= 1.0
    assert data["coverage_context"]["sampling_ratio"] == ratio


def test_frontend_extensions_produce_nodes(project: Path):
    data = _build(project)
    paths = {n["path"] for n in data["nodes"]}
    assert any(p.startswith("src/ui") for p in paths), (
        "no frontend node emitted — .tsx never reached the topology"
    )


def test_is_frontend_project_detected_from_manifest(project: Path):
    data = _build(project)
    assert data["project_metadata"]["is_frontend_project"] is True


# ─── Structural Transformation Funnel ─────────────────────────────────────────


def test_funnel_is_monotonic(project: Path):
    m = _build(project)["diagnostic_metrics"]
    assert (
        m["source_files"] >= m["candidate_count"] >= m["collapsed_count"] >= m["node_count"]
    ), m


def test_node_count_matches_emitted_nodes(project: Path):
    data = _build(project)
    assert data["diagnostic_metrics"]["node_count"] == len(data["nodes"])


def test_project_root_counters_are_consistent(project: Path):
    meta = _build(project)["project_metadata"]
    assert meta["project_roots_discovered"] >= meta["project_roots_analyzed"]
    assert meta["project_roots_truncated"] == (
        meta["project_roots_discovered"] > meta["project_roots_analyzed"]
    )


# ─── Golden funnel — the actual protection for candidate_count ────────────────
#
# Scope is STRICTLY these four integers. It deliberately does NOT pin node ordering,
# stable_key/hashes, domain names, semantic_weight or entry_points: pinning the whole
# artifact would turn every legitimate architectural change into snapshot bureaucracy
# and the test would be ignored as noise, losing the signal it exists to give.


_GOLDEN_FUNNEL = {
    "source_files": 14,
    "candidate_count": 5,
    "collapsed_count": 5,
    "node_count": 5,
}


def test_golden_funnel(project: Path):
    m = _build(project)["diagnostic_metrics"]
    actual = {k: m[k] for k in _GOLDEN_FUNNEL}
    assert actual == _GOLDEN_FUNNEL, (
        f"Structural funnel changed: expected {_GOLDEN_FUNNEL}, actual {actual}.\n"
        "This changes the structural interpretation of the project.\n"
        "Legitimate causes: new entry in CANONICAL_SOURCE_EXTENSIONS, deliberate "
        "change to a grouping/collapse rule, new structural type.\n"
        "Update these numbers ONLY with architectural justification in the PR "
        "description (ADR 0009)."
    )


# ─── files_sampled per node: population/evidence pair ────────────────────────


def test_node_files_sampled_within_file_count(project: Path):
    for node in _build(project)["nodes"]:
        assert 0 <= node["files_sampled"] <= node["file_count"], node


def test_unread_node_reports_zero_evidence(tmp_path: Path):
    """files_sampled == 0 means every semantic field of that node lacks evidence —
    not that it is empty (ADR 0009). Without it, entry_points: [] is ambiguous."""
    big = "y" * 8_000
    for i in range(60):
        _write(tmp_path, f"src/mod{i:03d}/index.ts", big)

    data = _build(tmp_path)
    unread = [n for n in data["nodes"] if n["files_sampled"] == 0]

    assert unread, "expected at least one node outside the content sample"
    assert all(n["entry_points"] == [] for n in unread)


# ─── Structural growth: topology != content ──────────────────────────────────


def test_new_code_enters_topology_even_when_it_does_not_fit_the_sample(project: Path):
    """Mirror of the docs test: docs must not displace topology, and code must enter
    topology even when the budget cannot read it.

    Files must have CONTENT: _read_file returns "" for an empty file and
    col.add(rel, "") adds ZERO to the budget, so 300 empty files would all be
    collected for free and sampling_ratio would not fall — the assertion would be
    vacuously true.
    """
    before = _build(project)["diagnostic_metrics"]

    big = "y" * 8_000
    for i in range(300):
        _write(project, f"src/extra{i:03d}/mod.ts", big)

    after = _build(project)["diagnostic_metrics"]

    assert after["candidate_count"] > before["candidate_count"]
    assert after["source_files"] == before["source_files"] + 300
    assert after["sampling_ratio"] < before["sampling_ratio"]


def test_existing_nodes_do_not_disappear_when_code_is_added(project: Path):
    """The original symptom, inverted: adding content used to SHRINK the map."""
    before = {n["path"] for n in _build(project)["nodes"]}

    big = "y" * 8_000
    for i in range(300):
        _write(project, f"src/extra{i:03d}/mod.ts", big)

    after = {n["path"] for n in _build(project)["nodes"]}
    assert before <= after, f"nodes lost: {sorted(before - after)}"


def test_adding_documentation_does_not_change_the_map(project: Path):
    """The symptom that opened the investigation: more docs, fewer nodes."""
    before = _build(project)

    for i in range(60):
        _write(project, f"docs/adr/{i:04d}-decision.md", "# adr\n" + "d" * 15_000)

    after = _build(project)

    assert after["diagnostic_metrics"] == before["diagnostic_metrics"]
    assert [n["path"] for n in after["nodes"]] == [n["path"] for n in before["nodes"]]
