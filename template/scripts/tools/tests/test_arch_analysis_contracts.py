"""Contracts of arch_analysis: single canonical builder + framework detection order."""

from __future__ import annotations

import json

from maes.arch_analysis import (
    _detect_frontend_framework,
    build_candidates,
    build_candidates_from_paths,
)
from maes.models import CANONICAL_SOURCE_EXTENSIONS, IMPORT_PARSEABLE_EXTENSIONS


# ─── One canonical implementation ─────────────────────────────────────────────


def test_adapter_is_equivalent_to_the_canonical_builder():
    """build_candidates is an ADAPTER: it must never grow logic of its own.

    This equivalence is what keeps a future fix from being applied to only one of the
    two entry points — the exact failure mode that made _SOURCE_EXTENSIONS diverge
    from _SOURCE_EXTS.
    """
    files = [
        ("src/services/auth.ts", "export const a = 1"),
        ("src/services/user.ts", "export const b = 2"),
        ("src/ui/View.tsx", "export default () => null"),
        ("README.md", "# ignored"),
        ("node_modules/lib/index.ts", "ignored"),
    ]
    via_adapter = build_candidates(files)
    via_canonical = build_candidates_from_paths([p for p, _ in files])
    assert via_adapter == via_canonical


def test_candidates_do_not_depend_on_content():
    """Topology derives from paths alone — that is why it can come from the inventory
    instead of the budget-capped sample."""
    paths = ["src/a/x.ts", "src/a/y.ts", "src/b/z.py"]
    assert build_candidates_from_paths(paths) == build_candidates(
        [(p, "wildly different content") for p in paths]
    )


# ─── Extension sets ───────────────────────────────────────────────────────────


def test_import_parseable_is_a_subset_of_the_canonical_definition():
    """Capability, not definition: derived from the canonical set, named for what it
    can do (ADR 0009)."""
    assert IMPORT_PARSEABLE_EXTENSIONS < CANONICAL_SOURCE_EXTENSIONS


def test_frontend_extensions_are_part_of_the_canonical_definition():
    assert {".tsx", ".jsx", ".vue", ".svelte"} <= CANONICAL_SOURCE_EXTENSIONS


# ─── Frontend detection: basename matching and tie-break semantics ────────────


def _pkg(*deps: str) -> str:
    return json.dumps({"dependencies": {d: "1.0.0" for d in deps}})


def test_detects_manifest_in_nested_workspace_package():
    """Exact-path matching made every multirepo workspace report false regardless of
    contents — the manifest lives at apps/web/package.json, not at the root."""
    assert _detect_frontend_framework([("apps/web/package.json", _pkg("react"))]) == "react"


def test_no_manifest_means_no_framework():
    assert _detect_frontend_framework([("src/a.ts", "x")]) is None


def test_config_file_wins_over_package_json():
    """Pinned semantics: a config file outranks dependency scanning, and the outcome
    must not depend on which file happens to come first in the collection order."""
    files = [
        ("apps/admin/package.json", _pkg("react")),
        ("apps/web/next.config.js", "module.exports = {}"),
    ]
    assert _detect_frontend_framework(files) == "nextjs"
    assert _detect_frontend_framework(list(reversed(files))) == "nextjs"


def test_conflicting_config_and_deps_resolves_to_config_not_any_truthy_value():
    """apps/web declares next.config.js but no `next` dependency: the answer is
    nextjs (config wins, by design) — asserted explicitly rather than accepting
    anything non-null."""
    files = [
        ("apps/web/package.json", _pkg("react")),
        ("apps/web/next.config.js", "module.exports = {}"),
    ]
    assert _detect_frontend_framework(files) == "nextjs"


def test_competing_manifests_resolve_deterministically():
    """Among competing manifests the collection order decides, and the inventory is
    sorted — so the same tree always yields the same answer."""
    files = [
        ("apps/admin/package.json", _pkg("react")),
        ("apps/web/package.json", _pkg("vue")),
    ]
    assert _detect_frontend_framework(files) == "react"
    assert _detect_frontend_framework(files) == "react"
