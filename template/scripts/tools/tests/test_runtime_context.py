"""Tests for _parse_human_runtime + _is_runtime_stale (I4 — runtime context)."""

from datetime import date, timedelta
from pathlib import Path

from maes.compiler import (
    _is_runtime_stale,
    _parse_human_runtime,
    _RUNTIME_STALE_THRESHOLD_DAYS,
)
from maes.models import RuntimeContext


# ─── _is_runtime_stale ────────────────────────────────────────────────────────

def test_stale_missing_returns_true():
    assert _is_runtime_stale("", date(2026, 6, 2)) is True


def test_stale_malformed_returns_true():
    assert _is_runtime_stale("not-a-date", date(2026, 6, 2)) is True
    assert _is_runtime_stale("2026/06/02", date(2026, 6, 2)) is True


def test_stale_recent_returns_false():
    today = date(2026, 6, 2)
    recent = (today - timedelta(days=15)).isoformat()
    assert _is_runtime_stale(recent, today) is False


def test_stale_old_returns_true():
    today = date(2026, 6, 2)
    old = (today - timedelta(days=_RUNTIME_STALE_THRESHOLD_DAYS + 1)).isoformat()
    assert _is_runtime_stale(old, today) is True


def test_stale_at_boundary_returns_false():
    today = date(2026, 6, 2)
    boundary = (today - timedelta(days=_RUNTIME_STALE_THRESHOLD_DAYS)).isoformat()
    assert _is_runtime_stale(boundary, today) is False


# ─── _parse_human_runtime ─────────────────────────────────────────────────────

def _write_runtime(human_dir: Path, frontmatter: dict, body: str = "") -> None:
    human_dir.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for k, v in frontmatter.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    if body:
        lines.append("")
        lines.append(body)
    (human_dir / "runtime.md").write_text("\n".join(lines), encoding="utf-8")


def test_parse_missing_returns_empty(tmp_path):
    rt = _parse_human_runtime(tmp_path / "human")
    assert rt.is_empty()
    assert rt.staleness_warning is False  # absent file is not stale, just missing


def test_parse_full_frontmatter_fresh(tmp_path):
    today = date(2026, 6, 2)
    _write_runtime(tmp_path, {
        "test": "pytest -q",
        "build": "pnpm build",
        "lint": "ruff check .",
        "run": "pnpm dev",
        "migrate": "alembic upgrade head",
        "test_pattern": "pytest -k {pattern}",
        "run_module_test": "pytest tests/{module}",
        "last_verified": today.isoformat(),
    })
    rt = _parse_human_runtime(tmp_path, today=today)
    assert rt.test == "pytest -q"
    assert rt.build == "pnpm build"
    assert rt.lint == "ruff check ."
    assert rt.migrate == "alembic upgrade head"
    assert rt.last_verified == today.isoformat()
    assert rt.staleness_warning is False


def test_parse_partial_frontmatter(tmp_path):
    today = date(2026, 6, 2)
    _write_runtime(tmp_path, {
        "test": "go test ./...",
        "last_verified": today.isoformat(),
    })
    rt = _parse_human_runtime(tmp_path, today=today)
    assert rt.test == "go test ./..."
    assert rt.build == ""
    assert rt.staleness_warning is False


def test_parse_stale_when_last_verified_old(tmp_path):
    today = date(2026, 6, 2)
    old = (today - timedelta(days=60)).isoformat()
    _write_runtime(tmp_path, {
        "test": "pytest",
        "last_verified": old,
    })
    rt = _parse_human_runtime(tmp_path, today=today)
    assert rt.staleness_warning is True


def test_parse_stale_when_last_verified_missing(tmp_path):
    today = date(2026, 6, 2)
    _write_runtime(tmp_path, {"test": "pytest"})
    rt = _parse_human_runtime(tmp_path, today=today)
    assert rt.staleness_warning is True


def test_runtime_context_to_dict_includes_staleness_flag():
    rt = RuntimeContext(test="pytest", last_verified="2026-06-02",
                        staleness_warning=True)
    d = rt.to_dict()
    assert d["test"] == "pytest"
    assert d["_staleness_warning"] is True
    assert d["last_verified"] == "2026-06-02"
