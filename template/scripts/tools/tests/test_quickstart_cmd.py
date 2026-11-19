"""Tests for maes.quickstart_cmd — managed adapter directory sync (orphan cleanup).

The per-agent classification/scope logic was removed when the specialist agents
were consolidated into `maes-review`. What remains is the adapter-copy/vendor/CI
plumbing — most importantly `_sync_managed_directory`, which removes generated
files that no longer exist in the staging source. This is the mechanism that lets
a removed agent's generated command/rule files disappear from a project on sync.
"""

from maes.quickstart_cmd import _sync_managed_directory


def test_sync_managed_directory_removes_orphans(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()

    # Source has only maes-review; dst still has a stale specialist file.
    (src / "maes-review.md").write_text("review", encoding="utf-8")
    (dst / "maes-review.md").write_text("old", encoding="utf-8")
    (dst / "backend-architect.md").write_text("orphan", encoding="utf-8")

    _sync_managed_directory(src, dst)

    assert (dst / "maes-review.md").read_text(encoding="utf-8") == "review"
    assert not (dst / "backend-architect.md").exists(), "orphan must be pruned"


def test_sync_managed_directory_creates_missing(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "maes-review.md").write_text("review", encoding="utf-8")

    _sync_managed_directory(src, dst)

    assert (dst / "maes-review.md").read_text(encoding="utf-8") == "review"


def test_sync_managed_directory_prunes_empty_dirs(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    (src / "keep.md").write_text("k", encoding="utf-8")
    # Stale nested dir that should be removed once its only file is pruned.
    nested = dst / "nested"
    nested.mkdir(parents=True)
    (nested / "orphan.md").write_text("o", encoding="utf-8")

    _sync_managed_directory(src, dst)

    assert (dst / "keep.md").exists()
    assert not nested.exists(), "empty dir left after pruning must be removed"
