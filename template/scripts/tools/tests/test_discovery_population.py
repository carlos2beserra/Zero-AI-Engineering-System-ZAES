"""Stage 1 behaviour over the inventory contract — population vs content sample.

Regression tests for the six root causes recorded in
docs/development/findings-discovery-sampling-e-placement-confidence.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maes.pipeline.stage_1_discovery import (
    _MAX_TOTAL_CHARS,
    _PRIORITY_BUDGET_RATIO,
    _Collector,
    _collect_priority,
    _matches_glob,
    find_project_roots,
    run_discovery,
    scan_project,
)


def _write(root: Path, rel: str, content: str = "x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


# ─── #5 — .tsx/.jsx/.vue must reach the source BFS ───────────────────────────


def test_frontend_extensions_reach_the_content_sample(tmp_path: Path):
    """Regression: _SOURCE_EXTENSIONS lacked .tsx/.jsx/.vue, so a React/Next project
    had NO eligible file outside _PRIORITY_FILES — 'zero frontend nodes' was a filter,
    not an exhausted budget."""
    _write(tmp_path, "src/pages/Rankings.tsx", "export default () => null\n")
    _write(tmp_path, "src/components/Card.jsx", "export default () => null\n")
    _write(tmp_path, "src/widgets/Panel.vue", "<template/>\n")

    result = run_discovery(tmp_path)
    collected = {rel for rel, _ in result.files}

    assert "src/pages/Rankings.tsx" in collected
    assert "src/components/Card.jsx" in collected
    assert "src/widgets/Panel.vue" in collected
    assert "src/pages/Rankings.tsx" in result.source_paths


# ─── #6 — priority files in nested project roots ─────────────────────────────


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Multi-manifest workspace: the real shape of the project that exposed the bug."""
    _write(tmp_path, "apps/web/package.json", json.dumps(
        {"dependencies": {"next": "14.0.0", "react": "18.0.0"}}))
    _write(tmp_path, "apps/web/next.config.js", "module.exports = {}\n")
    _write(tmp_path, "apps/web/src/Page.tsx", "export default () => null\n")
    _write(tmp_path, "apps/admin/package.json", json.dumps(
        {"dependencies": {"react": "18.0.0"}}))
    _write(tmp_path, "packages/ui/package.json", json.dumps(
        {"dependencies": {"react": "18.0.0"}}))
    _write(tmp_path, "services/api/pyproject.toml", "[project]\nname='api'\n")
    _write(tmp_path, "services/api/app/main.py", "app = None\n")
    # Must be ignored despite carrying a manifest
    _write(tmp_path, "node_modules/some-lib/package.json", "{}")
    return tmp_path


def test_finds_nested_project_roots(workspace: Path):
    roots, discovered = find_project_roots(workspace)
    rels = {
        "." if r == workspace else str(r.relative_to(workspace)).replace("\\", "/")
        for r in roots
    }
    assert rels == {".", "apps/web", "apps/admin", "packages/ui", "services/api"}
    assert discovered == 5


def test_ignored_dirs_never_become_project_roots(workspace: Path):
    roots, _ = find_project_roots(workspace)
    assert not [r for r in roots if "node_modules" in r.parts]


def test_nested_manifests_are_collected(workspace: Path):
    result = run_discovery(workspace)
    collected = {rel for rel, _ in result.files}
    assert "apps/web/package.json" in collected
    assert "services/api/pyproject.toml" in collected


def test_root_key_is_unchanged_for_the_project_root(tmp_path: Path):
    """Single-repo behaviour must be byte-identical: the key stays 'package.json'."""
    _write(tmp_path, "package.json", "{}")
    result = run_discovery(tmp_path)
    assert "package.json" in {rel for rel, _ in result.files}


def test_project_roots_ordered_by_manifest_priority_then_path(tmp_path: Path):
    """package.json outranks pyproject.toml; path only breaks ties.

    Cutting purely alphabetically could fill every slot with auxiliary packages while
    the application's manifest is never collected.
    """
    _write(tmp_path, "zzz-app/package.json", "{}")
    _write(tmp_path, "aaa-lib/pyproject.toml", "[project]\nname='x'\n")
    roots, _ = find_project_roots(tmp_path)
    ordered = [str(r.relative_to(tmp_path)).replace("\\", "/") for r in roots[1:]]
    assert ordered == ["zzz-app", "aaa-lib"]


def test_project_root_cut_is_reported_not_silent(tmp_path: Path):
    """A protection limit must never look like absence of evidence (ADR 0009)."""
    for i in range(20):
        _write(tmp_path, f"pkg{i:02d}/package.json", "{}")

    result = run_discovery(tmp_path)

    assert result.project_roots_discovered == 21          # 20 nested + root
    assert result.project_roots_analyzed < result.project_roots_discovered
    assert result.project_roots_analyzed == 8


def test_workspace_enumeration_is_deterministic(workspace: Path):
    """Multiple manifests must not make the result depend on filesystem order."""
    assert scan_project(workspace) == scan_project(workspace)
    a, b = run_discovery(workspace), run_discovery(workspace)
    assert a.source_paths == b.source_paths
    assert [rel for rel, _ in a.files] == [rel for rel, _ in b.files]


# ─── #10 — one enumeration, and no collection from ignored dirs ───────────────


