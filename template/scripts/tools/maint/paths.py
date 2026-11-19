"""Path/name derivation for MAES maintainer tooling.

Resolves the migrations package directory from the installed ``maes`` package
(so it works regardless of the current working directory) and derives migration
filenames from the ``m_<from>_to_<to>.py`` convention.
"""

from __future__ import annotations

from pathlib import Path


def migrations_dir() -> Path:
    """Absolute path to the maes.migrations package directory."""
    import maes.migrations

    return Path(maes.migrations.__path__[0])


def migration_filename(from_version: str, to_version: str) -> str:
    """Derive the migration module filename: 1.1.0, 1.2.0 -> m_1_1_0_to_1_2_0.py."""
    return f"m_{from_version.replace('.', '_')}_to_{to_version.replace('.', '_')}.py"


def migration_path(from_version: str, to_version: str) -> Path:
    """Absolute path where the migration module would live."""
    return migrations_dir() / migration_filename(from_version, to_version)
