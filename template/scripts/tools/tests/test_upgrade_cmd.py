"""Tests for the `maes upgrade` orchestrator and its version helpers.

Complements test_migration_remove_specialists.py (which tests one concrete
migration) by covering the orchestration itself: version reading/writing,
migration selection (find_path), corrupted-config handling, the run_upgrade
scenarios, partial-failure resumption, and deterministic auto-discovery.
"""

from __future__ import annotations

import importlib
import pkgutil
import types
from pathlib import Path

import pytest
import yaml

from maes import migrations, upgrade_cmd, versioning
from maes.migrations import Migration, find_path
from maes.versioning import (
    ProjectConfigError,
    read_project_version,
    version_tuple,
)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def make_project(tmp_path: Path, *, version: str | None = None, extra: str = "") -> Path:
    """Create a synthetic project with .maes/config.yaml + context/human/."""
    maes_dir = tmp_path / ".maes"
    (maes_dir / "context" / "human").mkdir(parents=True)
    cfg = "project:\n  name: demo\n" + extra
    if version is not None:
        cfg += f'meta:\n  maes_version: "{version}"\n'
    (maes_dir / "config.yaml").write_text(cfg, encoding="utf-8")
    return maes_dir


def marker_migration(from_v: str, to_v: str, marker: Path) -> Migration:
    """A guarded, idempotent fake migration that touches `marker` once."""
    def _run(maes_dir: Path) -> None:
        if marker.exists():          # guard → idempotent
            return
        marker.write_text("x", encoding="utf-8")
    return Migration(from_version=from_v, to_version=to_v,
                     description=f"{from_v}->{to_v}", run=_run)


@pytest.fixture
def isolate_side_effects(monkeypatch):
    """Neutralise template copy / finalize / sync so tests exercise orchestration only."""
    monkeypatch.setattr("maes.init_cmd._copy_templates", lambda *a, **k: None)
    monkeypatch.setattr(upgrade_cmd, "_finalize_upgrade", lambda *a, **k: None)
    monkeypatch.setattr(upgrade_cmd, "_run_sync_local", lambda *a, **k: None)
    # Stub the timestamped backup (real backup is covered by the dedicated
    # _apply_migrations test); avoids same-second copytree collisions when a test
    # runs run_upgrade twice (partial-failure resume).
    monkeypatch.setattr(upgrade_cmd, "_backup_human",
                        lambda maes_dir: maes_dir / "cache" / "backup-stub")


# --------------------------------------------------------------------------- #
# version_tuple — reduced-SemVer contract
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("raw,expected", [
    ("0.0.0", (0, 0, 0)),
    ("1.3.0", (1, 3, 0)),
    ("0.12.3", (0, 12, 3)),
    ("1", (0, 0, 0)),            # out of contract
    ("1.0", (0, 0, 0)),          # out of contract
    ("1.0-beta", (0, 0, 0)),     # out of contract
    ("1.0.0+build", (0, 0, 0)),  # out of contract
    ("", (0, 0, 0)),
])
def test_version_tuple_contract(raw, expected):
    assert version_tuple(raw) == expected


# --------------------------------------------------------------------------- #
# read_project_version — new vs corrupted vs pre-versioning
# --------------------------------------------------------------------------- #
def test_read_absent_config_is_new_project(tmp_path):
    maes_dir = tmp_path / ".maes"
    maes_dir.mkdir()
    assert read_project_version(maes_dir, strict=True) == "0.0.0"
    assert read_project_version(maes_dir, strict=False) == "0.0.0"


def test_read_valid_without_meta_is_pre_versioning(tmp_path):
    maes_dir = make_project(tmp_path)  # no meta.maes_version
    assert read_project_version(maes_dir, strict=True) == "0.0.0"


def test_read_valid_version(tmp_path):
    maes_dir = make_project(tmp_path, version="1.2.0")
    assert read_project_version(maes_dir, strict=True) == "1.2.0"


