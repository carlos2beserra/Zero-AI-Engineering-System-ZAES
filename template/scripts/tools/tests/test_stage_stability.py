"""Unit tests for pipeline/stage_5_stability.py — run_stability_scoring()."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maes.pipeline.stage_5_stability import run_stability_scoring
from maes.pipeline.contracts import StabilityResult


_BC_A = [{"name": "auth", "modules": ["auth", "users"]}]
_BC_B = [{"name": "auth", "modules": ["auth", "users"]}, {"name": "billing", "modules": ["billing"]}]
_BC_UNRELATED = [{"name": "totally_different", "modules": ["xyz"]}]


def _write_history(maes_dir: Path, date_str: str, bc: list) -> None:
    history_dir = maes_dir / "context" / "inferred" / ".history"
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / f"bounded-contexts-{date_str}.json").write_text(
        json.dumps({"bounded_contexts": bc}, ensure_ascii=False), encoding="utf-8"
    )


# ─── First execution (no history) ────────────────────────────────────────────


def test_returns_none_when_no_history(tmp_path):
    result = run_stability_scoring(_BC_A, tmp_path)
    assert result is None


def test_returns_none_when_history_dir_empty(tmp_path):
    history_dir = tmp_path / "context" / "inferred" / ".history"
    history_dir.mkdir(parents=True)
    result = run_stability_scoring(_BC_A, tmp_path)
    assert result is None


# ─── Returns StabilityResult when history exists ─────────────────────────────


def test_returns_stability_result_with_history(tmp_path):
    _write_history(tmp_path, "20260101", _BC_A)
    result = run_stability_scoring(_BC_A, tmp_path)
    assert isinstance(result, StabilityResult)


def test_stability_result_fields_present(tmp_path):
    _write_history(tmp_path, "20260101", _BC_A)
    result = run_stability_scoring(_BC_A, tmp_path)
    assert isinstance(result.avg_jaccard, float)
    assert isinstance(result.passed, bool)
    assert isinstance(result.threshold, float)
    assert isinstance(result.matched, tuple)
    assert isinstance(result.drift_detected, bool)


def test_previous_run_date_extracted_from_filename(tmp_path):
    _write_history(tmp_path, "20260515", _BC_A)
    result = run_stability_scoring(_BC_A, tmp_path)
    assert result.previous_run_date == "20260515"


# ─── Drift detection ─────────────────────────────────────────────────────────


def test_identical_contexts_pass_stability(tmp_path):
    _write_history(tmp_path, "20260101", _BC_A)
    result = run_stability_scoring(_BC_A, tmp_path)
    assert result.passed is True
    assert result.drift_detected is False


def test_completely_different_contexts_fail_stability(tmp_path):
    _write_history(tmp_path, "20260101", _BC_A)
    result = run_stability_scoring(_BC_UNRELATED, tmp_path, threshold=0.70)
    assert result.drift_detected is True
    assert result.passed is False


def test_custom_threshold_respected(tmp_path):
    _write_history(tmp_path, "20260101", _BC_A)
    # With threshold=0.0 anything passes
    result = run_stability_scoring(_BC_UNRELATED, tmp_path, threshold=0.0)
    assert result.passed is True
    assert result.drift_detected is False