def test_population_is_enumerated_once(tmp_path: Path, monkeypatch):
    """Stage 1 must not enumerate the same population twice.

    This is not the claim that the pipeline touches the filesystem once —
    build_file_tree is a different projection — but that no two places independently
    enumerate the source population and can disagree about which files exist.
    """
    _write(tmp_path, "src/a.ts", "export const a = 1\n")
    _write(tmp_path, "src/b.py", "b = 1\n")

    calls: list[str] = []
    original = Path.rglob

    def counting_rglob(self, pattern):
        calls.append(pattern)
        return original(self, pattern)

    monkeypatch.setattr(Path, "rglob", counting_rglob)
    run_discovery(tmp_path)

    assert calls.count("*") == 1, f"expected a single full walk, got {calls}"


def test_auth_models_are_not_collected_from_ignored_dirs(tmp_path: Path):
    """Regression: _collect_auth_models used raw globs and never called _in_ignored,
    so a virtualenv's user model could be collected as a project domain model."""
    _write(tmp_path, ".venv/lib/python3.11/site-packages/pkg/models/user.py",
           "class User: pass\n")
    _write(tmp_path, "node_modules/lib/models/user.model.ts", "class User {}\n")
    _write(tmp_path, "app/models/user.py", "class User: pass\n")

    result = run_discovery(tmp_path)
    collected = {rel for rel, _ in result.files}

    assert "app/models/user.py" in collected
    assert not [c for c in collected if c.startswith((".venv/", "node_modules/"))]


def test_matches_glob_reproduces_recursive_semantics():
    assert _matches_glob("a/b/models/user1.py", "**/models/user*.py")
    assert _matches_glob("models/user1.py", "**/models/user*.py")
    assert not _matches_glob("a/b/schemas/user1.py", "**/models/user*.py")
    assert _matches_glob("app/models/user.rb", "app/models/user.rb")


# ─── #8 — the 60/40 split is an invariant, not a comment ─────────────────────


def test_priority_phase_cannot_starve_the_source_bfs(tmp_path: Path):
    """Many large entity files used to consume the whole budget: auth/domain model
    collection was explicitly exempt from the priority cap and bounded only by the
    200k total (40 files x 12k = up to 480k)."""
    big = "z" * 12_000
    for i in range(40):
        _write(tmp_path, f"src/domain/thing{i:02d}.entity.ts", big)
    _write(tmp_path, "src/http/controller.ts", "export const c = 1\n")

    # The invariant is about what the PRIORITY PHASE consumes. Measure it directly:
    # the final file list legitimately contains more entity files, because the source
    # BFS goes on to collect them with the remaining 40% — they are, after all, the
    # only source files in this project.
    col = _Collector()
    inventory = scan_project(tmp_path)
    _collect_priority(col, tmp_path, inventory=inventory)

    priority_cap = int(_MAX_TOTAL_CHARS * _PRIORITY_BUDGET_RATIO)
    # Budget is checked BEFORE each add, so the file crossing the line is still
    # collected in full: the ceiling holds to within one file, not exactly.
    assert col.total_chars <= priority_cap + 30_000
    assert _MAX_TOTAL_CHARS - col.total_chars > 0.3 * _MAX_TOTAL_CHARS, (
        "priority phase left less than 30% of the budget for the source BFS"
    )

    result = run_discovery(tmp_path)
    collected = {rel for rel, _ in result.files}
    assert "src/http/controller.ts" in collected, (
        "the source BFS was starved by the priority phase"
    )


def test_collector_soft_limit_bounds_a_phase():
    col = _Collector()
    limit = int(_MAX_TOTAL_CHARS * _PRIORITY_BUDGET_RATIO)
    col.set_soft_limit(limit)
    assert col.add("a.ts", "y" * limit) is True
    assert col.at_limit() is True
    assert col.add("b.ts", "more") is False
    col.clear_soft_limit()
    assert col.at_limit() is False
    assert col.add("b.ts", "more") is True


def test_skip_existing_docs_collects_no_markdown(tmp_path: Path):
    _write(tmp_path, "docs/adr/0001-x.md", "# adr\n" + "d" * 5_000)
    _write(tmp_path, "src/a.ts", "export const a = 1\n")

    result = run_discovery(tmp_path, skip_existing_docs=True)
    collected = {rel for rel, _ in result.files}

    assert not [c for c in collected if c.startswith("docs/")]
    assert "src/a.ts" in collected


# ─── Scale: monorepo heavy on assets ─────────────────────────────────────────


def test_asset_heavy_monorepo_does_not_degrade_the_bfs(tmp_path: Path):
    """Versioned build output / icons / fixtures are common; asset volume must not
    displace code from the budget — the original problem through another door."""
    for i in range(200):
        _write(tmp_path, f"src/mod{i:03d}/index.ts", "export const a = 1\n")
    for i in range(2_000):
        _write(tmp_path, f"assets/icons/i{i:04d}.svg", "<svg/>")
        _write(tmp_path, f"fixtures/f{i:04d}.json", "{}")

    inv = scan_project(tmp_path)
    result = run_discovery(tmp_path)
    collected = {rel for rel, _ in result.files}

    assert len(inv.source_paths) == 200
    assert len(inv.all_paths) == 4_200
    # Assets are enumerated but never read, and never reach the topology input.
    assert not [c for c in collected if c.startswith(("assets/", "fixtures/"))]
    assert len([c for c in collected if c.startswith("src/")]) == 200