def test_read_empty_file_is_not_corruption(tmp_path):
    maes_dir = tmp_path / ".maes"
    maes_dir.mkdir()
    (maes_dir / "config.yaml").write_text("", encoding="utf-8")
    assert read_project_version(maes_dir, strict=True) == "0.0.0"


def test_read_broken_yaml_raises_when_strict(tmp_path):
    maes_dir = tmp_path / ".maes"
    maes_dir.mkdir()
    (maes_dir / "config.yaml").write_text("meta:\n  x: [unclosed\n", encoding="utf-8")
    with pytest.raises(ProjectConfigError):
        read_project_version(maes_dir, strict=True)
    # lenient never raises
    assert read_project_version(maes_dir, strict=False) == "0.0.0"


def test_read_non_mapping_toplevel_raises_when_strict(tmp_path):
    maes_dir = tmp_path / ".maes"
    maes_dir.mkdir()
    (maes_dir / "config.yaml").write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ProjectConfigError):
        read_project_version(maes_dir, strict=True)
    assert read_project_version(maes_dir, strict=False) == "0.0.0"


def test_write_then_read_roundtrip(tmp_path):
    maes_dir = make_project(tmp_path, version="1.0.0")
    upgrade_cmd._write_project_version(maes_dir, "1.2.0")
    assert read_project_version(maes_dir, strict=True) == "1.2.0"


def test_write_is_noop_without_config(tmp_path):
    maes_dir = tmp_path / ".maes"
    maes_dir.mkdir()
    upgrade_cmd._write_project_version(maes_dir, "1.2.0")  # must not raise
    assert not (maes_dir / "config.yaml").exists()


# --------------------------------------------------------------------------- #
# find_path — selection, gaps, no-op
# --------------------------------------------------------------------------- #
def test_find_path_full_chain_from_zero():
    path = find_path("0.0.0", "1.3.0")
    assert [(m.from_version, m.to_version) for m in path] == [
        ("0.0.0", "0.1.0"), ("0.8.0", "0.9.0"),
        ("0.12.3", "0.13.0"), ("1.0.0", "1.1.0"),
    ]


def test_find_path_no_migrations_when_ahead():
    assert find_path("1.1.0", "1.3.0") == []
    assert find_path("1.3.0", "1.3.0") == []


def test_find_path_supports_gaps():
    # A project at 0.5.0 (never at 0.8.0) still selects 0.8.0->0.9.0 onward; the
    # migrations' guards make applying a "skipped-from" migration harmless.
    got = [(m.from_version, m.to_version) for m in find_path("0.5.0", "1.3.0")]
    assert got == [("0.8.0", "0.9.0"), ("0.12.3", "0.13.0"), ("1.0.0", "1.1.0")]


def test_find_path_target_below_current():
    assert find_path("1.3.0", "1.0.0") == []


# --------------------------------------------------------------------------- #
# run_upgrade — orchestration scenarios
# --------------------------------------------------------------------------- #
def test_run_upgrade_applies_and_stamps(tmp_path, monkeypatch, isolate_side_effects):
    maes_dir = make_project(tmp_path, version="1.0.0")
    marker = tmp_path / "applied.txt"
    monkeypatch.setattr(migrations, "find_path",
                        lambda cur, tgt: [marker_migration("1.0.0", "1.3.0", marker)])
    rc = upgrade_cmd.run_upgrade(tmp_path, skip_sync=True)
    assert rc == 0
    assert marker.exists()
    assert read_project_version(maes_dir, strict=True) == versioning_cli_version()


def test_run_upgrade_dry_run_changes_nothing(tmp_path, monkeypatch, isolate_side_effects):
    maes_dir = make_project(tmp_path, version="1.0.0")
    marker = tmp_path / "applied.txt"
    monkeypatch.setattr(migrations, "find_path",
                        lambda cur, tgt: [marker_migration("1.0.0", "1.3.0", marker)])
    rc = upgrade_cmd.run_upgrade(tmp_path, dry_run=True)
    assert rc == 0
    assert not marker.exists()
    assert read_project_version(maes_dir, strict=True) == "1.0.0"  # unchanged


