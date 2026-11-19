"""MAES maintainer dev-tools — `python -m maint <command> ...`.

Internal tooling for MAES *maintainers* only. It is NOT part of the public `maes`
CLI and is NOT distributed in the wheel (it lives outside the `maes` package).
See docs/development/dev-tools.md for the principles behind these tools.

Commands are registered explicitly (no plugin/discovery magic): add a module in
maint/commands/ exposing `register(subparsers)` and one import + call below.
Run from template/scripts/tools (where `import maes` resolves), like tests/CI.
"""

from __future__ import annotations

import argparse
import sys

from maint.commands import migration


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m maint",
        description="MAES maintainer dev-tools (internal; not the public `maes` CLI).",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)
    migration.register(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
