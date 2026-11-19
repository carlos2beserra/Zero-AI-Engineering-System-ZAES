#!/usr/bin/env python3
"""Immutable data contracts for each stage of the MAES analysis pipeline.

All dataclasses are frozen so stage outputs cannot be mutated after creation.
Dicts inside frozen dataclasses are not deeply immutable but are treated as
read-only by convention — no stage may mutate another stage's output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DiscoveryResult:
    """Output of Stage 1 (Discovery). Immutable snapshot of collected project files.

    `files` is the CONTENT SAMPLE (budget-capped); `source_paths` is the POPULATION
    (complete, no budget). They are facts of different kinds and must never be
    conflated into one number — see ADR 0009.
    """

    files: tuple[tuple[str, str], ...]  # (rel_path, content) — the sample
    file_tree: str
    total_chars: int
    truncated_files: frozenset[str]
    dirs_seen: frozenset[str]
    budget_used_pct: float
    # Population: every source file in the project, from scan_project(). Default ()
    # keeps direct constructors working; consumers must warn when falling back.
    source_paths: tuple[str, ...] = ()
    # Collection-policy observation (not population): how many subproject roots
    # existed vs how many were analyzed. A protection limit must never look like
    # absence of evidence.
    project_roots_discovered: int = 0
    project_roots_analyzed: int = 0


@dataclass(frozen=True)
class DepResult:
    """Output of Stage 3 (Dependency Analysis). Layer violations + boundary map."""

    violations: tuple[dict, ...]
    boundary_map: dict[str, str]


@dataclass(frozen=True)
class GitResult:
    """Output of git history analysis. Optional — None when no .git exists."""

    co_change_clusters: tuple[dict, ...]
    high_churn_files: tuple[dict, ...]
    assertions: tuple[str, ...]
    days_analyzed: int
    commits_analyzed: int


@dataclass(frozen=True)
class BuiltContext:
    """Output of Stage 4 (Context Builder). Pure computation, no I/O."""

    bounded_contexts: tuple[dict, ...]   # fingerprints injected, entities normalized
    confidence: dict                     # capped confidence assessment
    coverage: dict                       # budget/truncation stats
    analysis_raw: dict                   # original LLM output preserved


@dataclass(frozen=True)
class StabilityResult:
    """Output of Stage 5 (Stability Scoring). Jaccard drift detection."""

    avg_jaccard: float
    passed: bool
    threshold: float
    matched: tuple[dict, ...]
    previous_run_date: Optional[str]          # None = first execution
    drift_detected: bool                      # True when avg_jaccard < threshold
    added_contexts: tuple[str, ...] = field(default_factory=tuple)    # contexts in run2 only
    removed_contexts: tuple[str, ...] = field(default_factory=tuple)  # contexts in run1 only


@dataclass(frozen=True)
class MetricsResult:
    """Output of Stage 6 (Metrics Aggregation). Pure aggregate metrics."""

    total_inferred_chars: int
    token_estimate: int
    sections: dict[str, int]
    mistakes_with_id_count: int
    modules_count: int
    collection_total_files: int
    collection_total_chars: int
    collection_budget_pct: float


@dataclass(frozen=True)
class StructuralTransformationMetrics:
    """Structural Transformation Funnel (ADR 0009).

    Descriptive counts, one per REDUCTION STEP — never evaluative: no score, no
    threshold, no adherence. Adding a step means adding a field here plus a mapping
    in emission; never adding a synonym for an existing step (two counts for the
    same transformation is how a funnel stops being diagnostic).

    `source_files` is the ENUMERATED POPULATION — not "files the collector found".
    Confusing the two is the origin of the self-referential coverage bug.

    `candidates` is the sentinel: it depends only on the inventory and the structural
    grouping rules — not on content sampling, budget or semantic enrichment.
    """

    source_files: int
    candidates: int
    collapsed: int
    nodes: int


@dataclass(frozen=True)
class ArchitectureMapResult:
    """Output of Stage 2 (Architecture Builder). Zero-LLM deterministic arch map."""

    nodes: tuple[dict, ...]          # ArchitectureNode.to_dict() for each node
    layer_map: dict[str, str]        # from dep_analysis (dir → layer label)
    modeled_coverage_pct: float      # files_assigned / files_total (population)
    files_assigned: int              # files belonging to at least one node
    files_total: int                 # POPULATION: source files in the project
    node_quality: dict               # avg_files_per_node, orphan_nodes_count, etc.
    dep_edges: dict[str, list[str]]  # stable_key → [stable_keys] dependency graph
    is_frontend_project: bool = False
    files_sampled: int = 0           # EVIDENCE: population files whose content was read
    sampling_ratio: float = 0.0      # files_sampled / files_total — population, not volume
    funnel: Optional[StructuralTransformationMetrics] = None
    # Collection-policy observation: a protection limit must never look like
    # absence of evidence (ADR 0009).
    project_roots_discovered: int = 0
    project_roots_analyzed: int = 0


@dataclass(frozen=True)
class PipelineOutput:
    """Complete output of the full analysis pipeline. Passed to Stage 7 (Emission)."""

    discovery: DiscoveryResult
    analysis_raw: dict
    dep: DepResult
    git: Optional[GitResult]
    context: BuiltContext
    stability: Optional[StabilityResult]
    metrics: MetricsResult
    timestamp: str
    migration_stack: dict
    arch_map: Optional[ArchitectureMapResult] = None