def test_run_upgrade_already_up_to_date(tmp_path, monkeypatch, isolate_side_effects):
    maes_dir = make_project(tmp_path, version=versioning_cli_version())
    # find_path must not even be consulted; make it explode if called.
    monkeypatch.setattr(migrations, "find_path",
                        lambda *a: (_ for _ in ()).throw(AssertionError("should not run")))
    rc = upgrade_cmd.run_upgrade(tmp_path, skip_sync=True)
    assert rc == 0
    assert read_project_version(maes_dir, strict=True) == versioning_cli_version()


def test_run_upgrade_new_project_pre_versioning(tmp_path, monkeypatch, isolate_side_effects):
    maes_dir = make_project(tmp_path)  # no meta → 0.0.0
    marker = tmp_path / "applied.txt"
    monkeypatch.setattr(migrations, "find_path",
                        lambda cur, tgt: [marker_migration("0.0.0", "1.3.0", marker)])
    rc = upgrade_cmd.run_upgrade(tmp_path, skip_sync=True)
    assert rc == 0
    assert marker.exists()


def test_run_upgrade_aborts_on_corrupted_config(tmp_path, monkeypatch, isolate_side_effects):
    maes_dir = tmp_path / ".maes"
    (maes_dir / "context" / "human").mkdir(parents=True)
    (maes_dir / "config.yaml").write_text("meta:\n  x: [unclosed\n", encoding="utf-8")
    # find_path must never be reached on a corrupted config.
    monkeypatch.setattr(migrations, "find_path",
                        lambda *a: (_ for _ in ()).throw(AssertionError("no migration on corruption")))
    rc = upgrade_cmd.run_upgrade(tmp_path, skip_sync=True)
    assert rc == 1


def test_run_upgrade_no_migrations_stamps_only(tmp_path, monkeypatch, isolate_side_effects):
    maes_dir = make_project(tmp_path, version="1.2.0")
    monkeypatch.setattr(migrations, "find_path", lambda cur, tgt: [])
    rc = upgrade_cmd.run_upgrade(tmp_path, skip_sync=True)
    assert rc == 0
    assert read_project_version(maes_dir, strict=True) == versioning_cli_version()


# --------------------------------------------------------------------------- #
# _apply_migrations — error handling
# --------------------------------------------------------------------------- #
def test_apply_migrations_aborts_and_preserves_backup(tmp_path):
    maes_dir = make_project(tmp_path, version="1.0.0")

    def _boom(_):
        raise RuntimeError("kaboom")

    bad = Migration("1.0.0", "1.1.0", "always fails", _boom)
    rc = upgrade_cmd._apply_migrations(maes_dir, [bad])
    assert rc == 1
    backups = list((maes_dir / "cache").glob("upgrade-backup-*"))
    assert backups, "backup of context/human/ should be preserved on failure"


# --------------------------------------------------------------------------- #
# partial-failure resumption (idempotent re-run)
# --------------------------------------------------------------------------- #
def test_partial_failure_then_resume(tmp_path, monkeypatch, isolate_side_effects):
    maes_dir = make_project(tmp_path, version="0.0.0")
    calls = {"m1": 0, "m2": 0, "m3": 0}
    state = {"m3_fixed": False}
    g1, g2 = tmp_path / "g1", tmp_path / "g2"

    def guarded(counter_key, guard):
        def _run(_):
            if guard.exists():
                return                       # idempotent no-op on re-run
            calls[counter_key] += 1
            guard.write_text("x", encoding="utf-8")
        return _run

    def _run_m3(_):
        calls["m3"] += 1
        if not state["m3_fixed"]:
            raise RuntimeError("m3 fails first time")

    chain = [
        Migration("0.0.0", "0.1.0", "m1", guarded("m1", g1)),
        Migration("0.1.0", "0.2.0", "m2", guarded("m2", g2)),
        Migration("0.2.0", "1.3.0", "m3", _run_m3),
    ]
    monkeypatch.setattr(migrations, "find_path", lambda cur, tgt: chain)

    # Run 1: m1, m2 apply; m3 fails → rc=1, version NOT stamped.
    rc1 = upgrade_cmd.run_upgrade(tmp_path, skip_sync=True)
    assert rc1 == 1
    assert (calls["m1"], calls["m2"]) == (1, 1)
    assert read_project_version(maes_dir, strict=True) == "0.0.0"  # not stamped

    # Fix m3 and re-run: m1/m2 are no-ops (guards), m3 now succeeds.
    state["m3_fixed"] = True
    rc2 = upgrade_cmd.run_upgrade(tmp_path, skip_sync=True)
    assert rc2 == 0
    assert (calls["m1"], calls["m2"]) == (1, 1)  # NOT re-executed
    assert calls["m3"] == 2                       # failed once + succeeded once
    assert read_project_version(maes_dir, strict=True) == versioning_cli_version()


