"""Unit tests for pipeline/stage_3_dep.py — run_dep_stage()."""

from __future__ import annotations

from pathlib import Path

import pytest

from maes.pipeline.stage_3_dep import run_dep_stage
from maes.pipeline.contracts import DepResult


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ─── Contract shape ───────────────────────────────────────────────────────────


def test_run_dep_stage_returns_dep_result(tmp_path):
    result = run_dep_stage(tmp_path)
    assert isinstance(result, DepResult)


def test_run_dep_stage_violations_is_tuple(tmp_path):
    result = run_dep_stage(tmp_path)
    assert isinstance(result.violations, tuple)


def test_run_dep_stage_boundary_map_is_dict(tmp_path):
    result = run_dep_stage(tmp_path)
    assert isinstance(result.boundary_map, dict)


def test_run_dep_stage_empty_dir_produces_no_violations(tmp_path):
    result = run_dep_stage(tmp_path)
    assert result.violations == ()


# ─── Stdlib imports do not produce violations ─────────────────────────────────


def test_stdlib_import_does_not_produce_violation(tmp_path):
    _write(
        tmp_path / "api" / "routes.py",
        "import os\nimport json\nfrom pathlib import Path\n",
    )
    _write(tmp_path / "domain" / "entity.py", "x = 1\n")
    result = run_dep_stage(tmp_path)
    assert result.violations == ()


def test_framework_import_does_not_produce_violation(tmp_path):
    _write(
        tmp_path / "api" / "routes.py",
        "from fastapi import FastAPI\nimport pydantic\n",
    )
    _write(tmp_path / "domain" / "entity.py", "x = 1\n")
    result = run_dep_stage(tmp_path)
    assert result.violations == ()


# ─── Violation shape ──────────────────────────────────────────────────────────


def test_violation_dict_has_expected_keys(tmp_path):
    # infrastructure importing from controller is a downward violation
    _write(
        tmp_path / "infrastructure" / "db.py",
        "from controller import handler\n",
    )
    _write(tmp_path / "controller" / "handler.py", "x = 1\n")
    result = run_dep_stage(tmp_path)
    for v in result.violations:
        assert "type" in v
        assert "file" in v
        assert "description" in v
