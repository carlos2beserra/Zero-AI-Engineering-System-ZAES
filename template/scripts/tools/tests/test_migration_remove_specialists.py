"""Tests for the 1.0.0 → 1.1.0 migration that consolidates specialist agents."""

import yaml

from maes.migrations.m_1_0_0_to_1_1_0 import _run, _REMOVED_AGENTS


def _make_project(tmp_path):
    project = tmp_path
    maes = project / ".maes"
    (maes / "agents").mkdir(parents=True)
    (maes / "evals" / "scenarios").mkdir(parents=True)
    (maes / "adapters" / "claude" / ".claude" / "commands").mkdir(parents=True)
    (project / ".claude" / "commands").mkdir(parents=True)
    (project / ".cursor" / "rules").mkdir(parents=True)
    (project / ".github" / "instructions").mkdir(parents=True)
    return project, maes


def test_migration_removes_sources_generated_and_fixes_config(tmp_path):
    project, maes = _make_project(tmp_path)

    # Source agent yamls: 6 specialists + the survivors.
    for aid in (*_REMOVED_AGENTS, "maes-review", "maes-analyze"):
        (maes / "agents" / f"{aid}.agent.yaml").write_text(f"id: {aid}\n", encoding="utf-8")

    # Generated files in several IDE dirs.
    for aid in _REMOVED_AGENTS:
        (project / ".claude" / "commands" / f"{aid}.md").write_text("x", encoding="utf-8")
        (project / ".cursor" / "rules" / f"{aid}.mdc").write_text("x", encoding="utf-8")
        (project / ".github" / "instructions" / f"{aid}.instructions.md").write_text("x", encoding="utf-8")
    (project / ".claude" / "commands" / "maes-review.md").write_text("keep", encoding="utf-8")

    # config.yaml lists the 6 specialists.
    (maes / "config.yaml").write_text(
        yaml.dump({"project": {"name": "p"}, "agents": list(_REMOVED_AGENTS)}),
        encoding="utf-8",
    )

    # An eval scenario bound to a removed agent.
    (maes / "evals" / "scenarios" / "review-backend.eval.yaml").write_text(
        "id: review-backend\nagent: backend-architect\ntask: x\n", encoding="utf-8"
    )

    _run(maes)

    # Sources removed; survivors kept.
    for aid in _REMOVED_AGENTS:
        assert not (maes / "agents" / f"{aid}.agent.yaml").exists()
    assert (maes / "agents" / "maes-review.agent.yaml").exists()
    assert (maes / "agents" / "maes-analyze.agent.yaml").exists()

    # Generated files removed; survivor kept.
    for aid in _REMOVED_AGENTS:
        assert not (project / ".claude" / "commands" / f"{aid}.md").exists()
        assert not (project / ".cursor" / "rules" / f"{aid}.mdc").exists()
        assert not (project / ".github" / "instructions" / f"{aid}.instructions.md").exists()
    assert (project / ".claude" / "commands" / "maes-review.md").exists()

    # Staging cleared.
    assert not (maes / "adapters").exists()

    # config.yaml agents rewritten to the target set.
    cfg = yaml.safe_load((maes / "config.yaml").read_text(encoding="utf-8"))
    assert "maes-review" in cfg["agents"]
    assert not any(a in cfg["agents"] for a in _REMOVED_AGENTS)

    # Eval scenario agent rewritten.
    scen = (maes / "evals" / "scenarios" / "review-backend.eval.yaml").read_text(encoding="utf-8")
    assert "agent: maes-review" in scen
    assert "backend-architect" not in scen


def test_migration_is_idempotent(tmp_path):
    project, maes = _make_project(tmp_path)
    (maes / "agents" / "maes-review.agent.yaml").write_text("id: maes-review\n", encoding="utf-8")
    (maes / "config.yaml").write_text(yaml.dump({"agents": ["maes-review"]}), encoding="utf-8")
    # Running on an already-clean project must not raise.
    _run(maes)
    _run(maes)
    assert (maes / "agents" / "maes-review.agent.yaml").exists()
