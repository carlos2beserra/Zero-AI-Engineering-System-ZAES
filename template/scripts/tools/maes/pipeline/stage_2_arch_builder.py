#!/usr/bin/env python3
"""Stage 2: ARCHITECTURE BUILDER — deterministic architecture map from file structure.

Zero-LLM. Pure computation on DiscoveryResult + DepResult.
Runs AFTER Stage 3 (dep analysis) to reuse the layer_map.

Produces ArchitectureMapResult with:
  - nodes: ArchitectureNode dicts (all modules, not just non-obvious ones)
  - dep_edges: dependency graph between nodes (stable_key → [stable_keys])
  - modeled_coverage_pct: files_assigned / files_total (observable metric)
  - node_quality: sanity metrics for the generated map
"""

from __future__ import annotations

import sys
from pathlib import Path

from .contracts import (
    ArchitectureMapResult,
    DepResult,
    DiscoveryResult,
    StructuralTransformationMetrics,
)


def _norm(p: str) -> str:
    return p.replace("\\", "/")


def _file_under_node(fp: str, norm_path: str) -> bool:
    """True iff file `fp` belongs to the node at `norm_path`.

    Segment-boundary match only: a file belongs iff it IS the node (file node)
    or lives strictly under the node directory. A bare `startswith(norm_path)`
    would match lexical neighbours (node "src/auth" claiming "src/authx.ts")
    and an empty node path would claim every file — inflating coverage.
    """
    if not norm_path:
        return False
    return fp == norm_path or fp.startswith(norm_path + "/")


def run_arch_builder(
    _project_dir: Path,
    discovery: DiscoveryResult,
    dep: DepResult,
) -> ArchitectureMapResult:
    """Stage 2 entry point. Zero-LLM. Returns ArchitectureMapResult.

    Ordering: call AFTER run_dep_stage() so dep.boundary_map (layer_map) is available.
    """
    from ..arch_analysis import (
        _detect_frontend_framework,
        build_candidates_from_paths,
        build_content_index,
        build_dependency_edges,
        candidates_to_nodes,
        collapse_candidates,
    )

    layer_map = dict(dep.boundary_map) if dep.boundary_map else {}
    all_files = list(discovery.files)
    is_frontend_project = _detect_frontend_framework(all_files) is not None

    # POPULATION — every source file in the project, from the Stage 1 inventory.
    #
    # TRANSITION: the `or` is a schema compatibility bridge, not design. Remove once
    # every DiscoveryResult producer emits source_paths (follow-up F1). While it
    # exists a badly-built DiscoveryResult silently reverts to topology-over-sample,
    # which is the very bug this corrects — hence the explicit warning.
    inventory = list(discovery.source_paths)
    if not inventory:
        inventory = [fp for fp, _ in discovery.files]
        if inventory:
            print(
                "⚠ DiscoveryResult.source_paths ausente; usando os arquivos "
                "amostrados como população.\n"
                "  Caminho de compatibilidade temporário — deve ser removido após a "
                "migração.\n"
                "  A topologia deste mapa pode estar incompleta.",
                file=sys.stderr,
            )

    # Auxiliary structures — built ONCE, local to this stage; none crosses the
    # contract between stages.
    content_by_path = build_content_index(all_files)
    inventory_set = frozenset(_norm(p) for p in inventory)
    sampled_set = {_norm(fp) for fp, _ in all_files}

    # Phase 1: candidates from the POPULATION — topology needs paths, not content
    candidates = build_candidates_from_paths(inventory)
    candidate_count = len(candidates)

    # Phase 2: collapse to module-level granularity (sample only weighs)
    collapsed = collapse_candidates(
        candidates, layer_map, files=all_files, content_by_path=content_by_path
    )

    # Phase 3: convert candidates to ArchitectureNode dicts
    nodes = candidates_to_nodes(
        collapsed, layer_map, all_files, is_frontend_project, content_by_path
    )

    # Phase 4: build dependency graph
    dep_edges = build_dependency_edges(nodes, all_files)

    # Attach dependencies to nodes
    nodes_with_deps = []
    for node in nodes:
        deps = dep_edges.get(node.stable_key, [])
        if deps != node.dependencies:
            from dataclasses import replace
            node = replace(node, dependencies=deps)
        nodes_with_deps.append(node)

    # Coverage — measured against the POPULATION, never against the sample.
    # A coverage metric whose denominator is its own sample is structurally unable
    # to reveal under-sampling: it is tautology, not observation (ADR 0009).
    assigned: set[str] = set()
    for node in nodes_with_deps:
        norm_path = node.path.rstrip("/")
        for fp in inventory_set:
            if _file_under_node(fp, norm_path):
                assigned.add(fp)

    files_total = len(inventory_set)                        # population
    files_sampled = len(sampled_set & inventory_set)        # evidence
    files_assigned = len(assigned)
    modeled_coverage_pct = round(files_assigned / max(files_total, 1), 3)
    sampling_ratio = round(files_sampled / max(files_total, 1), 3)

    funnel = StructuralTransformationMetrics(
        source_files=files_total,
        candidates=candidate_count,
        collapsed=len(collapsed),
        nodes=len(nodes_with_deps),
    )

    # Node quality metrics
    file_counts = [n.file_count for n in nodes_with_deps]
    node_quality = {
        "total_nodes": len(nodes_with_deps),
        "avg_files_per_node": round(
            sum(file_counts) / max(len(nodes_with_deps), 1), 1
        ),
        "max_files_per_node": max(file_counts, default=0),
        "orphan_nodes_count": sum(1 for c in collapsed if c.file_count < 2),
        "collapsed_nodes_count": sum(1 for c in collapsed if c.collapsed_from),
        "files_assigned": files_assigned,
        "files_total": files_total,
        "files_sampled": files_sampled,
        "sampling_ratio": sampling_ratio,
    }

    return ArchitectureMapResult(
        nodes=tuple(n.to_dict() for n in nodes_with_deps),
        layer_map=layer_map,
        modeled_coverage_pct=modeled_coverage_pct,
        files_assigned=files_assigned,
        files_total=files_total,
        node_quality=node_quality,
        dep_edges=dep_edges,
        is_frontend_project=is_frontend_project,
        files_sampled=files_sampled,
        sampling_ratio=sampling_ratio,
        funnel=funnel,
        project_roots_discovered=discovery.project_roots_discovered,
        project_roots_analyzed=discovery.project_roots_analyzed,
    )
