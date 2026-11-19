"""Migration 0.0.0 → 0.1.0

Adds the `meta.maes_version` field to .maes/config.yaml for projects that
were created before MAES introduced version tracking.
"""
from __future__ import annotations

from pathlib import Path

from maes.migrations import Migration

_CONFIG_YAML = "config.yaml"


def _run(maes_dir: Path) -> None:
    config_path = maes_dir / _CONFIG_YAML
    if not config_path.exists():
        return

    text = config_path.read_text(encoding="utf-8")
    if "maes_version:" in text:
        return

    meta_block = '\nmeta:\n  maes_version: "0.1.0"\n'
    lines = text.splitlines(keepends=True)
    insert_at = len(lines)

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and ":" in stripped:
            insert_at = i
            break

    lines.insert(insert_at, meta_block)
    config_path.write_text("".join(lines), encoding="utf-8")


MIGRATION = Migration(
    from_version="0.0.0",
    to_version="0.1.0",
    description="Add meta.maes_version to config.yaml",
    run=_run,
)
