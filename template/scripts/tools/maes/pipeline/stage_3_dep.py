#!/usr/bin/env python3
"""Stage 3: DEPENDENCY ANALYSIS — typed wrapper over dep_analysis.

Pure function. Zero-LLM. No disk writes.
Returns DepResult with layer violations and boundary map.
"""

from __future__ import annotations

from pathlib import Path

from .contracts import DepResult


def run_dep_stage(project_dir: Path) -> DepResult:
    """Stage 3 entry point. Delegates to dep_analysis.analyze_imports().

    Always succeeds — returns empty violations on any error.
    """
    try:
        from ..dep_analysis import analyze_imports
        raw = analyze_imports(project_dir)
    except Exception:
        return DepResult(violations=(), boundary_map={})

    return DepResult(
        violations=tuple(raw.get("layer_violations", [])),
        boundary_map=dict(raw.get("boundary_map", {})),
    )
