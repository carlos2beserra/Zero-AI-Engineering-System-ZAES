"""Unit tests for pipeline/stage_1_discovery.py — run_discovery() and _Collector API."""

from __future__ import annotations

from pathlib import Path

import pytest

from maes.pipeline.stage_1_discovery import (
    _Collector,
    _MAX_TOTAL_CHARS,
    _TRUNCATION_MARKER,
    run_discovery,
)
from maes.pipeline.contracts import DiscoveryResult


# ─── _Collector public properties ────────────────────────────────────────────


def test_collector_truncated_files_returns_frozenset():
    col = _Collector()
    assert isinstance(col.truncated_files, frozenset)


def test_collector_truncated_files_reflects_add():
    col = _Collector()
    suffix = f"\n... {_TRUNCATION_MARKER} 6000 chars]"
    col.add("src/api/routes.py", "content" + suffix)
    assert "src/api/routes.py" in col.truncated_files


def test_collector_dirs_seen_returns_top_level_segments():
    col = _Collector()
    col.add("src/api/routes.py", "x")
    col.add("src/domain/entity.py", "x")
    col.add("tests/unit/test_x.py", "x")
    assert col.dirs_seen == frozenset({"src", "tests"})


def test_collector_total_chars_accumulates():
    col = _Collector()
    col.add("a.py", "hello")
    col.add("b.py", "world!")
    assert col.total_chars == len("hello") + len("world!")


def test_collector_budget_used_pct_is_float():
    col = _Collector()
    col.add("a.py", "x" * 10_000)
    assert isinstance(col.budget_used_pct, float)
    assert col.budget_used_pct == round(10_000 / _MAX_TOTAL_CHARS * 100, 1)


def test_collector_at_limit_after_budget_exhausted():
    col = _Collector()
    col.add("big.py", "x" * _MAX_TOTAL_CHARS)
    assert col.at_limit() is True
    assert col.add("extra.py", "small") is False


# ─── run_discovery() contract ─────────────────────────────────────────────────


def test_run_discovery_returns_discovery_result(tmp_path):
    result = run_discovery(tmp_path)
    assert isinstance(result, DiscoveryResult)


def test_run_discovery_empty_dir_produces_valid_result(tmp_path):
    result = run_discovery(tmp_path)
    assert result.files == ()
    assert isinstance(result.truncated_files, frozenset)
    assert isinstance(result.dirs_seen, frozenset)
    assert result.total_chars == 0
    assert result.budget_used_pct == 0.0


def test_run_discovery_collects_py_files(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('hello')", encoding="utf-8")
    result = run_discovery(tmp_path)
    collected_paths = {rel for rel, _ in result.files}
    assert any("main.py" in p for p in collected_paths)


def test_run_discovery_files_is_tuple_of_pairs(tmp_path):
    (tmp_path / "x.py").write_text("x = 1", encoding="utf-8")
    result = run_discovery(tmp_path)
    assert isinstance(result.files, tuple)
    for item in result.files:
        assert isinstance(item, tuple)
        assert len(item) == 2
        rel, content = item
        assert isinstance(rel, str)
        assert isinstance(content, str)


def test_run_discovery_ignores_node_modules(tmp_path):
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports = {}", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1", encoding="utf-8")
    result = run_discovery(tmp_path)
    assert not any("node_modules" in rel for rel, _ in result.files)
