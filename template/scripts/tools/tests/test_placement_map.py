"""Tests for _build_placement_map (I5/I6 — convention discovery)."""

import json
from pathlib import Path

from maes.compiler import _build_placement_map, _confidence_tier, _dominant_prefix


_SCHEMA = "2.1"


def _write(p: Path, payload: object) -> Path:
    """Write an arch map fixture with a valid schema and full sampling by default.

    _build_placement_map gates on two independent things (ADR 0009): artifact validity
    (schema_version present and supported) and evidence sufficiency (sampling_ratio at
    or above the floor). Tests about the PREFIX logic must satisfy both, so the three
    concerns stay independently testable.
    """
    if isinstance(payload, dict):
        payload = {"schema_version": _SCHEMA, **payload}
        if "diagnostic_metrics" not in payload:
            payload = {**payload, "diagnostic_metrics": {"sampling_ratio": 1.0}}
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_confidence_tier_thresholds():
    assert _confidence_tier(0.95) == "high"
    assert _confidence_tier(0.80) == "high"
    assert _confidence_tier(0.65) == "medium"
    assert _confidence_tier(0.50) == "medium"
    assert _confidence_tier(0.49) == "low"
    assert _confidence_tier(0.0) == "low"


def test_dominant_prefix_picks_majority():
    nodes = [
        {"path": "src/services/auth.ts", "file_count": 10},
        {"path": "src/services/user.ts", "file_count": 8},
        {"path": "src/services/db.ts", "file_count": 5},
        {"path": "lib/other.ts", "file_count": 2},
    ]
    prefix, covered, total = _dominant_prefix(nodes)
    assert prefix == "src/services"
    assert covered == 23
    assert total == 25


def test_dominant_prefix_empty_nodes():
    assert _dominant_prefix([]) == ("", 0, 0)


def test_build_placement_map_high_confidence(tmp_path):
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"type": "Service", "path": "src/services/auth.ts", "file_count": 5},
            {"type": "Service", "path": "src/services/user.ts", "file_count": 5},
            {"type": "Service", "path": "src/services/db.ts", "file_count": 5},
        ],
    })
    out = _build_placement_map(p)
    assert out is not None
    assert out["status"] == "generated"
    assert out["schema_version"] == "1.1"
    assert len(out["placements"]) == 1
    pl = out["placements"][0]
    assert pl["category"] == "Service"
    assert pl["path"] == "src/services"
    assert pl["confidence"] == "high"
    assert pl["coverage_pct"] >= 0.999


def test_build_placement_map_multiple_categories(tmp_path):
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"type": "Service", "path": "src/services/a.ts", "file_count": 4},
            {"type": "Service", "path": "src/services/b.ts", "file_count": 4},
            {"type": "Module", "path": "packages/core/x.ts", "file_count": 2},
            {"type": "Module", "path": "packages/core/y.ts", "file_count": 2},
        ],
    })
    out = _build_placement_map(p)
    cats = {pl["category"]: pl for pl in out["placements"]}
    assert "Service" in cats
    assert "Module" in cats
    assert cats["Module"]["path"] == "packages/core"


def test_build_placement_map_low_confidence(tmp_path):
    # 4 distinct directories, no clear convention
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"type": "Service", "path": "src/auth/svc.ts", "file_count": 1},
            {"type": "Service", "path": "lib/user/svc.ts", "file_count": 1},
            {"type": "Service", "path": "packages/core/svc.ts", "file_count": 1},
            {"type": "Service", "path": "apps/web/svc.ts", "file_count": 1},
        ],
    })
    out = _build_placement_map(p)
    pl = out["placements"][0]
    # Each unique prefix has only 1 file out of 4 → 25%
    assert pl["confidence"] == "low"


def test_dominant_prefix_single_two_segment_node_does_not_overcount():
    # A single 2-segment node: depth 3 and depth 2 collapse to the same prefix.
    # Without per-node prefix dedupe, file_count would be counted twice (20) vs
    # a total of 10, producing covered > total (P0-B impossible metric).
    nodes = [{"path": "src/services", "file_count": 10}]
    _, covered, total = _dominant_prefix(nodes)
    assert covered <= total
    assert covered == 10
    assert total == 10


def test_dominant_prefix_single_one_segment_node_does_not_overcount():
    # A 1-segment node collapses all three depths to the same prefix.
    nodes = [{"path": "src", "file_count": 7}]
    _, covered, total = _dominant_prefix(nodes)
    assert covered <= total
    assert covered == 7
    assert total == 7


