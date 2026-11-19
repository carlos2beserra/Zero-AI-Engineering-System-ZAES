#!/usr/bin/env python3
"""Stage 5: STABILITY SCORING — multi-run Jaccard drift detection.

Zero-LLM. Zero I/O except reading history from disk.
Returns StabilityResult or None (first execution).

This stage integrates context_stability.validate_context_stability() into the
pipeline so every run of `maes analyze` computes and surfaces drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .contracts import StabilityResult

_HISTORY_DIR = "context/inferred/.history"
_BC_STEM = "bounded-contexts"
_DEFAULT_THRESHOLD = 0.70


def _load_previous_bounded_contexts(maes_dir: Path) -> tuple[list[dict] | None, str | None]:
    """Load the most recent bounded-contexts snapshot from .history/.

    Returns (contexts, date_str) or (None, None) if no history exists.
    """
    history_dir = maes_dir / _HISTORY_DIR
    if not history_dir.exists():
        return None, None

    # Find all bounded-contexts snapshots, sorted newest first
    candidates = sorted(
        history_dir.glob(f"{_BC_STEM}-*.json"),
        key=lambda p: p.stem,
        reverse=True,
    )
    if not candidates:
        return None, None

    latest = candidates[0]
    # Extract date from filename: "bounded-contexts-20260101.json" → "20260101"
    stem = latest.stem  # e.g. "bounded-contexts-20260101"
    date_str = stem[len(_BC_STEM) + 1:] if len(stem) > len(_BC_STEM) + 1 else None

    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
        # Support both {"bounded_contexts": [...]} and plain [...]
        if isinstance(data, dict):
            contexts = data.get("bounded_contexts", [])
        elif isinstance(data, list):
            contexts = data
        else:
            return None, None
        return contexts, date_str
    except (json.JSONDecodeError, OSError):
        return None, None


def run_stability_scoring(
    bounded_contexts: list[dict],
    maes_dir: Path,
    threshold: float = _DEFAULT_THRESHOLD,
) -> Optional[StabilityResult]:
    """Stage 5 entry point.

    Compares current bounded_contexts against the most recent history snapshot.
    Returns None on the first execution (no history to compare against).
    """
    previous, prev_date = _load_previous_bounded_contexts(maes_dir)
    if previous is None:
        return None

    from ..context_stability import validate_context_stability
    raw = validate_context_stability(previous, bounded_contexts, threshold)

    return StabilityResult(
        avg_jaccard=raw["avg_jaccard"],
        passed=raw["passed"],
        threshold=threshold,
        matched=tuple(raw["matched"]),
        previous_run_date=prev_date,
        drift_detected=not raw["passed"],
        added_contexts=tuple(raw.get("added_contexts", [])),
        removed_contexts=tuple(raw.get("removed_contexts", [])),
    )
