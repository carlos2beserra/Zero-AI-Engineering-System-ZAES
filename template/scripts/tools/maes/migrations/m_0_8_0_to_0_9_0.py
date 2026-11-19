"""Migration 0.8.0 → 0.9.0

Agent ID renames:
- `release`   → `release-manager`  (default agent, always present)
- `git-guide` → `dev-workflow`     (catalogue agent, only if installed)

Also removes stale adapter files generated for the old IDs so that `maes sync`
starts clean and only generates adapters for the new IDs.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from maes.migrations import Migration


_RENAMES: list[tuple[str, str, str, str, str, str]] = [
    # (old_id, old_name, old_file, new_id, new_name, new_file)
    (
        "release", "Release Manager", "release.agent.yaml",
        "release-manager", "Release Manager", "release-manager.agent.yaml",
    ),
    (
        "git-guide", "Git Guide", "git-guide.agent.yaml",
        "dev-workflow", "Dev Workflow", "dev-workflow.agent.yaml",
    ),
]

_ADAPTER_GLOBS = [
    ".claude/commands/{id}.md",
    ".cursor/rules/{id}.mdc",
    ".continue/rules/{id}.md",
    ".github/instructions/{id}.instructions.md",
    ".github/skills/{id}",
]


def _remove_stale_adapters(project_dir: Path, old_id: str) -> None:
    for pattern in _ADAPTER_GLOBS:
        target = project_dir / pattern.format(id=old_id)
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()


def _rename_agent(agents_dir: Path, project_dir: Path, rename: tuple) -> None:
    old_id, old_name, old_file, new_id, new_name, new_file = rename
    old_path = agents_dir / old_file
    new_path = agents_dir / new_file
    if not old_path.exists():
        return

    content = old_path.read_text(encoding="utf-8")
    content = re.sub(
        rf'^id:\s*{re.escape(old_id)}\s*$',
        f'id: {new_id}',
        content,
        flags=re.MULTILINE,
    )
    content = re.sub(
        rf'^name:\s*{re.escape(old_name)}\s*$',
        f'name: {new_name}',
        content,
        flags=re.MULTILINE,
    )
    new_path.write_text(content, encoding="utf-8")
    old_path.unlink()
    _remove_stale_adapters(project_dir, old_id)


def _run(maes_dir: Path) -> None:
    agents_dir = maes_dir / "agents"
    project_dir = maes_dir.parent
    for rename in _RENAMES:
        _rename_agent(agents_dir, project_dir, rename)


MIGRATION = Migration(
    from_version="0.8.0",
    to_version="0.9.0",
    description="Rename agents: release→release-manager, git-guide→dev-workflow; remove stale adapters",
    run=_run,
)
