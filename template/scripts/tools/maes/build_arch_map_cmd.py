#!/usr/bin/env python3
"""maes build-arch-map — deterministic architecture map generator.

Runs Stage 1 (discovery) → Stage 3 (dep analysis) → Stage 2 (arch builder)
on a stable filesystem snapshot and emits:
  - context/inferred/architecture_map.json  (schema v2.0, always written)
  - context/inferred/build_metadata.json    (timestamp record, always written)

Contract (Engine Contract Strict V2):
  - Input: full project filesystem snapshot (no partial views)
  - Output: architecture_map.json + build_metadata.json in context/inferred/
  - Failure: any stage error → exit 1, no partial output written
  - dep_edges source: Stage 3 only — no LLM, no heuristics
  - stable_key: pure function _path_to_id(path), deterministic across environments
  - TypeScript dep_edges: relative imports only (permanent parser limitation)
  - This system guarantees structural determinism, not full language resolution completeness
  - Zero LLM calls
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_build_arch_map(project_dir: Path, maes_dir: Path) -> int:
    """Build architecture_map.json deterministically from a stable filesystem snapshot.

    Pipeline order: Stage 1 -> Stage 3 -> Stage 2 (exact; do not reorder).

    Returns 0 on success, 1 on failure. Never produces partial output on failure.
    """
    from .pipeline.stage_1_discovery import run_discovery
    from .pipeline.stage_3_dep import run_dep_stage
    from .pipeline.stage_2_arch_builder import run_arch_builder
    from .pipeline.stage_7_emission import _emit_architecture_map

    inferred_dir = maes_dir / "context" / "inferred"

    print("Building architecture map...")

    # Stage 1 — Project Discovery
    print("  Stage 1 — Discovering project structure...")
    try:
        # Docs contribute nothing to topology (build_candidates filters to source
        # extensions and drops .md), so they must not compete for the content budget
        # of a zero-LLM structural map.
        discovery = run_discovery(project_dir, skip_existing_docs=True)
    except Exception as exc:
        print(f"\u2717 Stage 1 (discovery) failed: {exc}", file=sys.stderr)
        return 1

    if not discovery.files:
        print(
            "\u2717 No source files found. Snapshot appears empty or inaccessible.",
            file=sys.stderr,
        )
        return 1

    print(
        f"    {len(discovery.files)} files collected "
        f"({discovery.total_chars:,} chars, {discovery.budget_used_pct:.0f}% budget)"
    )

    # Stage 3 — Dependency Analysis
    print("  Stage 3 — Analyzing dependencies...")
    try:
        dep = run_dep_stage(project_dir)
    except Exception as exc:
        print(f"\u2717 Stage 3 (dep analysis) failed: {exc}", file=sys.stderr)
        return 1

    # Stage 2 — Architecture Builder (zero-LLM)
    print("  Stage 2 — Building architecture map...")
    try:
        arch_map = run_arch_builder(project_dir, discovery, dep)
    except Exception as exc:
        print(f"\u2717 Stage 2 (arch builder) failed: {exc}", file=sys.stderr)
        return 1

    # Emit to disk — only after all stages succeed (no partial output on failure)
    inferred_dir.mkdir(parents=True, exist_ok=True)

    # Write build_metadata.json (timestamp record; architecture_map.json is timestamp-free)
    build_metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": "2.0",
        "tool": "maes",
        "artifact": "architecture_map",
    }
    (inferred_dir / "build_metadata.json").write_text(
        json.dumps(build_metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    try:
        _emit_architecture_map(inferred_dir, arch_map)
    except Exception as exc:
        print(f"\u2717 Emission failed: {exc}", file=sys.stderr)
        return 1

    print("\n\u2713 Architecture map generated")
    print(f"  Nodes:    {len(arch_map.nodes)}")
    print(f"  Coverage: {arch_map.modeled_coverage_pct * 100:.1f}%")
    print(f"  Output:   {inferred_dir / 'architecture_map.json'}")
    print()
    print("  Note: TypeScript dep_edges include relative imports only (permanent parser limitation).")
    print("  Run `maes sync` to compile the map into synthesis/.")

    return 0
