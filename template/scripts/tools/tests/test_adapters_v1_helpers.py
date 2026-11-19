"""Tests for adapters.py V1 helpers (Evidence Preservation + Stack section + composition)."""

from datetime import date

from maes.adapters import (
    _compose,
    _est_tokens,
    _fmt_assertion_bullet,
    _render_placement_section,
    _render_runtime_section,
    _render_stack_section,
    _truncate_to_budget,
)
from maes.models import Assertion, RuntimeContext, StackContext


def _mk_assertion(claim: str, evidence: str | None = None) -> Assertion:
    return Assertion(
        id=Assertion.make_id(claim),
        claim=claim,
        type="OBSERVATION",
        layer=4,
        subject=None,
        paths=[],
        confidence="explicit",
        source="human/test.md",
        ttl="P30D",
        last_verified="2025-01-01",
        owner="test",
        evidence=evidence,
    )


# ─── Evidence Preservation ────────────────────────────────────────────────────

def test_fmt_assertion_bullet_with_evidence():
    a = _mk_assertion("auth uses JWT", evidence="src/auth.ts:42")
    out = _fmt_assertion_bullet(a)
    assert out == "- auth uses JWT  *(src/auth.ts:42)*"


def test_fmt_assertion_bullet_without_evidence():
    a = _mk_assertion("auth uses JWT")
    assert _fmt_assertion_bullet(a) == "- auth uses JWT"


def test_fmt_assertion_bullet_with_stale_suffix():
    a = _mk_assertion("auth uses JWT", evidence="src/auth.ts:42")
    out = _fmt_assertion_bullet(a, stale_suffix=" ⚠️")
    assert "⚠️" in out
    assert "src/auth.ts:42" in out


def test_fmt_assertion_bullet_stale_only():
    a = _mk_assertion("auth uses JWT")
    out = _fmt_assertion_bullet(a, stale_suffix=" (may be stale)")
    assert out == "- auth uses JWT (may be stale)"


# ─── Stack section (C2 + I3) ──────────────────────────────────────────────────

def test_render_stack_section_empty_returns_no_lines():
    assert _render_stack_section(None) == []
    assert _render_stack_section(StackContext()) == []


def test_render_stack_section_populated():
    s = StackContext(
        languages=("Python", "TypeScript"),
        frameworks=("FastAPI",),
        runtimes=(),
        package_managers=("pip",),
    )
    lines = _render_stack_section(s)
    text = "\n".join(lines)
    assert "## Tech Stack" in text
    assert "Python, TypeScript" in text
    assert "FastAPI" in text
    assert "pip" in text
    # Runtimes empty → not rendered
    assert "Runtimes" not in text


def test_render_stack_section_respects_budget():
    big_frameworks = tuple(f"Framework{i}" for i in range(200))
    s = StackContext(frameworks=big_frameworks)
    lines = _render_stack_section(s, max_tokens=20)
    assert any("truncated" in ln for ln in lines)


# ─── Placement section (I5/I6 + I3) ───────────────────────────────────────────

def test_render_placement_section_empty_or_missing():
    assert _render_placement_section(None) == []
    assert _render_placement_section({}) == []
    assert _render_placement_section({"status": "empty", "placements": []}) == []


def test_render_placement_section_omitted_when_evidence_insufficient():
    """The refusal must actually reach the adapter: this is the cut of the leak into
    CLAUDE.md. Without it, a ~5% sample kept orienting where new code goes."""
    assert _render_placement_section(
        {"status": "insufficient_sample", "placements": []}
    ) == []


def test_render_placement_section_omitted_when_no_observed_convention():
    assert _render_placement_section(
        {"status": "no_observed_convention", "placements": []}
    ) == []


def test_render_placement_section_high_confidence():
    pm = {
        "status": "generated",
        "placements": [
            {"category": "Service", "path": "src/services",
             "confidence": "high", "coverage_pct": 0.92},
        ],
    }
    out = _render_placement_section(pm)
    text = "\n".join(out)
    assert "## Code Placement" in text
    assert "Service" in text
    assert "src/services" in text
    assert "92%" in text
    assert "convenção dispersa" not in text


def test_render_placement_section_low_confidence_warns():
    pm = {
        "status": "generated",
        "placements": [
            {"category": "Service", "path": "src/svc",
             "confidence": "low", "coverage_pct": 0.25},
        ],
    }
    out = _render_placement_section(pm)
    text = "\n".join(out)
    assert "⚠️" in text
    assert "convenção dispersa" in text


# ─── Runtime section (I4 + I3) ────────────────────────────────────────────────

def test_render_runtime_section_empty():
    assert _render_runtime_section(None) == []
    assert _render_runtime_section(RuntimeContext()) == []


def test_render_runtime_section_fresh():
    rt = RuntimeContext(test="pytest -q", build="pnpm build",
                        last_verified="2026-06-01", staleness_warning=False)
    out = _render_runtime_section(rt)
    text = "\n".join(out)
    assert "## Runtime Commands" in text
    assert "pytest -q" in text
    assert "pnpm build" in text
    assert "may be stale" not in text


def test_render_runtime_section_warns_when_stale():
    rt = RuntimeContext(test="pytest", last_verified="2025-01-01",
                        staleness_warning=True)
    out = _render_runtime_section(rt)
    text = "\n".join(out)
    assert "⚠️" in text
    assert "may be stale" in text
    assert "2025-01-01" in text


def test_render_runtime_section_warns_when_no_last_verified():
    rt = RuntimeContext(test="pytest", staleness_warning=True)
    out = _render_runtime_section(rt)
    text = "\n".join(out)
    assert "never" in text


# ─── Composition / budget helpers ─────────────────────────────────────────────

def test_compose_skips_empty_sections():
    out = _compose([["a"], [], ["b"]])
    assert out == ["a", "b"]


def test_compose_handles_all_empty():
    assert _compose([[], []]) == []


def test_est_tokens_minimum_one():
    assert _est_tokens("") == 1
    assert _est_tokens("x") == 1
    assert _est_tokens("a" * 400) == 100


def test_truncate_to_budget_keeps_within_limit():
    lines = ["short", "another short", "yet another line"]
    out = _truncate_to_budget(lines, max_tokens=1000)
    assert out == lines  # under budget


def test_truncate_to_budget_appends_marker_when_cut():
    lines = ["a" * 100 for _ in range(10)]
    out = _truncate_to_budget(lines, max_tokens=30)
    assert any("truncated" in ln for ln in out)
    assert len(out) < len(lines) + 2
