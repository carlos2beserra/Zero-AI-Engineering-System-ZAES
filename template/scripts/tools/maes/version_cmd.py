"""maes version — show CLI version and project version."""
from __future__ import annotations

from pathlib import Path

from . import __version__
from .versioning import read_project_version, version_tuple


def _find_config(project_dir: str | None) -> Path | None:
    """Locate .maes/config.yaml walking up from cwd (or project_dir)."""
    if project_dir:
        candidate = Path(project_dir) / ".maes" / "config.yaml"
        return candidate if candidate.exists() else None

    current = Path.cwd()
    for _ in range(10):
        candidate = current / ".maes" / "config.yaml"
        if candidate.exists():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    return None


def run_version(project_dir: str | None = None) -> int:
    _B = "\033[1m"
    _X = "\033[0m"
    _Y = "\033[33m"
    _G = "\033[32m"
    _R = "\033[31m"

    print(f"{_B}MAES CLI{_X}   {__version__}")

    config_path = _find_config(project_dir)
    if config_path is None:
        print(f"\nProject    {_Y}no .maes/ found in current directory tree{_X}")
        print("           Run `maes init` to initialize a project.")
    else:
        project_name = config_path.parent.parent.name
        # lenient: `maes version` is read-only status and must never crash on a
        # malformed config; read_project_version degrades to "0.0.0" there.
        stored = read_project_version(config_path.parent, strict=False)

        print(f"\nProject    {_B}{project_name}{_X}  ({config_path.parent})")

        if version_tuple(stored) == (0, 0, 0):
            print(f"  stored   {_Y}— (pre-versioning){_X}")
            print(f"  status   {_R}UPGRADE AVAILABLE{_X} — run 'maes upgrade' to apply")
        else:
            cli_t = version_tuple(__version__.split("+")[0])
            stored_t = version_tuple(stored)

            print(f"  stored   {stored}")

            if cli_t > stored_t:
                print(f"  status   {_Y}UPGRADE AVAILABLE{_X} ({stored} → {__version__}) — run 'maes upgrade'")
            elif cli_t == stored_t:
                print(f"  status   {_G}up to date{_X}")
            else:
                print(f"  status   {_Y}CLI is older than project{_X} (project {stored}, CLI {__version__})")
                print("           Consider updating the MAES CLI.")

    return 0
