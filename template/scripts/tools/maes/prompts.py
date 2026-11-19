#!/usr/bin/env python3
"""Centralized registry of all LLM system prompts used by MAES commands.

This module is the single source of truth for every system prompt.
Centralizing them here enables:
  - Version-controlled prompt history (git blame is useful)
  - A/B testing by swapping constants before a call
  - Observability: any logging layer can reference prompt names, not raw strings

Rules:
  - NEVER define a system prompt inline in a command module
  - Reference prompts from this module via import
"""

from __future__ import annotations

# ─── eval ─────────────────────────────────────────────────────────────────────

EVAL_JUDGE_SYSTEM = "You are a precise evaluator. Return only JSON."

EVAL_AGENT_BASE_SYSTEM = "You are a senior engineer."
