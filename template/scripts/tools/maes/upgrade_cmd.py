"""maes upgrade — migrate project .maes/ to the current CLI version."""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .versioning import ProjectConfigError, read_project_version, version_tuple


_B = "\033[1m"
_X = "\033[0m"
_G = "\033[32m"
_R = "\033[31m"
_Y = "\033[33m"

_MAES_DIR_NAME = ".maes"
_CONFIG_YAML = "config.yaml"
_MSG_RUNNING_SYNC = "\nRunning maes sync ..."


def _locate_maes_dir(project_dir: Path | None) -> Path:
    if project_dir:
        candidate = project_dir / _MAES_DIR_NAME
        if not candidate.exists():
            print(f"Error: {_MAES_DIR_NAME}/ not found at {candidate}", file=sys.stderr)
            print("Run `maes init` to initialize.", file=sys.stderr)
            sys.exit(1)
        return candidate

    current = Path.cwd()
    for _ in range(10):
        candidate = current / _MAES_DIR_NAME
        if candidate.exists():
            return candidate
        if current.parent == current:
            break
        current = current.parent

    print(f"Error: {_MAES_DIR_NAME}/ not found in current directory or any parent.", file=sys.stderr)
    print("Run `maes init` to initialize.", file=sys.stderr)
    sys.exit(1)


def _write_project_version(maes_dir: Path, new_version: str) -> None:
    config_path = maes_dir / _CONFIG_YAML
    if not config_path.exists():
        return
    try:
        import re
        text = config_path.read_text(encoding="utf-8")
        if "maes_version:" in text:
            text = re.sub(
                r'(maes_version:\s*["\']?)[\d.]+(["\']?)',
                rf'\g<1>{new_version}\g<2>',
                text,
            )
        else:
            meta_block = f'\nmeta:\n  maes_version: "{new_version}"\n'
            lines = text.splitlines(keepends=True)
            insert_at = len(lines)
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and ":" in stripped:
                    insert_at = i
                    break
            lines.insert(insert_at, meta_block)
            text = "".join(lines)
        config_path.write_text(text, encoding="utf-8")
    except Exception as exc:
        print(f"  {_Y}Warning: could not stamp version in {_CONFIG_YAML}: {exc}{_X}", file=sys.stderr)


