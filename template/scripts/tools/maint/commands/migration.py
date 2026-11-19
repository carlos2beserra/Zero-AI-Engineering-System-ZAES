"""`python -m maint migration create` — scaffold a new migration module.

Validates the version pair, derives the conventional filename, refuses to
overwrite, and writes the guarded boilerplate from the dedicated template. The
generated file is picked up by the existing auto-discovery in maes.migrations —
no registry edit required.
"""

from __future__ import annotations

import argparse
import sys

from maint import paths, templates, validation


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "migration",
        help="Migration authoring helpers (create)",
    )
    action = parser.add_subparsers(dest="action", metavar="ACTION", required=True)

    create = action.add_parser("create", help="Scaffold a new migration module")
    create.add_argument("--from", dest="from_version", required=True, metavar="X.Y.Z",
                        help="Version the migration upgrades from")
    create.add_argument("--to", dest="to_version", required=True, metavar="A.B.C",
                        help="Version the migration upgrades to")
    create.add_argument("--description", required=True,
                        help="One-line description of what the migration does")
    create.set_defaults(func=_create)


def _create(args: argparse.Namespace) -> int:
    try:
        validation.require_version(args.from_version, flag="--from")
        validation.require_version(args.to_version, flag="--to")
        validation.require_forward(args.from_version, args.to_version)
        validation.require_not_registered(args.from_version, args.to_version)
        description = validation.require_clean_description(args.description)
    except validation.ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    target = paths.migration_path(args.from_version, args.to_version)
    if target.exists():
        print(f"error: {target.name} already exists — refusing to overwrite.",
              file=sys.stderr)
        return 1

    content = templates.render_migration(
        args.from_version, args.to_version, description
    )
    try:
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"error: could not write {target}: {exc}", file=sys.stderr)
        return 1

    print(f"created {target}")
    print("  next: implement the guarded _run(); it is auto-discovered — no registry edit.")
    return 0
