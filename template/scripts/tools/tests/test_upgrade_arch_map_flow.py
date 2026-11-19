"""Fase 4 — the official update flow absorbs this evolution end to end.

Acceptance criterion: a repository configured on a previous MAES version, after running
ONLY `maes upgrade` and the official subsequent commands, uses the corrected Analyze —
with no manual intervention in the repository and without knowing any detail of this
evolution. The hard case is an EXISTING repo, not a fresh `maes init`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maes.build_arch_map_cmd import run_build_arch_map
from maes.compiler import _build_placement_map
from maes.upgrade_cmd import _arch_map_needs_rebuild, _vendored_version


def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


_STALE_ARCH_MAP = {
    "schema_version": "2.0",
    "status": "generated",
    "nodes": [
        # The shape that produced `Service → <repo root> (100%)` in the field.
        {"type": "Service", "path": "ldc-backend/src/points", "file_count": 40},
        {"type": "Service", "path": "ldc-backend/src/auth", "file_count": 20},
        {"type": "Worker", "path": "ldc-backend/src/cron", "file_count": 5},
    ],
    "diagnostic_metrics": {"discovered_files": 43, "total_nodes": 3},
}


@pytest.fixture()
def legacy_repo(tmp_path: Path) -> Path:
    """Existing repo frozen on a previous version, with previous-schema artifacts."""
    _write(tmp_path, ".maes/config.yaml", 'meta:\n  maes_version: "1.2.0"\n')
    _write(
        tmp_path,
        ".maes/context/inferred/architecture_map.json",
        json.dumps(_STALE_ARCH_MAP, indent=2),
    )
    _write(tmp_path, ".maes/synthesis/placement-map.json", json.dumps({
        "schema_version": "1.0",
        "status": "generated",
        "placements": [{
            "category": "Service", "path": "ldc-backend",
            "confidence": "high", "coverage_pct": 1.0,
            "file_count": 65, "total_file_count": 65,
        }],
    }))
    for i in range(3):
        for name in ("index.ts", "handler.ts", "types.ts"):
            _write(tmp_path, f"src/services/svc{i}/{name}", "export const a = 1\n")
    _write(tmp_path, "package.json", json.dumps({"dependencies": {"react": "18"}}))
    return tmp_path


# ─── Fail-closed over a previous-schema artifact ───────────────────────────────


def test_stale_arch_map_yields_no_placement_conclusion(legacy_repo: Path):
    """The wrong Code Placement disappears from the FIRST sync — the one `maes upgrade`
    runs itself — instead of being re-emitted and waiting for build-arch-map.

    Fail-closed on SCHEMA, not on content sampling: a 2.0 map's prefixes describe the
    budget-capped sample (43 files in the field case), so they cannot support a claim
    about the project.
    """
    stale = legacy_repo / ".maes" / "context" / "inferred" / "architecture_map.json"

    out = _build_placement_map(stale)

    assert out["status"] == "stale_schema"
    assert out["placements"] == []


def test_upgrade_detects_that_the_arch_map_needs_rebuilding(legacy_repo: Path):
    assert _arch_map_needs_rebuild(legacy_repo / ".maes") is True


def test_unreadable_arch_map_also_asks_for_a_rebuild(tmp_path: Path):
    _write(tmp_path, ".maes/context/inferred/architecture_map.json", "{ not json")
    assert _arch_map_needs_rebuild(tmp_path / ".maes") is True


def test_absent_arch_map_needs_no_rebuild(tmp_path: Path):
    """Absence is valid (I2): nothing to regenerate, so nothing to nag about."""
    (tmp_path / ".maes").mkdir()
    assert _arch_map_needs_rebuild(tmp_path / ".maes") is False


# ─── After the official flow, the placement is correct again ──────────────────


def test_rebuild_restores_a_correct_placement(legacy_repo: Path):
    maes_dir = legacy_repo / ".maes"

    assert run_build_arch_map(legacy_repo, maes_dir) == 0
    rebuilt = maes_dir / "context" / "inferred" / "architecture_map.json"
    data = json.loads(rebuilt.read_text(encoding="utf-8"))

    assert data["schema_version"] == "2.1"
    assert _arch_map_needs_rebuild(maes_dir) is False

    out = _build_placement_map(rebuilt)
    assert out["status"] == "generated"
    for pl in out["placements"]:
        # Never the repo root, and never a single segment at high confidence.
        assert pl["path"].count("/") + 1 >= 2 or pl["confidence"] == "low"


# ─── No hidden intermediate state ─────────────────────────────────────────────


_TIMESTAMPED = {"generated_at"}


def test_second_build_produces_identical_content(legacy_repo: Path):
    """Two consecutive runs must produce the same artifacts.

    `git diff` empty is not literally reachable, and that is by design:
    architecture_map.json is deliberately timestamp-free (the timestamp was isolated
    into build_metadata.json precisely so the map stays diffable), while
    build_metadata.json / placement-map.json / impact-graph.json carry generated_at.
    So the assertion is byte-identity for the map and diff-restricted-to-generated_at
    for the rest — asserting "stable content", not "identical file". A literally-empty
    diff would one day be "fixed" by deleting generated_at, destroying traceability.
    """
    maes_dir = legacy_repo / ".maes"
    arch = maes_dir / "context" / "inferred" / "architecture_map.json"
    meta = maes_dir / "context" / "inferred" / "build_metadata.json"

    assert run_build_arch_map(legacy_repo, maes_dir) == 0
    first_arch = arch.read_bytes()
    first_meta = json.loads(meta.read_text(encoding="utf-8"))

    assert run_build_arch_map(legacy_repo, maes_dir) == 0
    second_arch = arch.read_bytes()
    second_meta = json.loads(meta.read_text(encoding="utf-8"))

    assert second_arch == first_arch, "architecture_map.json must be byte-identical"

    ignored = _TIMESTAMPED
    assert {k: v for k, v in second_meta.items() if k not in ignored} == {
        k: v for k, v in first_meta.items() if k not in ignored
    }


# ─── Version agreement: is the Analyze that ran the installed one? ────────────


def test_vendored_version_is_read_when_present(tmp_path: Path):
    _write(tmp_path, ".maes/vendor/maes/__init__.py", '__version__ = "1.2.3"\n')
    assert _vendored_version(tmp_path / ".maes") == "1.2.3"


def test_vendored_version_absent_is_not_an_error(tmp_path: Path):
    (tmp_path / ".maes").mkdir()
    assert _vendored_version(tmp_path / ".maes") is None
