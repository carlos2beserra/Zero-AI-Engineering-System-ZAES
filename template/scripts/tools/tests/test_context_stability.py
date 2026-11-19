"""Tests for context_stability.py — jaccard, validate_context_stability, compute_retrieval_score."""

from __future__ import annotations

import pytest

from maes.context_stability import (
    _flatten_assertion_text,
    compute_retrieval_score,
    jaccard,
    validate_context_stability,
)


# ─── jaccard ─────────────────────────────────────────────────────────────────


def test_jaccard_identical_sets():
    assert jaccard(["a", "b", "c"], ["a", "b", "c"]) == 1.0


def test_jaccard_disjoint_sets():
    assert jaccard(["a", "b"], ["c", "d"]) == 0.0


def test_jaccard_partial_overlap():
    # |intersection| = 1, |union| = 3 → 1/3
    result = jaccard(["a", "b"], ["b", "c"])
    assert abs(result - 1 / 3) < 1e-9


def test_jaccard_empty_both():
    assert jaccard([], []) == 1.0


def test_jaccard_empty_one_side():
    assert jaccard(["a"], []) == 0.0
    assert jaccard([], ["a"]) == 0.0


def test_jaccard_accepts_sets():
    assert jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


def test_jaccard_deduplicates_input():
    # Duplicates in input should not affect the result (set semantics)
    assert jaccard(["a", "a", "b"], ["b", "b", "c"]) == pytest.approx(1 / 3)


def test_jaccard_symmetric():
    a, b = ["app/api", "app/services"], ["app/services", "app/domain"]
    assert jaccard(a, b) == jaccard(b, a)


# ─── validate_context_stability ───────────────────────────────────────────────


def _ctx(name: str, modules: list[str], fingerprint: str | None = None) -> dict:
    return {"name": name, "modules": modules, "module_fingerprint": fingerprint}


def test_stability_identical_runs():
    contexts = [
        _ctx("pipeline", ["app/api", "app/services"]),
        _ctx("auth", ["app/domain", "app/workers"]),
    ]
    result = validate_context_stability(contexts, contexts)
    assert result["passed"] is True
    assert result["avg_jaccard"] == 1.0


def test_stability_passes_above_threshold():
    run1 = [_ctx("pipeline", ["app/api", "app/services", "app/workers"])]
    run2 = [_ctx("pipeline_v2", ["app/api", "app/services", "app/domain"])]
    result = validate_context_stability(run1, run2, threshold=0.40)
    # |intersection|=2, |union|=4 → 0.5
    assert result["avg_jaccard"] == pytest.approx(0.5)
    assert result["passed"] is True


def test_stability_fails_below_threshold():
    run1 = [_ctx("pipeline", ["app/api", "app/services"])]
    run2 = [_ctx("different", ["app/domain", "app/workers"])]
    result = validate_context_stability(run1, run2, threshold=0.70)
    assert result["avg_jaccard"] == 0.0
    assert result["passed"] is False


def test_stability_fingerprint_match_scores_1():
    fp = "abcdef012345"
    run1 = [_ctx("pipeline", ["app/api"], fingerprint=fp)]
    run2 = [_ctx("pipeline_renamed", ["app/api"], fingerprint=fp)]
    result = validate_context_stability(run1, run2)
    assert result["matched"][0]["jaccard"] == 1.0
    assert result["passed"] is True


def test_stability_fingerprint_match_ignores_name_change():
    fp = "abcdef012345"
    run1 = [_ctx("ctx_old_name", ["app/api", "app/services"], fingerprint=fp)]
    run2 = [_ctx("ctx_new_name", ["app/api", "app/services"], fingerprint=fp)]
    result = validate_context_stability(run1, run2)
    assert result["matched"][0]["name_run1"] == "ctx_old_name"
    assert result["matched"][0]["name_run2"] == "ctx_new_name"
    assert result["matched"][0]["jaccard"] == 1.0


def test_stability_fallback_to_module_overlap():
    run1 = [_ctx("pipeline", ["app/api", "app/services"], fingerprint="fp1")]
    run2 = [_ctx("pipeline", ["app/api", "app/services"], fingerprint="fp2")]
    result = validate_context_stability(run1, run2)
    # Different fingerprints → fallback to module overlap; modules identical → Jaccard=1.0
    assert result["matched"][0]["jaccard"] == 1.0


def test_stability_empty_runs():
    result = validate_context_stability([], [])
    assert result["avg_jaccard"] == 1.0
    assert result["passed"] is True
    assert result["matched"] == []