def test_dominant_prefix_two_segment_siblings_pick_common_parent():
    # Two sibling 2-segment nodes: the honest dominant prefix is the shared
    # parent "src", not an arbitrary leaf. (Behaviour pinned post-P0-B fix.)
    nodes = [{"path": "src/a", "file_count": 10}, {"path": "src/b", "file_count": 10}]
    prefix, covered, total = _dominant_prefix(nodes)
    assert prefix == "src"
    assert covered <= total


def test_build_placement_map_invariants_hold(tmp_path):
    # coverage_pct must be a fraction <= 1.0 and file_count <= total_file_count
    # for every placement, including 1- and 2-segment node paths.
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"type": "Service", "path": "src/services", "file_count": 10},
            {"type": "Module", "path": "lib", "file_count": 4},
            {"type": "Module", "path": "lib/util", "file_count": 3},
        ],
    })
    out = _build_placement_map(p)
    assert out["placements"]
    for pl in out["placements"]:
        assert 0 <= pl["coverage_pct"] <= 1.0, pl
        assert pl["file_count"] <= pl["total_file_count"], pl


def test_build_placement_map_empty(tmp_path):
    p = _write(tmp_path / "arch.json", {"nodes": []})
    out = _build_placement_map(p)
    assert out["status"] == "empty"
    assert out["placements"] == []


def test_build_placement_map_unreadable(tmp_path):
    p = tmp_path / "arch.json"
    p.write_text(json.dumps([]), encoding="utf-8")
    assert _build_placement_map(p) is None


# ─── Evidence gate — fail-closed (ADR 0009) ──────────────────────────────────


def test_low_content_sampling_does_not_block_a_structural_claim(tmp_path):
    """The evidence for "where does a Service live?" is the topology, not the text.

    A placement conclusion is built from node paths, types and file counts — all
    population-derived — so `sampling_ratio` is the wrong evidence for it. Field
    proof: a 941-file project reads ~3% of its content within the budget while its
    topology is complete; gating on sampling suppressed five valid observations.
    """
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"type": "Service", "path": "src/services/a", "file_count": 5},
            {"type": "Repository", "path": "src/repos/b", "file_count": 5},
        ],
        "diagnostic_metrics": {"sampling_ratio": 0.03},
    })

    out = _build_placement_map(p)

    assert out["status"] == "generated"
    assert {pl["category"] for pl in out["placements"]} == {"Service", "Repository"}


def test_previous_schema_cannot_support_a_structural_claim(tmp_path):
    """Fail-closed on schema: a 2.0 map's topology was built over the budget-capped
    SAMPLE, so its prefixes describe 43 files, not the project. This is what makes the
    `sync` run by `maes upgrade` omit the section instead of re-emitting the wrong one.
    """
    p = tmp_path / "arch.json"
    p.write_text(json.dumps({
        "schema_version": "2.0",
        "nodes": [{"type": "Service", "path": "src/services/a", "file_count": 5}],
        "diagnostic_metrics": {"sampling_ratio": 1.0},
    }), encoding="utf-8")

    out = _build_placement_map(p)

    assert out["status"] == "stale_schema"
    assert out["placements"] == []


# ─── The two evidence policies are distinct ──────────────────────────────────


def test_evidence_policies_answer_different_questions():
    """Content-derived and structure-derived claims need different evidence (ADR 0009).

    Conflating them is the category error the ADR exists to prevent — and the one that
    made a 941-file project emit no placement at all.
    """
    from maes.sampling_policy import has_population_semantics, has_sufficient_sample

    # 3% sampling: not enough to assert anything read from file content...
    assert has_sufficient_sample(0.03) is False
    # ...but the topology of a 2.1 artifact is complete regardless.
    assert has_population_semantics("2.1") is True

    # Both are fail-closed on absent/unparseable input.
    assert has_sufficient_sample(None) is False
    assert has_population_semantics(None) is False
    assert has_population_semantics("2.0") is False
    assert has_population_semantics("abc") is False
    assert has_population_semantics("3.0") is True


# ─── Artifact state: old, broken and future must not collapse into one ────────


def test_broken_schema_version_is_invalid_artifact(tmp_path):
    p = tmp_path / "arch.json"
    p.write_text(json.dumps({
        "schema_version": "abc",
        "nodes": [{"type": "Service", "path": "src/services/a", "file_count": 5}],
        "diagnostic_metrics": {"sampling_ratio": 1.0},
    }), encoding="utf-8")
    assert _build_placement_map(p)["status"] == "invalid_artifact"


