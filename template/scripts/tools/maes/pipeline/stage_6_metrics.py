#!/usr/bin/env python3
"""Stage 6: METRICS AGGREGATION — pure metrics computation.

Zero-LLM. Zero I/O. Returns MetricsResult.
Extracted from analyze_cmd._write_context_metrics() computation logic.
"""

from __future__ import annotations

import json

from .contracts import DiscoveryResult, MetricsResult


def aggregate_metrics(analysis: dict, discovery: DiscoveryResult) -> MetricsResult:
    """Stage 6 entry point. Pure computation — no I/O.

    Aggregates token estimates, section sizes, and collection stats.
    """
    gaps = analysis.get("gaps") or {}

    def _json_chars(key: str) -> int:
        val = analysis.get(key) or gaps.get(key)
        return len(json.dumps(val, ensure_ascii=False)) if val else 0

    def _nested_chars(outer: str, inner: str) -> int:
        outer_val = analysis.get(outer) or {}
        val = outer_val.get(inner) if isinstance(outer_val, dict) else None
        return len(json.dumps(val, ensure_ascii=False)) if val else 0

    sections = {
        "ai_likely_mistakes": _json_chars("ai_likely_mistakes"),
        "behavior_contracts": _json_chars("behavior_contracts"),
        "warning_antipatterns": _json_chars("warning_antipatterns"),
        "constraints": _json_chars("constraints"),
        "modules": _json_chars("modules"),
        "bounded_contexts": _json_chars("bounded_contexts"),
        "data_model": _json_chars("data_model"),
        "notable_patterns": _nested_chars("code_patterns", "notable_patterns"),
        "confidence": _json_chars("_confidence"),
    }
    total_inferred = sum(sections.values())

    modules_raw = analysis.get("modules")
    if isinstance(modules_raw, list):
        modules_count = len(modules_raw)
    elif isinstance(modules_raw, dict):
        modules_count = len(modules_raw.get("modules", []))
    else:
        modules_count = 0

    mistakes = analysis.get("ai_likely_mistakes") or gaps.get("ai_likely_mistakes") or []

    return MetricsResult(
        total_inferred_chars=total_inferred,
        token_estimate=total_inferred // 4,
        sections=sections,
        mistakes_with_id_count=sum(1 for m in mistakes if isinstance(m, dict) and m.get("id")),
        modules_count=modules_count,
        collection_total_files=len(discovery.files),
        collection_total_chars=discovery.total_chars,
        collection_budget_pct=discovery.budget_used_pct,
    )
