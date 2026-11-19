#!/usr/bin/env python3
"""Shared helpers for adapter copy and CI vendoring.

Historical name kept to avoid churn across importers; the `maes quickstart`
CLI command itself was removed in v1.0.0. The per-agent classification/scope
logic was removed when the specialist agents were consolidated into
`maes-review` (a single global-scope review workflow needs no per-agent scoping).
"""

from __future__ import annotations

import shutil
from pathlib import Path


def _is_single_path_unit(path: str) -> bool:
    """Return True if path represents exactly one logical path unit.

    A valid single path has no whitespace in any segment. A path like
    'app/services/job/ and app/services/jobs/' has whitespace inside a segment,
    which violates the modules.json schema invariant (one module = one path unit).
    Shared with doctor_cmd as the single source of truth for this invariant.
    """
    segments = [s for s in path.replace("\\", "/").split("/") if s]
    return bool(segments) and all(" " not in segment for segment in segments)


def _copy_adapters_to_root(maes_dir: Path, project_dir: Path) -> list[str]:
    """Copy adapter output from .maes/adapters/ to project root. Returns copied paths."""
    adapters_dir = maes_dir / "adapters"
    copied: list[str] = []

    copy_map = [
        ("claude/CLAUDE.md", "CLAUDE.md", "file"),
        ("claude/.claude/commands", ".claude/commands", "sync_dir"),
        ("cursor/.cursor/rules", ".cursor/rules", "sync_dir"),
        ("continue/.continue/rules", ".continue/rules", "sync_dir"),
        ("windsurf/.windsurfrules", ".windsurfrules", "file"),
        ("copilot/.github/copilot-instructions.md", ".github/copilot-instructions.md", "file"),
        ("copilot/.github/instructions", ".github/instructions", "sync_dir"),
        ("copilot/.github/skills", ".github/skills", "sync_dir"),
    ]

    for src_rel, dst_rel, mode in copy_map:
        src = adapters_dir / src_rel
        dst = project_dir / dst_rel
        if not src.exists():
            continue
        try:
            if mode == "sync_dir":
                _sync_managed_directory(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            copied.append(dst_rel)
        except OSError as e:
            print(f"  ⚠ Could not copy {dst_rel}: {e}")

    copied.extend(_deploy_github_templates(project_dir))

    return copied


def _sync_managed_directory(src_dir: Path, dst_dir: Path) -> None:
    """Sync dst_dir to src_dir for generated files while preserving unrelated parent paths."""
    src_files = [p for p in src_dir.rglob("*") if p.is_file()]
    src_rel_set = {p.relative_to(src_dir) for p in src_files}

    dst_dir.mkdir(parents=True, exist_ok=True)

    # Remove stale generated files that no longer exist in source.
    for dst_file in sorted([p for p in dst_dir.rglob("*") if p.is_file()]):
        rel = dst_file.relative_to(dst_dir)
        if rel not in src_rel_set:
            dst_file.unlink(missing_ok=True)

    # Copy current generated files.
    for src_file in src_files:
        rel = src_file.relative_to(src_dir)
        dst_file = dst_dir / rel
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)

    # Remove empty directories left behind after stale file cleanup.
    for maybe_empty in sorted(
        [p for p in dst_dir.rglob("*") if p.is_dir()],
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        if not any(maybe_empty.iterdir()):
            maybe_empty.rmdir()


def _deploy_gha_workflows(project_dir: Path, templates_dir: Path) -> list[str]:
    deployed: list[str] = []
    gha_src = templates_dir / "github-actions"
    if not gha_src.exists():
        return deployed
    gha_dst = project_dir / ".github" / "workflows"
    gha_dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(gha_src.glob("*.yml")):
        dst = gha_dst / f.name
        if not dst.exists():
            try:
                shutil.copy2(f, dst)
                deployed.append(f".github/workflows/{f.name}")
            except OSError as e:
                print(f"  ⚠ Could not copy {f.name}: {e}")
    return deployed


def _deploy_requirements_txt(f: Path, project_dir: Path, deployed: list[str]) -> None:
    req_dst = project_dir / "scripts" / "requirements.txt"
    if not req_dst.exists():
        try:
            shutil.copy2(f, req_dst)
            deployed.append("scripts/requirements.txt")
        except OSError:
            pass


def _deploy_ci_script(f: Path, ci_dst: Path) -> bool:
    dst = ci_dst / f.name
    if not dst.exists():
        try:
            shutil.copy2(f, dst)
            return True
        except OSError:
            pass
    return False


def _deploy_ci_scripts(project_dir: Path, templates_dir: Path) -> list[str]:
    deployed: list[str] = []
    ci_src = templates_dir / "ci"
    if not ci_src.exists():
        return deployed
    ci_dst = project_dir / "scripts" / "ci"
    ci_dst.mkdir(parents=True, exist_ok=True)
    ci_files_deployed = 0
    for f in sorted(ci_src.iterdir()):
        if f.name == "requirements.txt":
            _deploy_requirements_txt(f, project_dir, deployed)
        elif f.is_file() and _deploy_ci_script(f, ci_dst):
            ci_files_deployed += 1
    if ci_files_deployed:
        deployed.append(f"scripts/ci/ ({ci_files_deployed} scripts)")
    return deployed


def _deploy_github_templates(project_dir: Path) -> list[str]:
    """Deploy GitHub Actions workflows and CI scripts from package templates."""
    templates_dir = Path(__file__).parent / "templates"
    deployed = _deploy_gha_workflows(project_dir, templates_dir)
    deployed += _deploy_ci_scripts(project_dir, templates_dir)
    return deployed


_VENDOR_MODULES = {
    "__init__.py", "__main__.py",
    "models.py", "compiler.py",
    "adapters.py", "staleness.py", "quickstart_cmd.py", "explain.py",
}


def _vendor_maes_package(maes_dir: Path) -> None:
    """Copy only the CI-required modules to .maes/vendor/maes/."""
    src = Path(__file__).parent
    vendor_dir = maes_dir / "vendor" / "maes"
    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)
    vendor_dir.mkdir(parents=True)
    for name in _VENDOR_MODULES:
        shutil.copy2(src / name, vendor_dir / name)
