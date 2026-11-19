"""MAES Analysis Pipeline — modular stage-based architecture.

Stages:
  1. Discovery         stage_1_discovery.run_discovery()
  2. Arch Builder      stage_2_arch_builder.run_arch_builder()   [zero-LLM]
  2.5. LLM Analysis    analyze_cmd._run_llm_phase()              [LLM — only permitted entry point]
  3. Dependency        stage_3_dep.run_dep_stage()
  4. Context Builder   stage_4_context_build.build_context()
  5. Stability         stage_5_stability.run_stability_scoring()
  6. Metrics           stage_6_metrics.aggregate_metrics()
  7. Emission          stage_7_emission.emit_pipeline_outputs()

Execution order in analyze_cmd.py:
  Stage 1 → Stage 3 → Stage 2 → LLM → Stage 4 → Stage 5 → Stage 6 → Stage 7
  (Stage 3 runs before Stage 2 so dep.boundary_map/layer_map is available to Stage 2)

Public API:
"""

from .contracts import (
    ArchitectureMapResult,
    BuiltContext,
    DepResult,
    DiscoveryResult,
    GitResult,
    MetricsResult,
    PipelineOutput,
    StabilityResult,
)
from .stage_1_discovery import run_discovery
from .stage_2_arch_builder import run_arch_builder
from .stage_3_dep import run_dep_stage
from .stage_4_context_build import build_context
from .stage_5_stability import run_stability_scoring
from .stage_6_metrics import aggregate_metrics
from .stage_7_emission import emit_pipeline_outputs

__all__ = [
    # Contracts
    "ArchitectureMapResult",
    "DiscoveryResult",
    "DepResult",
    "GitResult",
    "BuiltContext",
    "StabilityResult",
    "MetricsResult",
    "PipelineOutput",
    # Stage entry points
    "run_discovery",
    "run_arch_builder",
    "run_dep_stage",
    "build_context",
    "run_stability_scoring",
    "aggregate_metrics",
    "emit_pipeline_outputs",
]
