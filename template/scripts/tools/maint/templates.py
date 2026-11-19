"""Render maintainer boilerplate from dedicated template files (stdlib only).

Uses string.Template so the boilerplate lives in one place (maint/templates/*),
never as inline string concatenation — keeping generated files in sync with the
migration contract.
"""

from __future__ import annotations

from pathlib import Path
from string import Template

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def render_migration(from_version: str, to_version: str, description: str) -> str:
    """Render migration.py.template with the given fields."""
    template_text = (_TEMPLATES_DIR / "migration.py.template").read_text(encoding="utf-8")
    return Template(template_text).substitute(
        from_version=from_version,
        to_version=to_version,
        description=description,
    )
