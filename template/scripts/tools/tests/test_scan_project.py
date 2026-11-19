"""Public contract of scan_project() — the single source of truth for enumeration.

These tests assert the CONTRACT declared in ADR 0009, not incidental behaviour.
scan_project became shared pipeline infrastructure: five consumers depend on it, so
what is pinned here is what the rest of the pipeline is allowed to assume without
verifying.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from maes.models import CANONICAL_SOURCE_EXTENSIONS
from maes.pipeline.stage_1_discovery import (
    _MAX_TOTAL_CHARS,
    _FileInventory,
    scan_project,
)


def _write(root: Path, rel: str, content: str = "x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    _write(tmp_path, "src/auth/service.ts", "export const a = 1\n")
    _write(tmp_path, "src/auth/user.entity.ts", "class User {}\n")
    _write(tmp_path, "src/ui/Button.tsx", "export default () => null\n")
    _write(tmp_path, "src/ui/Card.jsx", "export default () => null\n")
    _write(tmp_path, "app/models/user.py", "class User: pass\n")
    _write(tmp_path, "README.md", "# hi\n")
    _write(tmp_path, "package.json", "{}\n")
    _write(tmp_path, "node_modules/lib/index.ts", "ignored\n")
    _write(tmp_path, "dist/bundle.js", "ignored\n")
    return tmp_path


# ─── Completeness ─────────────────────────────────────────────────────────────


def test_inventory_lists_every_source_file(project: Path):
    inv = scan_project(project)
    assert set(inv.source_paths) == {
        "src/auth/service.ts",
        "src/auth/user.entity.ts",
        "src/ui/Button.tsx",
        "src/ui/Card.jsx",
        "app/models/user.py",
    }


def test_inventory_includes_non_source_in_all_paths(project: Path):
    inv = scan_project(project)
    assert "README.md" in inv.all_paths
    assert "package.json" in inv.all_paths
    # ...but they are not part of the POPULATION
    assert "README.md" not in inv.source_paths


def test_source_paths_is_subset_of_all_paths(project: Path):
    inv = scan_project(project)
    assert set(inv.source_paths) <= set(inv.all_paths)


def test_ignored_dirs_are_excluded(project: Path):
    inv = scan_project(project)
    assert not [p for p in inv.all_paths if p.startswith(("node_modules/", "dist/"))]


# ─── Normalization ────────────────────────────────────────────────────────────


def test_paths_are_relative_and_posix(project: Path):
    inv = scan_project(project)
    for rel in inv.all_paths:
        assert "\\" not in rel, f"backslash leaked into inventory: {rel!r}"
        assert not Path(rel).is_absolute(), f"absolute path in inventory: {rel!r}"


# ─── Determinism ──────────────────────────────────────────────────────────────


def test_enumeration_is_deterministic(project: Path):
    assert scan_project(project) == scan_project(project)


def test_order_is_sorted_not_os_dependent(project: Path):
    inv = scan_project(project)
    assert list(inv.all_paths) == sorted(inv.all_paths)
    assert list(inv.source_paths) == sorted(inv.source_paths)


def test_no_duplicates(project: Path):
    inv = scan_project(project)
    assert len(inv.all_paths) == len(set(inv.all_paths))
    assert len(inv.source_paths) == len(set(inv.source_paths))


# ─── Symlinks: the same file must never appear under two paths ─────────────────


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlink creation needs elevation on Windows"
)
def test_symlinked_source_file_is_not_enumerated_twice(tmp_path: Path):
    real = _write(tmp_path, "src/real.ts", "export const a = 1\n")
    (tmp_path / "src" / "alias.ts").symlink_to(real)

    inv = scan_project(tmp_path)

    assert "src/real.ts" in inv.source_paths
    assert "src/alias.ts" not in inv.source_paths, (
        "a symlink duplicates content under a second path, inflating the population "
        "and potentially producing two nodes for the same code"
    )


# ─── Temporal stability: only path and existence matter ───────────────────────


def test_metadata_changes_do_not_affect_enumeration(project: Path):
    before = scan_project(project)

    # Touch mtime on every file — if enumeration ever depended on metadata (e.g.
    # prioritising recently-changed files), the same commit would produce different
    # maps on two machines.
    for rel in before.all_paths:
        p = project / rel
        import os
        os.utime(p, (1_000_000, 1_000_000))

    assert scan_project(project) == before


# ─── No classification, no budget ─────────────────────────────────────────────


def test_inventory_exposes_only_the_two_contract_fields():
    """No frontend_paths / entity_paths / config_paths: dividing by architectural
    MEANING belongs to consumers, not to the inventory (ADR 0009)."""
    fields = set(_FileInventory.__dataclass_fields__)
    assert fields == {"all_paths", "source_paths"}


def test_enumeration_is_independent_of_content_budget(tmp_path: Path):
    # Far more source content than the collection budget; enumeration must still be
    # complete, because it never reads a byte.
    big = "y" * 20_000
    for i in range(20):
        _write(tmp_path, f"src/mod{i:02d}/file.ts", big)

    inv = scan_project(tmp_path)

    assert len(inv.source_paths) == 20
    assert 20 * len(big) > _MAX_TOTAL_CHARS


def test_every_canonical_extension_is_recognized(tmp_path: Path):
    for i, ext in enumerate(sorted(CANONICAL_SOURCE_EXTENSIONS)):
        _write(tmp_path, f"src/f{i}{ext}", "x")
    inv = scan_project(tmp_path)
    assert len(inv.source_paths) == len(CANONICAL_SOURCE_EXTENSIONS)
