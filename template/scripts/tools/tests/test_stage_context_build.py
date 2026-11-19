"""Unit tests for pipeline/stage_4_context_build.py — build_context()."""

from __future__ import annotations

from maes.pipeline.stage_4_context_build import build_context, _compute_fingerprint, _normalize_entity_ownership
from maes.pipeline.contracts import BuiltContext, DiscoveryResult


def _make_discovery(files=(), total_chars=0, truncated=(), dirs=(), budget_pct=0.0) -> DiscoveryResult:
    return DiscoveryResult(
        files=tuple(files),
        file_tree="",
        total_chars=total_chars,
        truncated_files=frozenset(truncated),
        dirs_seen=frozenset(dirs),
        budget_used_pct=budget_pct,
    )


# ─── build_context() — contract shape ────────────────────────────────────────


def test_build_context_returns_built_context():
    result = build_context({}, _make_discovery())
    assert isinstance(result, BuiltContext)


def test_build_context_no_io(tmp_path):
    # Pure function — calling it must not create any files
    import os
    before = set(os.listdir(tmp_path))
    build_context({}, _make_discovery())
    after = set(os.listdir(tmp_path))
    assert before == after


def test_build_context_empty_analysis_produces_empty_contexts():
    result = build_context({}, _make_discovery())
    assert result.bounded_contexts == ()


def test_build_context_preserves_analysis_raw():
    analysis = {"modules": ["auth"], "bounded_contexts": []}
    result = build_context(analysis, _make_discovery())
    assert result.analysis_raw is analysis


# ─── Fingerprint injection ────────────────────────────────────────────────────


def test_build_context_injects_module_fingerprint():
    analysis = {
        "bounded_contexts": [{"name": "auth", "modules": ["auth", "users"]}]
    }
    result = build_context(analysis, _make_discovery())
    assert len(result.bounded_contexts) == 1
    ctx = result.bounded_contexts[0]
    assert "module_fingerprint" in ctx
    assert isinstance(ctx["module_fingerprint"], str)
    assert len(ctx["module_fingerprint"]) == 12


def test_fingerprint_is_deterministic():
    modules = ["auth", "users", "tokens"]
    fp1 = _compute_fingerprint(modules)
    fp2 = _compute_fingerprint(modules)
    assert fp1 == fp2


def test_fingerprint_is_order_independent():
    fp1 = _compute_fingerprint(["auth", "users"])
    fp2 = _compute_fingerprint(["users", "auth"])
    assert fp1 == fp2


# ─── Entity ownership normalization ──────────────────────────────────────────


def test_normalize_entity_ownership_string_gets_owner_context():
    result = _normalize_entity_ownership(["User", "Token"], "auth")
    assert result == [
        {"name": "User", "owner_context": "auth"},
        {"name": "Token", "owner_context": "auth"},
    ]


def test_normalize_entity_ownership_dict_preserves_existing_owner_context():
    entity = {"name": "User", "owner_context": "existing"}
    result = _normalize_entity_ownership([entity], "auth")
    assert result[0]["owner_context"] == "existing"


def test_normalize_entity_ownership_dict_without_owner_context_gets_inferred():
    entity = {"name": "User"}
    result = _normalize_entity_ownership([entity], "auth")
    assert result[0]["owner_context"] == "auth"


def test_build_context_entities_have_owner_context():
    analysis = {
        "bounded_contexts": [{
            "name": "billing",
            "modules": ["billing"],
            "shared_entities": ["Invoice", "Payment"],
        }]
    }
    result = build_context(analysis, _make_discovery())
    ctx = result.bounded_contexts[0]
    for entity in ctx["shared_entities"]:
        assert "owner_context" in entity
        assert entity["owner_context"] == "billing"
