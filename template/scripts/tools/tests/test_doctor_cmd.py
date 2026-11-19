"""Tests for maes.doctor_cmd — agent scope path invariant check."""

import pytest
import yaml
from pathlib import Path

from maes.doctor_cmd import _check_agent_scope_paths


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _write_agent(path: Path, scope_paths: list | None, enabled: bool | None = None) -> None:
    data: dict = {"id": path.stem, "scope": {}}
    if scope_paths is not None:
        data["scope"]["paths"] = scope_paths
    if enabled is not None:
        data["enabled"] = enabled
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")


def _collect(agents_dir: Path) -> tuple[list[str], list[str], list[str]]:
    ok_msgs: list[str] = []
    warn_msgs: list[str] = []
    err_msgs: list[str] = []
    _check_agent_scope_paths(
        agents_dir,
        ok=ok_msgs.append,
        warn=warn_msgs.append,
    )
    return ok_msgs, warn_msgs, err_msgs


# ─── 1. No agents directory ──────────────────────────────────────────────────


def test_no_agents_dir_is_silent(tmp_path):
    ok_msgs, warn_msgs, err_msgs = _collect(tmp_path / "nonexistent")
    assert ok_msgs == []
    assert warn_msgs == []
    assert err_msgs == []


# ─── 2. Empty agents directory ───────────────────────────────────────────────


def test_empty_agents_dir_is_silent(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    ok_msgs, warn_msgs, err_msgs = _collect(agents)
    assert ok_msgs == []
    assert warn_msgs == []
    assert err_msgs == []


# ─── 3. Agent without scope.paths ────────────────────────────────────────────


def test_agent_without_scope_paths_emits_no_warning(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "minimal.agent.yaml").write_text(
        yaml.dump({"id": "minimal", "scope": {}}), encoding="utf-8"
    )
    _, warn_msgs, err_msgs = _collect(agents)
    assert warn_msgs == []
    assert err_msgs == []


# ─── 4. Valid paths emit ok ───────────────────────────────────────────────────


def test_valid_paths_emit_ok(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    _write_agent(agents / "maes-review.agent.yaml", [
        "app/services/**",
        "**/guards/**",
        "src/api/v1/**",
    ])
    ok_msgs, _, err_msgs = _collect(agents)
    assert err_msgs == []
    assert len(ok_msgs) == 1
    assert "valid" in ok_msgs[0]


# ─── 5. Invalid path emits warning ───────────────────────────────────────────


def test_invalid_path_emits_warning(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    _write_agent(agents / "maes-review.agent.yaml", [
        "app/services/job/ and app/services/jobs/**",
    ])
    _, warn_msgs, err_msgs = _collect(agents)
    assert err_msgs == []
    assert len(warn_msgs) == 1
    assert "maes-review.agent.yaml" in warn_msgs[0]
    assert "app/services/job/ and app/services/jobs/**" in warn_msgs[0]
    assert "single-path-unit" in warn_msgs[0]


# ─── 6. Multiple agents — only invalid reported ───────────────────────────────


def test_multiple_agents_only_invalid_reported(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    _write_agent(agents / "maes-review.agent.yaml", [
        "app/services/job/ and app/services/jobs/**",
    ])
    _write_agent(agents / "sample-agent.agent.yaml", ["web/src/**"])

    _, warn_msgs, _ = _collect(agents)
    assert len(warn_msgs) == 1
    assert "maes-review" in warn_msgs[0]
    assert "sample-agent" not in warn_msgs[0]


# ─── 7. Multiple violations in the same agent ────────────────────────────────


def test_multiple_violations_in_same_agent(tmp_path):
    agents = tmp_path / "agents"
    agents.mkdir()
    _write_agent(agents / "maes-review.agent.yaml", [
        "app/services/job/ and app/services/jobs/**",   # space connector
        "app/workers/ai & app/workers/ingestion/**",     # ampersand connector
        "app/valid/path/**",                             # valid — must not appear
    ])
    _, warn_msgs, _ = _collect(agents)
    assert len(warn_msgs) == 2
    combined = " ".join(warn_msgs)
    assert "and" in combined
    assert "&" in combined
    assert "app/valid/path/**" not in combined


# ─── 8. Reuse of the same invariant as the pipeline ──────────────────────────


def test_uses_same_invariant_as_pipeline(tmp_path):
    """Doctor and pipeline share _is_single_path_unit as single source of truth."""
    from maes.quickstart_cmd import _is_single_path_unit

    agents = tmp_path / "agents"
    agents.mkdir()

    valid_path = "app/services/job/**"
    invalid_path = "app/services/job/ and app/services/jobs/**"

    # Confirm the invariant function agrees with doctor for valid path
    _write_agent(agents / "a.agent.yaml", [valid_path])
    _, warn_msgs, _ = _collect(agents)
    assert warn_msgs == []
    assert _is_single_path_unit(valid_path) is True

    # Confirm the invariant function agrees with doctor for invalid path
    (agents / "a.agent.yaml").unlink()
    _write_agent(agents / "a.agent.yaml", [invalid_path])
    _, warn_msgs, _ = _collect(agents)
    assert len(warn_msgs) == 1
    assert _is_single_path_unit(invalid_path) is False