def test_broken_structure_is_invalid_artifact(tmp_path):
    p = tmp_path / "arch.json"
    p.write_text(json.dumps({
        "schema_version": "2.1",
        "nodes": "not-a-list",
        "diagnostic_metrics": {"sampling_ratio": 1.0},
    }), encoding="utf-8")
    assert _build_placement_map(p)["status"] == "invalid_artifact"


def test_future_schema_is_unsupported_not_silently_degraded(tmp_path):
    """An unknown version must never degrade silently: the user needs to update the
    CLI, not regenerate the map."""
    p = tmp_path / "arch.json"
    p.write_text(json.dumps({
        "schema_version": "99.0",
        "nodes": [{"type": "Service", "path": "src/services/a", "file_count": 5}],
        "diagnostic_metrics": {"sampling_ratio": 1.0},
    }), encoding="utf-8")
    assert _build_placement_map(p)["status"] == "unsupported_schema"


# ─── Non-discriminating prefix (the LDC regression) ──────────────────────────


def test_prefix_equal_to_universal_ancestor_is_discarded(tmp_path):
    """`Service → <repo root> (100%)` carries zero information: it is where
    EVERYTHING lives, so it cannot answer "where does a Service live?"."""
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"type": "Service", "path": "ldc-backend/src/a", "file_count": 5},
            {"type": "Service", "path": "ldc-backend/src/b", "file_count": 5},
            {"type": "Worker", "path": "ldc-backend/src/w", "file_count": 5},
        ],
    })
    out = _build_placement_map(p)
    # Universal ancestor is "ldc-backend/src"; Service's dominant prefix equals it.
    assert not [pl for pl in out["placements"] if pl["category"] == "Service"]
    assert out["status"] in {"generated", "no_observed_convention"}


def test_single_category_map_keeps_its_shared_prefix(tmp_path):
    """With one category every node IS a Service, so the shared prefix is the answer —
    discarding it would suppress a correct observation."""
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"type": "Service", "path": "src/services/a", "file_count": 5},
            {"type": "Service", "path": "src/services/b", "file_count": 5},
        ],
    })
    out = _build_placement_map(p)
    assert out["status"] == "generated"
    assert out["placements"][0]["path"] == "src/services"


def test_homonymous_directory_does_not_false_positive(tmp_path):
    """The rule is structural, never a comparison against the project directory name:
    a project called `ldc` with inner `packages/ldc` must not be affected."""
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"type": "Service", "path": "packages/ldc/services", "file_count": 5},
            {"type": "Worker", "path": "apps/ldc-web/workers", "file_count": 5},
        ],
    })
    out = _build_placement_map(p)
    assert out["status"] == "generated"
    assert {pl["category"] for pl in out["placements"]} == {"Service", "Worker"}


def test_single_segment_prefix_is_never_high_confidence(tmp_path):
    """Every node sharing one root makes the depth-1 bucket score 100% by
    construction — that is not a strong convention."""
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"type": "Service", "path": "src/a", "file_count": 5},
            {"type": "Service", "path": "src/b", "file_count": 5},
            {"type": "Worker", "path": "lib/w", "file_count": 1},
        ],
    })
    out = _build_placement_map(p)
    services = [pl for pl in out["placements"] if pl["category"] == "Service"]
    assert services and services[0]["path"] == "src"
    assert services[0]["confidence"] == "low"


# ─── no_observed_convention: absence of convention != absence of data ────────


def test_no_discriminating_prefix_reports_no_observed_convention(tmp_path):
    """Every category's dominant prefix collapses to the shared ancestor: the map is
    valid and the sample sufficient, but there is no convention to observe."""
    p = _write(tmp_path / "arch.json", {
        "nodes": [
            {"type": "Service", "path": "src/alpha", "file_count": 5},
            {"type": "Service", "path": "src/beta", "file_count": 5},
            {"type": "Worker", "path": "src/gamma", "file_count": 5},
            {"type": "Worker", "path": "src/delta", "file_count": 5},
        ],
    })
    out = _build_placement_map(p)
    assert out["status"] == "no_observed_convention"
    assert out["placements"] == []


def test_no_nodes_is_empty_not_no_observed_convention(tmp_path):
    p = _write(tmp_path / "arch.json", {"nodes": []})
    out = _build_placement_map(p)
    assert out["status"] == "empty"
