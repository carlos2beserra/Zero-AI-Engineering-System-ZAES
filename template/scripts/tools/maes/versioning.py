"""Canonical version parsing + project-version reading for MAES.

Single source of truth (avoids the duplicated helpers that used to live in both
``upgrade_cmd`` and ``version_cmd``):

- :func:`version_tuple` — parse a project version string into a comparable tuple.
- :func:`read_project_version` — read ``meta.maes_version`` from ``.maes/config.yaml``.

Version contract (reduced SemVer)
---------------------------------
``meta.maes_version`` uses a **reduced SemVer**: only the ``X.Y.Z`` form (exactly
three integers) is part of the MAES contract. Forms such as ``1``, ``1.0``,
``1.0-beta`` or ``1.0.0+build`` are **not** supported and are outside the contract.
:func:`version_tuple` maps any out-of-contract input to the sentinel ``(0, 0, 0)``
so it sorts as "oldest" (a project stamped with a malformed version is treated as
needing a full upgrade rather than crashing).

Corrupted config vs new project
--------------------------------
An **absent** ``config.yaml`` means a brand-new project → ``"0.0.0"``. An
**existing but unreadable/invalid** ``config.yaml`` is corruption, never a new
project: in ``strict`` mode :func:`read_project_version` raises
:class:`ProjectConfigError` so ``maes upgrade`` aborts before touching anything; in
lenient mode it degrades to ``"0.0.0"`` so read-only status (``maes version``)
never crashes.
"""

from __future__ import annotations

from pathlib import Path

_CONFIG_YAML = "config.yaml"


class ProjectConfigError(Exception):
    """An existing ``.maes/config.yaml`` exists but cannot be read/parsed.

    Distinguishes a corrupted/unreadable config (must abort the upgrade) from a
    genuinely new project (no config → ``0.0.0``).
    """


def version_tuple(v: str) -> tuple[int, int, int]:
    """Parse a reduced-SemVer ``"X.Y.Z"`` into a 3-tuple of ints for comparison.

    Only the ``X.Y.Z`` form (three integers) is part of the MAES contract. Any
    input outside that form (``""``, ``"1"``, ``"1.0"``, ``"1.0-beta"``,
    ``"1.0.0+build"``, ...) is outside the contract and maps to ``(0, 0, 0)``.
    """
    parts = (v or "").split(".")
    if len(parts) != 3:
        return (0, 0, 0)
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return (0, 0, 0)


def read_project_version(maes_dir: Path, *, strict: bool) -> str:
    """Return the project's stored ``maes_version``, or ``"0.0.0"``.

    - ``config.yaml`` absent → ``"0.0.0"`` (new project; both modes).
    - present, valid, with ``meta.maes_version`` → that value.
    - present, valid, without ``meta.maes_version`` → ``"0.0.0"`` (pre-versioning
      project; a legitimate state handled by the 0.0.0→0.1.0 migration).
    - present but unreadable / invalid YAML / top-level not a mapping →
      ``strict=True`` raises :class:`ProjectConfigError`; ``strict=False`` returns
      ``"0.0.0"``.
    """
    import yaml  # hard dependency (declared in pyproject); absence is an env error

    config_path = maes_dir / _CONFIG_YAML
    if not config_path.exists():
        return "0.0.0"

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        if strict:
            raise ProjectConfigError(
                f"{config_path} exists but could not be read/parsed: {exc}. "
                f"Fix or restore it (e.g. `git checkout -- {config_path}`) and re-run."
            ) from exc
        return "0.0.0"

    # Empty file (safe_load → None) is a minimal/pre-versioning config, not corruption.
    if data is None:
        return "0.0.0"
    if not isinstance(data, dict):
        if strict:
            raise ProjectConfigError(
                f"{config_path} is not a valid MAES config: top-level is "
                f"{type(data).__name__}, expected a mapping."
            )
        return "0.0.0"

    meta = data.get("meta")
    if not isinstance(meta, dict):
        return "0.0.0"
    return meta.get("maes_version") or "0.0.0"
