"""Migration 0.12.3 → 0.13.0

Adds owner_context field to NormalizedAssertion.
Existing assertions.json entries that lack the field receive owner_context: null.
"""
from __future__ import annotations

import json
from pathlib import Path

from maes.migrations import Migration


def _run(maes_dir: Path) -> None:
    assertions_path = maes_dir / "synthesis" / "assertions.json"
    if not assertions_path.exists():
        return
    data = json.loads(assertions_path.read_text(encoding="utf-8"))
    changed = False
    for entry in data.get("assertions", []):
        if "owner_context" not in entry:
            entry["owner_context"] = None
            changed = True
    if changed:
        assertions_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


MIGRATION = Migration(
    from_version="0.12.3",
    to_version="0.13.0",
    description="Add owner_context field to NormalizedAssertion entries in assertions.json",
    run=_run,
)
