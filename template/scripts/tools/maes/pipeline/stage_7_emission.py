#!/usr/bin/env python3
"""Stage 7: EMISSION — the ONLY stage allowed to write to disk.

All filesystem writes for the analysis pipeline are consolidated here.
No other stage may call write_text(), open(..., 'w'), or any I/O operation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from .contracts import BuiltContext, MetricsResult, PipelineOutput

if TYPE_CHECKING:
    from .stage_1_discovery import _Collector

_HISTORY_DIR = ".history"
_HISTORY_KEEP = 5
_FILE_GAPS = "gaps.json"
_FILE_PATTERNS = "patterns.json"
_FILE_DATA_MODEL = "data-model.json"
_HISTORY_FILES = (_FILE_GAPS, _FILE_PATTERNS, _FILE_DATA_MODEL)
_BC_STEM = "bounded-contexts"
_FILE_ARCH_MAP = "architecture_map.json"


# ─── Coverage ─────────────────────────────────────────────────────────────────

def _write_coverage(inferred: Path, col: "_Collector") -> None:
    """Write coverage.json. Accepts _Collector for backward compatibility."""
    truncated = sorted(col._truncated)
    dirs_seen = sorted({p.split("/")[0] for p in col._seen})
    from .stage_1_discovery import _MAX_TOTAL_CHARS
    coverage = {
        "total_files_collected": len(col._seen),
        "total_chars": col._chars,
        "budget_used_pct": round(col._chars / _MAX_TOTAL_CHARS * 100, 1),
        "truncated_files": truncated,
        "truncated_count": len(truncated),
        "dirs_collected": dirs_seen,
    }
    (inferred / "coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _emit_coverage(inferred: Path, context: BuiltContext) -> None:
    """Write coverage.json from BuiltContext (new pipeline path)."""
    (inferred / "coverage.json").write_text(
        json.dumps(context.coverage, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─── History ──────────────────────────────────────────────────────────────────

def _save_history(inferred: Path, analysis: dict, date_str: str) -> None:
    history_dir = inferred / _HISTORY_DIR
    history_dir.mkdir(exist_ok=True)
    file_map = {
        _FILE_GAPS: analysis.get("gaps", {}),
        _FILE_PATTERNS: analysis.get("code_patterns", {}),
        _FILE_DATA_MODEL: analysis.get("data_model", {}),
    }
    for fname, data in file_map.items():
        stem = fname.rsplit(".json", 1)[0]
        (history_dir / f"{stem}-{date_str}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    _prune_history(history_dir)


def _save_bc_history(inferred: Path, bounded_contexts: list, date_str: str) -> None:
    """Snapshot bounded contexts with stable_ids injected by Stage 4.

    Called separately from _save_history() so the snapshot always contains
    the post-Stage 4 data (stable_id, module_fingerprint) rather than the
    raw LLM output which lacks these fields.
    """
    if not bounded_contexts:
        return
    history_dir = inferred / _HISTORY_DIR
    history_dir.mkdir(exist_ok=True)
    (history_dir / f"{_BC_STEM}-{date_str}.json").write_text(
        json.dumps({"bounded_contexts": bounded_contexts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _prune_history(history_dir)


def _prune_history(history_dir: Path) -> None:
    by_stem: dict[str, list[Path]] = {}
    for f in sorted(history_dir.glob("*.json")):
        stem = f.stem.rsplit("-", 1)[0]
        by_stem.setdefault(stem, []).append(f)
    for files in by_stem.values():
        for old in files[:-_HISTORY_KEEP]:
            old.unlink(missing_ok=True)


# ─── Inferred outputs ─────────────────────────────────────────────────────────

def _write_inferred(inferred: Path, analysis: dict, date_str: str) -> None:
    inferred.mkdir(parents=True, exist_ok=True)

    gaps = analysis.get("gaps", {})
    constraints = gaps.get("constraints", [])
    if isinstance(constraints, str) and constraints.strip():
        gaps["constraints"] = [constraints.strip()]
    elif not isinstance(constraints, list):
        gaps["constraints"] = []
    (inferred / "gaps.json").write_text(
        json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (inferred / "stack.json").write_text(
        json.dumps(analysis.get("stack", {}), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    modules = analysis.get("modules", [])
    (inferred / "modules.json").write_text(
        json.dumps({"modules": modules}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (inferred / "data-model.json").write_text(
        json.dumps(analysis.get("data_model", {}), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (inferred / "patterns.json").write_text(
        json.dumps(analysis.get("code_patterns", {}), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (inferred / "_full-analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    notes = analysis.get("_analyzer_notes", "")
    if notes:
        (inferred / "analyzer-notes.md").write_text(notes[:3_000], encoding="utf-8")

    _save_history(inferred, analysis, date_str)


# ─── Derived outputs (bounded contexts, confidence, metrics) ──────────────────

def _write_derived_outputs(inferred: Path, analysis: dict, col: "_Collector") -> None:
    """Write derived outputs from analysis. Backward-compatible signature using _Collector.

    Called from test_bounded_contexts.py and legacy paths in analyze_cmd.py.
    New code should use emit_pipeline_outputs() instead.
    """
    from .stage_4_context_build import _apply_confidence_cap, _normalize_entity_ownership, _compute_fingerprint
    from .stage_1_discovery import _MAX_TOTAL_CHARS

    _write_coverage(inferred, col)

    confidence = analysis.get("_confidence", {})
    if confidence:
        confidence = _apply_confidence_cap(confidence, col)
        (inferred / "confidence.json").write_text(
            json.dumps(confidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    bc_path = inferred / "bounded-contexts.json"
    if bc_path.exists():
        data = json.loads(bc_path.read_text(encoding="utf-8"))
        for ctx in data.get("bounded_contexts", []):
            ctx["module_fingerprint"] = _compute_fingerprint(ctx.get("modules", []))
            ctx["shared_entities"] = _normalize_entity_ownership(
                ctx.get("shared_entities", []), ctx.get("name", "")
            )
        bc_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    _write_context_metrics(inferred, analysis, col)


def _write_context_metrics(inferred: Path, analysis: dict, col: "_Collector") -> None:
    """Write context-metrics.json. Uses _Collector for budget stats."""
    from .stage_6_metrics import aggregate_metrics
    from .contracts import DiscoveryResult

    # Build a minimal DiscoveryResult from the collector for aggregate_metrics
    discovery = DiscoveryResult(
        files=tuple((p, "") for p in col._seen),
        file_tree="",
        total_chars=col._chars,
        truncated_files=frozenset(col._truncated),
        dirs_seen=frozenset(p.split("/")[0] for p in col._seen),
        budget_used_pct=col.budget_used_pct if hasattr(col, "budget_used_pct") else 0.0,
    )
    metrics = aggregate_metrics(analysis, discovery)
    data = {
        "total_inferred_chars": metrics.total_inferred_chars,
        "token_estimate": metrics.token_estimate,
        "sections": metrics.sections,
        "mistakes_with_id_count": metrics.mistakes_with_id_count,
        "avg_context_size_per_module": metrics.total_inferred_chars // max(metrics.modules_count, 1),
        "collection": {
            "total_files": metrics.collection_total_files,
            "total_chars_collected": metrics.collection_total_chars,
            "budget_used_pct": metrics.collection_budget_pct,
        },
    }
    (inferred / "context-metrics.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─── Stability report ─────────────────────────────────────────────────────────

def _dep_graph_reliability(flat_edges: list[dict]) -> dict:
    """Trust signal for the architecture dependency graph (heuristic SIGNAL only —
    does not modify edges). Relative-import resolution may misattribute/fabricate
    edges and alias (@/) imports are not captured, so agents must NOT treat this
    graph as ground truth. Machine-readable flags (agents act on flags, not prose).
    """
    from collections import Counter
    n = len(flat_edges)
    top_pct = 0.0
    top_sink = None
    if n:
        top_sink, cnt = Counter(e["to"] for e in flat_edges).most_common(1)[0]
        top_pct = round(cnt / n, 3)
    return {
        "authoritative": False,
        "trust_level": "experimental",
        "agent_safe": False,
        "max_edge_target_concentration_pct": top_pct,
        "suspected_artificial_hub": top_sink if top_pct >= 0.30 else None,
        "guidance": (
            "Dependency edges are heuristic: TS/relative-import resolution may "
            "misattribute or fabricate edges, and alias (@/) imports are not captured. "
            "Coverage is relative to a budget-capped snapshot, not the whole codebase. "
            "Do NOT treat this graph as ground truth — verify against source."
        ),
    }


_COVERAGE_SCOPE = (
    "Project source-file population enumerated by Stage 1 (scan_project). "
    "Coverage is measured against that population; sampling_ratio reports how much "
    "of it had content read within the 200k-char budget. Population is not "
    "budget-capped — only reading is."
)


def _project_metadata(arch_map) -> dict:
    """Frontend flag plus the root-truncation counters it must be read against.

    ADR 0009: `is_frontend_project: false` together with `project_roots_truncated:
    true` is NOT negative evidence — it means "found no frontend manifest among the
    roots I analyzed", not "this project has no frontend". A protection limit must
    never look like absence of evidence.
    """
    discovered = arch_map.project_roots_discovered
    analyzed = arch_map.project_roots_analyzed
    return {
        "is_frontend_project": arch_map.is_frontend_project,
        "project_roots_discovered": discovered,
        "project_roots_analyzed": analyzed,
        "project_roots_truncated": discovered > analyzed,
    }


def _diagnostic_metrics(arch_map, *, node_count: int) -> dict:
    """Structural Transformation Funnel + evidence counts.

    Funnel keys are named for the concept: `source_files` is the enumerated
    population, NOT "files the collector found".
    """
    funnel = arch_map.funnel
    return {
        "source_files": arch_map.files_total,
        "candidate_count": funnel.candidates if funnel else 0,
        "collapsed_count": funnel.collapsed if funnel else 0,
        "node_count": node_count,
        "sampled_files": arch_map.files_sampled,
        "sampling_ratio": arch_map.sampling_ratio,
        "modeled_files": arch_map.files_assigned if node_count else 0,
        "unmodeled_files": (
            arch_map.files_total - arch_map.files_assigned
            if node_count
            else arch_map.files_total
        ),
    }


def _coverage_warning(arch_map) -> str | None:
    """Prose form of the limitations a consumer must not miss.

    The sampling threshold comes from sampling_policy — the same policy any consumer
    of a CONTENT-derived claim must consult, rather than a floor duplicated here.
    """
    from ..sampling_policy import has_sufficient_sample

    parts: list[str] = []
    if arch_map.modeled_coverage_pct < 0.5:
        parts.append(
            "Modeled coverage < 50% — project may have files outside standard "
            "source patterns"
        )
    if not has_sufficient_sample(arch_map.sampling_ratio):
        parts.append(
            f"Only {arch_map.sampling_ratio * 100:.0f}% of source files had content "
            "read — semantic fields (entry_points, dep_edges) are under-evidenced; "
            "compare file_count vs files_sampled per node"
        )
    if arch_map.project_roots_discovered > arch_map.project_roots_analyzed:
        parts.append(
            f"Only {arch_map.project_roots_analyzed} of "
            f"{arch_map.project_roots_discovered} project roots were analyzed"
            + (
                "; is_frontend_project=false is NOT negative evidence here"
                if not arch_map.is_frontend_project
                else ""
            )
        )
    return ". ".join(parts) if parts else None


def _emit_architecture_map(
    inferred: Path,
    arch_map,  # ArchitectureMapResult | None
) -> None:
    """Write architecture_map.json (schema v2.1). dep_edges are embedded in graph.edges.

    2.1 changes the MEANING of the coverage numbers (denominator is now the project
    population, not the content sample) and renames two funnel keys for accuracy:
    discovered_files → source_files, total_nodes → node_count. See ADR 0009.
    """
    _SCHEMA_VER = "2.1"
    _SCHEMA_META = {
        "source": "maes build-arch-map",
        "generator": "stage_2_arch_builder",
        "schema_version": _SCHEMA_VER,
    }

    if arch_map is None:
        skeleton = {
            "schema_version": _SCHEMA_VER,
            "status": "no_arch_map",
            "schema_metadata": _SCHEMA_META,
            "reliability": _dep_graph_reliability([]),
            "nodes": [],
            "graph": {"edges": [], "dep_edge_count": 0},
        }
        (inferred / _FILE_ARCH_MAP).write_text(
            json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return

    if not arch_map.nodes:
        skeleton = {
            "schema_version": _SCHEMA_VER,
            "status": "empty_no_nodes",
            "schema_metadata": _SCHEMA_META,
            "reliability": _dep_graph_reliability([]),
            "project_metadata": _project_metadata(arch_map),
            "diagnostic_metrics": _diagnostic_metrics(arch_map, node_count=0),
            "coverage_context": {
                "scope": _COVERAGE_SCOPE,
                "modeled_coverage_pct": 0.0,
                "sampling_ratio": arch_map.sampling_ratio,
                "warning": (
                    "No nodes generated. Verify project has source files"
                    " in recognized patterns."
                ),
                "note": None,
            },
            "nodes": [],
            "graph": {"edges": [], "dep_edge_count": 0},
        }
        (inferred / _FILE_ARCH_MAP).write_text(
            json.dumps(skeleton, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return

    nodes_list = list(arch_map.nodes)
    flat_edges = [
        {"from": src, "to": tgt, "type": "import"}
        for src, targets in sorted(arch_map.dep_edges.items())
        for tgt in sorted(targets)
    ]
    arch_payload = {
        "schema_version": _SCHEMA_VER,
        "status": "generated",
        "schema_metadata": _SCHEMA_META,
        "reliability": _dep_graph_reliability(flat_edges),
        "project_metadata": _project_metadata(arch_map),
        "diagnostic_metrics": _diagnostic_metrics(arch_map, node_count=len(nodes_list)),
        "coverage_context": {
            "scope": _COVERAGE_SCOPE,
            "modeled_coverage_pct": arch_map.modeled_coverage_pct,
            "sampling_ratio": arch_map.sampling_ratio,
            "warning": _coverage_warning(arch_map),
            "note": (
                "TypeScript dep_edges include relative imports only"
                " (permanent parser limitation)"
            ),
        },
        "nodes": nodes_list,
        "graph": {"edges": flat_edges, "dep_edge_count": len(flat_edges)},
    }
    (inferred / _FILE_ARCH_MAP).write_text(
        json.dumps(arch_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _emit_stability_report(inferred: Path, stability) -> None:
    """Write stability-report.json if stability result is available."""
    if stability is None:
        return
    report = {
        "avg_jaccard": stability.avg_jaccard,
        "passed": stability.passed,
        "threshold": stability.threshold,
        "drift_detected": stability.drift_detected,
        "previous_run_date": stability.previous_run_date,
        "matched": list(stability.matched),
        "added_contexts": list(stability.added_contexts),
        "removed_contexts": list(stability.removed_contexts),
    }
    (inferred / "stability-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─── Pipeline emission entry point ────────────────────────────────────────────

def emit_pipeline_outputs(
    maes_dir: Path,
    output: PipelineOutput,
    date_str: str,
) -> None:
    """Stage 7 entry point. Write all pipeline outputs to disk.

    This is the ONLY function in the analysis pipeline allowed to perform I/O.
    """
    inferred = maes_dir / "context" / "inferred"
    inferred.mkdir(parents=True, exist_ok=True)

    # Write inferred JSON files (uses analysis_raw — bounded-contexts snapshot excluded)
    _write_inferred(inferred, output.analysis_raw, date_str)

    # Snapshot bounded contexts with stable_ids injected by Stage 4
    _save_bc_history(inferred, list(output.context.bounded_contexts), date_str)

    # Write dep analysis
    deps_data = {
        "layer_violations": list(output.dep.violations),
        "boundary_map": output.dep.boundary_map,
    }
    (inferred / "deps.json").write_text(
        json.dumps(deps_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Write git patterns
    if output.git is not None:
        git_data = {
            "co_change_clusters": list(output.git.co_change_clusters),
            "high_churn_files": list(output.git.high_churn_files),
            "assertions": list(output.git.assertions),
            "metadata": {
                "days_analyzed": output.git.days_analyzed,
                "commits_analyzed": output.git.commits_analyzed,
            },
        }
        (inferred / "git-patterns.json").write_text(
            json.dumps(git_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Write coverage
    _emit_coverage(inferred, output.context)

    # Write confidence
    if output.context.confidence:
        (inferred / "confidence.json").write_text(
            json.dumps(output.context.confidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Write bounded contexts (fingerprints already injected by stage 4)
    if output.context.bounded_contexts:
        bc_list = list(output.context.bounded_contexts)
        (inferred / "bounded-contexts.json").write_text(
            json.dumps({"bounded_contexts": bc_list}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # Write metrics
    metrics = output.metrics
    metrics_data = {
        "total_inferred_chars": metrics.total_inferred_chars,
        "token_estimate": metrics.token_estimate,
        "sections": metrics.sections,
        "mistakes_with_id_count": metrics.mistakes_with_id_count,
        "avg_context_size_per_module": metrics.total_inferred_chars // max(metrics.modules_count, 1),
        "collection": {
            "total_files": metrics.collection_total_files,
            "total_chars_collected": metrics.collection_total_chars,
            "budget_used_pct": metrics.collection_budget_pct,
        },
    }
    (inferred / "context-metrics.json").write_text(
        json.dumps(metrics_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Write stability report
    _emit_stability_report(inferred, output.stability)

    # Write architecture_map.json (Stage 2 outputs, schema v2.0)
    _emit_architecture_map(inferred, output.arch_map)
