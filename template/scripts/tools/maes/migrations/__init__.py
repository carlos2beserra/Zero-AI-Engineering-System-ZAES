"""MAES migration registry.

Each Migration describes a single step in the upgrade chain.
Migrations are ordered by (from_version tuple, to_version tuple).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class Migration:
    from_version: str
    to_version: str
    description: str
    run: Callable[[Path], None]


def _ver(v: str) -> tuple[int, ...]:
    """Convert "1.2.3" to (1, 2, 3) for comparison."""
    return tuple(int(x) for x in v.split("."))


def _load_migrations() -> list[Migration]:
    """Auto-discover every ``m_*.py`` migration module in this package.

    Discovery uses :func:`pkgutil.iter_modules` over the package ``__path__`` (not a
    filesystem glob), so it works regardless of the physical layout — installed
    wheel, editable checkout, zip/egg or any importlib loader. Each ``m_*`` module
    must export a module-level ``MIGRATION``; a module that does not is a
    programming error and raises immediately (fail loud, never skip silently).

    The returned list is ordered **exclusively by ``from_version``**, so the result
    is deterministic regardless of the order in which modules are discovered.
    """
    import importlib
    import pkgutil

    migrations: list[Migration] = []
    for mod_info in pkgutil.iter_modules(__path__):
        if not mod_info.name.startswith("m_"):
            continue
        module = importlib.import_module(f"{__name__}.{mod_info.name}")
        migration = getattr(module, "MIGRATION", None)
        if not isinstance(migration, Migration):
            raise RuntimeError(
                f"Migration module '{__name__}.{mod_info.name}' must export a "
                f"module-level `MIGRATION` of type Migration (found: {migration!r})."
            )
        migrations.append(migration)

    return sorted(migrations, key=lambda m: _ver(m.from_version))


MIGRATIONS: list[Migration] = _load_migrations()


def find_path(current: str, target: str) -> list[Migration]:
    """Return ordered list of migrations to run from current to target."""
    cur = _ver(current)
    tgt = _ver(target)
    if cur >= tgt:
        return []

    path: list[Migration] = []
    for m in sorted(MIGRATIONS, key=lambda m: _ver(m.from_version)):
        if _ver(m.from_version) >= cur and _ver(m.to_version) <= tgt:
            path.append(m)
            cur = _ver(m.to_version)

    return path
