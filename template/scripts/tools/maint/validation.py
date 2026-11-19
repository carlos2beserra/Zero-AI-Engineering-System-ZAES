"""Version validation for MAES maintainer tooling.

Reuses the framework's version contract instead of duplicating it: a version is
valid only in the reduced-SemVer ``X.Y.Z`` form (see maes.versioning). Raises
``ValidationError`` with an actionable message on any violation.
"""

from __future__ import annotations

from maes.versioning import version_tuple


class ValidationError(Exception):
    """A maintainer supplied an invalid/inconsistent argument."""


def require_version(value: str, *, flag: str) -> tuple[int, int, int]:
    """Return the parsed tuple, or raise if `value` is not reduced-SemVer X.Y.Z.

    version_tuple() maps anything outside the contract to (0, 0, 0); we reject the
    malformed case explicitly here so the tool never silently accepts e.g. "1.2".
    """
    parts = value.split(".")
    is_three_ints = len(parts) == 3 and all(p.isdigit() for p in parts)
    if not is_three_ints:
        raise ValidationError(
            f"{flag}: '{value}' is not a valid version. Use reduced SemVer X.Y.Z "
            f"(three integers), e.g. 1.2.0."
        )
    return version_tuple(value)


def require_clean_description(description: str) -> str:
    """Return a trimmed description, or raise if it would break the generated module.

    The description is inserted into the generated migration's docstring and into its
    ``Migration(description=...)`` literal. A triple-quote sequence would terminate the
    docstring early (producing an invalid — potentially code-injectable — module that
    auto-discovery then imports), so it is rejected outright.
    """
    cleaned = description.strip()
    if not cleaned:
        raise ValidationError("--description must not be empty.")
    if '"""' in cleaned:
        raise ValidationError('--description must not contain a triple-quote (""").')
    return cleaned


def require_forward(from_version: str, to_version: str) -> None:
    """Ensure to_version is strictly greater than from_version."""
    if version_tuple(to_version) <= version_tuple(from_version):
        raise ValidationError(
            f"--to ({to_version}) must be strictly greater than --from ({from_version})."
        )


def require_not_registered(from_version: str, to_version: str) -> None:
    """Reject a migration that duplicates an already-registered step.

    Checks against the live, auto-discovered registry (maes.migrations.MIGRATIONS):
    reject an exact (from, to) duplicate and reject a duplicate from_version (which
    would make find_path's selection ambiguous).
    """
    from maes.migrations import MIGRATIONS

    for m in MIGRATIONS:
        if (m.from_version, m.to_version) == (from_version, to_version):
            raise ValidationError(
                f"A migration {from_version} -> {to_version} is already registered."
            )
        if m.from_version == from_version:
            raise ValidationError(
                f"A migration already starts at from_version {from_version} "
                f"({m.from_version} -> {m.to_version}); pick a distinct from_version."
            )