def _backup_human(maes_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = maes_dir / "cache" / f"upgrade-backup-{timestamp}"
    human_dir = maes_dir / "context" / "human"
    if human_dir.exists():
        shutil.copytree(human_dir, backup_dir / "human")
    return backup_dir


def _run_sync_local(maes_dir: Path) -> None:
    """Run the **canonical** `maes sync` pipeline — single source of truth.

    Delegates to __main__._run_sync so the upgrade regenerates the synthesis AND
    the IDE adapters (rewrites the .maes/adapters/ staging and copies them to the
    project root via _copy_adapters_to_root). Previously this was a partial
    reimplementation that discarded generate_adapters()' output and never touched
    the root output dirs, so new/updated agents (e.g. maes-create) were never
    compiled for the supported AI tools after an upgrade.
    """
    from .__main__ import _run_sync

    _run_sync(maes_dir)


def _update_gha_workflows(maes_dir: Path) -> None:
    """Overwrite .github/workflows/maes-*.yml with current package templates."""
    import maes as _maes_pkg
    templates_dir = Path(_maes_pkg.__file__).parent / "templates" / "github-actions"
    if not templates_dir.exists():
        return
    gha_dst = maes_dir.parent / ".github" / "workflows"
    gha_dst.mkdir(parents=True, exist_ok=True)
    updated: list[str] = []
    for src in sorted(templates_dir.glob("*.yml")):
        dst = gha_dst / src.name
        shutil.copy2(src, dst)
        updated.append(src.name)
    if updated:
        print(f"  {_G}✓{_X} GitHub Actions workflows updated: {', '.join(updated)}")


def _remove_vendor_from_gitignore(maes_dir: Path) -> None:
    """Remove .maes/vendor/ from project .gitignore if present (vendor is now tracked)."""
    gitignore = maes_dir.parent / ".gitignore"
    if not gitignore.exists():
        return
    text = gitignore.read_text(encoding="utf-8")
    if ".maes/vendor/" not in text:
        return
    lines = [l for l in text.splitlines(keepends=True) if ".maes/vendor/" not in l]
    gitignore.write_text("".join(lines), encoding="utf-8")
    print(f"  {_G}✓{_X} Removed .maes/vendor/ from .gitignore (vendor is now tracked in git)")


_ARCH_MAP_REQUIRED_SCHEMA = "2.1"


def _vendored_version(maes_dir: Path) -> str | None:
    """__version__ declared by the vendored copy, or None when absent/unreadable."""
    init = maes_dir / "vendor" / "maes" / "__init__.py"
    if not init.exists():
        return None
    try:
        import re as _re
        m = _re.search(
            r'__version__\s*=\s*["\']([^"\']+)["\']',
            init.read_text(encoding="utf-8"),
        )
        return m.group(1) if m else None
    except OSError:
        return None


def _check_version_agreement(maes_dir: Path, cli_version: str) -> None:
    """Guard against the hardest failure mode: an upgrade that ends GREEN while the
    code that actually runs is still the old one.

    Three plausible causes — vendoring from a different installation, an older `maes`
    earlier in PATH, or module resolution landing in .maes/vendor/maes/ instead of the
    installed package. In all of them every command exits 0 and the artifacts stay on
    the previous schema, with no message at all.

    This catches the cause at the moment it is created, and costs one file read. It
    cannot live inside build-arch-map: if the code that ran is the old one, the old
    self-check does not exist either — old code does not know it is old.
    """
    vendored = _vendored_version(maes_dir)
    if vendored is None or vendored == cli_version:
        return
    import maes as _maes_pkg
    print(
        f"  {_Y}Warning: versão vendorizada ({vendored}) difere do CLI instalado "
        f"({cli_version}).{_X}",
        file=sys.stderr,
    )
    print(
        f"    Módulo resolvido: {_maes_pkg.__file__}\n"
        "    O Analyze executado pode não corresponder à versão instalada.",
        file=sys.stderr,
    )


def _arch_map_needs_rebuild(maes_dir: Path) -> bool:
    """True when the on-disk architecture map predates the current schema."""
    import json as _json
    p = maes_dir / "context" / "inferred" / "architecture_map.json"
    if not p.exists():
        return False
    try:
        data = _json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    return str(data.get("schema_version") or "") != _ARCH_MAP_REQUIRED_SCHEMA


def _print_next_steps(maes_dir: Path) -> None:
    """Explain the omitted Code Placement instead of letting it vanish silently.

    The `sync` run inside `maes upgrade` produces a CLAUDE.md WITHOUT the section
    (fail-closed over a previous-schema map). That is the safe state, but an upgrade
    that says "Done" while a section disappears reads as a defect.
    """
    if not _arch_map_needs_rebuild(maes_dir):
        return
    print()
    print(
        "O Code Placement foi temporariamente omitido porque o architecture map "
        "precisa ser regenerado."
    )
    print("\nPróximo passo:")
    print("  maes build-arch-map")
    print("  maes sync")


def _finalize_upgrade(maes_dir: Path, cli_version: str | None = None) -> None:
    from .quickstart_cmd import _vendor_maes_package
    from .init_cmd import _patch_gitignore
    _update_gha_workflows(maes_dir)
    _remove_vendor_from_gitignore(maes_dir)
    _patch_gitignore(maes_dir.parent)
    _vendor_maes_package(maes_dir)
    print(f"  {_G}✓{_X} Vendor atualizado (.maes/vendor/maes/)")
    if cli_version:
        _check_version_agreement(maes_dir, cli_version)


def _apply_migrations(maes_dir: Path, migrations: list) -> int:
    backup_dir = _backup_human(maes_dir)
    rel = backup_dir.relative_to(maes_dir.parent) if backup_dir.is_relative_to(maes_dir.parent) else backup_dir
    print(f"\nBacking up .maes/context/human/ → {rel} ... {_G}✓{_X}")

    for i, m in enumerate(migrations, 1):
        print(f"Running migration {i}/{len(migrations)} ({m.from_version} → {m.to_version}) ... ", end="", flush=True)
        try:
            m.run(maes_dir)
            print(_G + "✓" + _X)
        except Exception as exc:
            print(_R + "✗" + _X)
            print(f"  Error: {exc}", file=sys.stderr)
            print(
                f"  A copy of .maes/context/human/ is at {backup_dir} "
                "(this backup covers context/human/ ONLY).",
                file=sys.stderr,
            )
            print(
                "  config.yaml / agents/ / synthesis/ are tracked by git — "
                "restore them with `git checkout -- .maes` if needed.",
                file=sys.stderr,
            )
            print(
                "  The project version was NOT changed; fix the cause and re-run "
                "`maes upgrade` (migrations are idempotent).",
                file=sys.stderr,
            )
            return 1
    return 0


def _upgrade_no_migrations(maes_dir: Path, dry_run: bool, skip_sync: bool, cli_version: str) -> int:
    print(f"\n{_Y}No migrations found — stamping version only.{_X}")
    if not dry_run:
        _write_project_version(maes_dir, cli_version)
        from .init_cmd import _copy_templates
        _copy_templates(maes_dir, merge_existing_agents=True)
        if not skip_sync:
            print(_MSG_RUNNING_SYNC)
            _run_sync_local(maes_dir)
        _finalize_upgrade(maes_dir, cli_version)
    print(f"\n{_G}{_B}Done.{_X} Project upgraded to {cli_version}")
    if not dry_run:
        _print_next_steps(maes_dir)
    return 0


def run_upgrade(
    project_dir: Path | None = None,
    dry_run: bool = False,
    skip_sync: bool = False,
) -> int:
    from .migrations import find_path

    maes_dir = _locate_maes_dir(project_dir)

    cli_version = __version__.split("+")[0]
    # strict: an existing-but-corrupted config.yaml must abort — never be silently
    # treated as a new (0.0.0) project, which would re-run every migration.
    try:
        project_version = read_project_version(maes_dir, strict=True)
    except ProjectConfigError as exc:
        print(f"{_R}✗ Cannot read project version.{_X}", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        print("  No migrations were run.", file=sys.stderr)
        return 1

    display_stored = project_version if project_version != "0.0.0" else "— (pre-versioning)"
    print(f"Detected project version: {_B}{display_stored}{_X}")
    print(f"Target version:           {_B}{cli_version}{_X}")

    if version_tuple(project_version) >= version_tuple(cli_version):
        print(f"\n{_G}✔ Project is already at {cli_version}.{_X}")
        if not dry_run:
            from .init_cmd import _copy_templates
            _copy_templates(maes_dir, merge_existing_agents=True)
            if not skip_sync:
                print(_MSG_RUNNING_SYNC)
                _run_sync_local(maes_dir)
            _finalize_upgrade(maes_dir, cli_version)
            _print_next_steps(maes_dir)
        return 0

    migrations = find_path(project_version, cli_version)

    if not migrations:
        return _upgrade_no_migrations(maes_dir, dry_run, skip_sync, cli_version)

    print("\nMigrations to run:")
    for i, m in enumerate(migrations, 1):
        print(f"  [{i}/{len(migrations)}] {m.from_version} → {m.to_version}  {m.description}")

    if dry_run:
        print(f"\n{_Y}Dry run — no changes applied.{_X}")
        return 0

    rc = _apply_migrations(maes_dir, migrations)
    if rc != 0:
        return rc

    _write_project_version(maes_dir, cli_version)
    print(f"Stamping {_CONFIG_YAML} with maes_version={cli_version} ... {_G}✓{_X}")
    from .init_cmd import _copy_templates
    _copy_templates(maes_dir, merge_existing_agents=True)

    if not skip_sync:
        print(_MSG_RUNNING_SYNC)
        try:
            _run_sync_local(maes_dir)
        except Exception as exc:
            print(f"{_R}✗ maes sync failed: {exc}{_X}", file=sys.stderr)
            return 1

    _finalize_upgrade(maes_dir, cli_version)

    print(f"\n{_G}{_B}Done.{_X} Project upgraded to {cli_version}")
    _print_next_steps(maes_dir)
    return 0
