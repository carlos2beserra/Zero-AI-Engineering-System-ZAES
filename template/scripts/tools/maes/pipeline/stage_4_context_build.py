#!/usr/bin/env python3
"""Stage 4: CONTEXT BUILDER — pure transformation of LLM analysis output.

Zero-LLM. Zero I/O. Deterministic pure functions.
Accepts analysis dict + DiscoveryResult and returns BuiltContext.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from .contracts import BuiltContext, DiscoveryResult

if TYPE_CHECKING:
    from .stage_1_discovery import _Collector

# ─── Constants ────────────────────────────────────────────────────────────────

# Minimum number of distinct top-level source dirs required for "full" coverage.
# Structural signal: a project collected from only 1 directory is unlikely to be
# representative of the full codebase regardless of framework naming conventions.
_MIN_SOURCE_DIRS_FOR_FULL_COVERAGE = 2

# Imported lazily to avoid circular; used only in _apply_confidence_cap(col) path.
_MAX_TOTAL_CHARS_FALLBACK = 200_000


# ─── Confidence cap ───────────────────────────────────────────────────────────

def _count_source_dirs(seen: "frozenset[str]") -> int:
    """Count distinct top-level directories that contain files with extensions."""
    dirs: set[str] = set()
    for p in seen:
        parts = PurePosixPath(p.replace("\\", "/")).parts
        if len(parts) >= 1 and "." in parts[-1]:
            dirs.add(parts[0].lower())
    return len(dirs)


def _apply_confidence_cap(confidence: dict, col_or_discovery) -> dict:
    """Apply deterministic confidence overrides.

    Rule precedence (highest to lowest):
      1. Explicit truncation → max "partial"
      2. Budget pressure (>80%) → max "partial"
      3. No recognized critical dirs → max "partial"

    Accepts _Collector (backward compat) or DiscoveryResult.
    """
    result = dict(confidence)

    # Extract stats from either type (duck typing for backward compat)
    if isinstance(col_or_discovery, DiscoveryResult):
        truncated = len(col_or_discovery.truncated_files)
        budget_pct = col_or_discovery.budget_used_pct
        seen = frozenset(path for path, _ in col_or_discovery.files)
    else:
        # _Collector duck typing
        from .stage_1_discovery import _MAX_TOTAL_CHARS
        truncated = len(col_or_discovery._truncated)
        budget_pct = col_or_discovery._chars / _MAX_TOTAL_CHARS * 100
        seen = frozenset(col_or_discovery._seen)

    coverage_degraded = False

    if truncated > 0 and result.get("coverage_level") == "full":
        result["coverage_level"] = "partial"
        rationale = result.get("coverage_rationale", "")
        result["coverage_rationale"] = (rationale + f" [cap: {truncated} truncated]")[:200]
        coverage_degraded = True
    elif budget_pct > 80 and result.get("coverage_level") == "full":
        result["coverage_level"] = "partial"
        result["coverage_rationale"] = (
            result.get("coverage_rationale", "") + f" [cap: budget {budget_pct:.0f}%]"
        )[:200]
        coverage_degraded = True

    source_dir_count = _count_source_dirs(seen)
    if source_dir_count < _MIN_SOURCE_DIRS_FOR_FULL_COVERAGE and result.get("coverage_level") == "full":
        result["coverage_level"] = "partial"
        result["coverage_rationale"] = (
            result.get("coverage_rationale", "")
            + f" [cap: only {source_dir_count} source dir(s) collected]"
        )[:200]
        coverage_degraded = True

    # Cascade cap to section_confidence: LLM may return "high" for sections
    # whose source files were truncated or not reached due to budget overflow.
    # Cap those to "partial" so calibration in downstream phases uses honest data.
    if coverage_degraded and "section_confidence" in result:
        result["section_confidence"] = {
            section: ("partial" if conf == "high" else conf)
            for section, conf in result["section_confidence"].items()
        }

    return result


# ─── Entity ownership normalization ───────────────────────────────────────────

def _normalize_entity_ownership(entities: list, context_name: str) -> list:
    """Normalize shared_entities to [{name, owner_context}] format.

    owner_context is inferred structurally from the containing bounded context.
    It is metadata only — never domain truth. Always nullable.
    """
    result = []
    for e in entities:
        if isinstance(e, str):
            result.append({"name": e, "owner_context": context_name})
        elif isinstance(e, dict):
            if "owner_context" not in e:
                e = dict(e)
                e["owner_context"] = context_name
            result.append(e)
    return result


# ─── Module fingerprint ───────────────────────────────────────────────────────

def _compute_fingerprint(modules: list[str]) -> str:
    """Deterministic SHA-256 fingerprint for a bounded context's module list."""
    normalized = sorted(
        m.replace("\\", "/").strip("/").lower()
        for m in modules
    )
    return hashlib.sha256(json.dumps(normalized).encode()).hexdigest()[:12]


# ─── Coverage dict builder ────────────────────────────────────────────────────

def _build_coverage_dict(discovery: DiscoveryResult) -> dict:
    return {
        "total_files_collected": len(discovery.files),
        "total_chars": discovery.total_chars,
        "budget_used_pct": discovery.budget_used_pct,
        "truncated_files": sorted(discovery.truncated_files),
        "truncated_count": len(discovery.truncated_files),
        "dirs_collected": sorted(discovery.dirs_seen),
    }


# ─── Stage 4 entry point ──────────────────────────────────────────────────────

def build_context(analysis: dict, discovery: DiscoveryResult) -> BuiltContext:
    """Stage 4 entry point. Pure transformation — no I/O.

    Injects fingerprints into bounded contexts, applies confidence cap,
    normalizes entity ownership, and returns an immutable BuiltContext.
    """
    # Process bounded contexts: inject fingerprint + normalize entity ownership
    raw_bc = analysis.get("bounded_contexts", [])
    processed_bc = []
    for ctx in raw_bc:
        ctx_copy = dict(ctx)
        ctx_copy["module_fingerprint"] = _compute_fingerprint(ctx.get("modules", []))
        ctx_copy["stable_id"] = hashlib.sha256(ctx.get("name", "").encode()).hexdigest()[:12]
        ctx_copy["shared_entities"] = _normalize_entity_ownership(
            ctx.get("shared_entities", []), ctx.get("name", "")
        )
        processed_bc.append(ctx_copy)

    # Apply confidence cap
    confidence = dict(analysis.get("_confidence", {}))
    if confidence:
        confidence = _apply_confidence_cap(confidence, discovery)

    coverage = _build_coverage_dict(discovery)

    return BuiltContext(
        bounded_contexts=tuple(processed_bc),
        confidence=confidence,
        coverage=coverage,
        analysis_raw=analysis,
    )