def test_stability_unmatched_contexts_score_zero():
    run1 = [_ctx("ctx_a", ["app/api"]), _ctx("ctx_b", ["app/services"])]
    run2 = [_ctx("ctx_c", ["app/domain"])]
    result = validate_context_stability(run1, run2)
    # ctx_a matches ctx_c (only option), ctx_b has nothing left → scores 0.0
    assert len(result["matched"]) == 2
    scores = [m["jaccard"] for m in result["matched"]]
    assert 0.0 in scores


def test_stability_result_structure():
    run1 = [_ctx("pipeline", ["app/api"])]
    run2 = [_ctx("pipeline", ["app/api"])]
    result = validate_context_stability(run1, run2)

    assert "matched" in result
    assert "avg_jaccard" in result
    assert "passed" in result
    assert "threshold" in result

    m = result["matched"][0]
    assert "name_run1" in m
    assert "name_run2" in m
    assert "jaccard" in m


def test_stability_respects_custom_threshold():
    run1 = [_ctx("ctx", ["a", "b", "c", "d"])]
    run2 = [_ctx("ctx", ["c", "d", "e", "f"])]
    # Jaccard = 2/6 ≈ 0.333
    result_low = validate_context_stability(run1, run2, threshold=0.30)
    result_high = validate_context_stability(run1, run2, threshold=0.40)
    assert result_low["passed"] is True
    assert result_high["passed"] is False


# ─── compute_retrieval_score ──────────────────────────────────────────────────


def test_retrieval_score_all_keywords_match():
    assertion = {"trigger": "pipeline status mutation", "description": "avoid direct mutation"}
    score = compute_retrieval_score(["pipeline", "status", "mutation"], assertion)
    assert score > 0.5


def test_retrieval_score_no_keywords_match():
    assertion = {"trigger": "some unrelated text"}
    score = compute_retrieval_score(["pipeline", "status"], assertion)
    assert score == 0.0


def test_retrieval_score_with_id_bonus():
    assertion = {"id": "pipeline.direct_status", "trigger": "unrelated"}
    score_with_id = compute_retrieval_score([], assertion)
    score_without = compute_retrieval_score([], {"trigger": "unrelated"})
    assert score_with_id > score_without
    assert score_with_id == pytest.approx(0.15)


def test_retrieval_score_domain_match():
    assertion = {"trigger": "job_lifecycle pipeline mutation"}
    score = compute_retrieval_score([], assertion, domain_names=["job_lifecycle"])
    assert score == pytest.approx(0.30)


def test_retrieval_score_empty_query():
    assertion = {"trigger": "something"}
    score = compute_retrieval_score([], assertion)
    assert score == 0.0


def test_retrieval_score_capped_at_1():
    # All signals fire simultaneously
    assertion = {"id": "x.y", "trigger": "pipeline status mutation job_lifecycle"}
    score = compute_retrieval_score(
        ["pipeline", "status", "mutation"],
        assertion,
        domain_names=["job_lifecycle"],
    )
    assert score <= 1.0


def test_retrieval_score_keyword_case_insensitive():
    assertion = {"trigger": "PIPELINE STATUS mutation"}
    score = compute_retrieval_score(["pipeline", "status"], assertion)
    assert score > 0.0


def test_retrieval_score_nested_assertion():
    assertion = {
        "trigger": "direct db access",
        "likely_wrong": "repo.query()",
        "correction": "use service layer",
        "id": "infra.direct_db",
    }
    score = compute_retrieval_score(["db", "service"], assertion)
    assert score > 0.0


# ─── _flatten_assertion_text ──────────────────────────────────────────────────


def test_flatten_string_value():
    assert "hello world" in _flatten_assertion_text({"key": "Hello World"})


def test_flatten_nested_dict():
    text = _flatten_assertion_text({"outer": {"inner": "deep value"}})
    assert "deep value" in text


def test_flatten_list_values():
    text = _flatten_assertion_text({"items": ["alpha", "beta", "gamma"]})
    assert "alpha" in text
    assert "beta" in text
    assert "gamma" in text


def test_flatten_mixed_structure():
    text = _flatten_assertion_text({
        "id": "x.y",
        "tags": ["pipeline", "status"],
        "meta": {"author": "team_a"},
    })
    assert "x.y" in text
    assert "pipeline" in text
    assert "team_a" in text


def test_flatten_ignores_non_string_leaves():
    # Non-string leaves (int, bool, None) must not crash
    text = _flatten_assertion_text({"count": 42, "active": True, "note": None})
    assert isinstance(text, str)