# --------------------------------------------------------------------------- #
# auto-discovery — determinism + fail-loud
# --------------------------------------------------------------------------- #
def test_discovery_finds_all_without_dupes_or_omissions():
    migs = migrations._load_migrations()
    froms = [m.from_version for m in migs]
    assert froms == sorted(froms, key=migrations._ver)          # ordered by from_version
    assert len(froms) == len(set(froms))                        # no duplicates
    assert set(froms) == {"0.0.0", "0.8.0", "0.12.3", "1.0.0"}  # no omissions


def test_discovery_order_independent_of_input_order():
    import random
    migs = migrations._load_migrations()
    shuffled = migs[:]
    random.Random(20260712).shuffle(shuffled)
    resorted = sorted(shuffled, key=lambda m: migrations._ver(m.from_version))
    assert [m.from_version for m in resorted] == [m.from_version for m in migs]


def test_discovery_fails_loud_when_module_missing_MIGRATION(monkeypatch):
    fake = types.ModuleType("maes.migrations.m_bad")  # no MIGRATION attribute
    monkeypatch.setattr(pkgutil, "iter_modules",
                        lambda path: [types.SimpleNamespace(name="m_bad")])
    monkeypatch.setattr(importlib, "import_module", lambda name: fake)
    with pytest.raises(RuntimeError, match="MIGRATION"):
        migrations._load_migrations()


# --------------------------------------------------------------------------- #
# regression: `maes upgrade` must COMPILE agents to the root IDE adapters, not
# only copy them into .maes/agents/. The upgrade's sync used to discard the
# generate_adapters() output and never write the root dirs, so new/updated
# agents were never seen by the AI tools. This runs the real canonical sync.
# --------------------------------------------------------------------------- #
def test_upgrade_compiles_agents_to_root_adapters(tmp_path):
    maes_dir = tmp_path / ".maes"
    (maes_dir / "context" / "human").mkdir(parents=True)
    (maes_dir / "agents").mkdir()
    (maes_dir / "config.yaml").write_text(
        'project:\n  name: demo\nadapters:\n  - claude\nmeta:\n  maes_version: "1.1.0"\n',
        encoding="utf-8",
    )

    rc = upgrade_cmd.run_upgrade(tmp_path)  # skip_sync=False → real canonical sync
    assert rc == 0

    # every framework agent copied into .maes/agents/ must be compiled into the
    # root .claude/commands/ adapters.
    agent_ids = {p.name[: -len(".agent.yaml")]
                 for p in (maes_dir / "agents").glob("*.agent.yaml")}
    commands = {p.stem for p in (tmp_path / ".claude" / "commands").glob("*.md")}
    assert agent_ids, "expected framework agents present after upgrade"
    assert agent_ids <= commands, f"agents not compiled to root: {agent_ids - commands}"
    # the Fase-1 create agent specifically must reach the AI tool
    assert (tmp_path / ".claude" / "commands" / "maes-create.md").exists()


# --------------------------------------------------------------------------- #
def versioning_cli_version() -> str:
    from maes import __version__
    return __version__.split("+")[0]
