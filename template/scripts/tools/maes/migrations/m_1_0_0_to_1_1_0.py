"""Migration 1.0.0 → 1.1.0

Consolidate the six specialist agents into the single advisory `maes-review`.

Removes, for each consumer project:
  - .maes/agents/{id}.agent.yaml             (source agent definitions)
  - generated adapter files for {id} across all IDE output dirs
  - .maes/adapters/                          (staging — regenerated on next sync)
and rewrites:
  - .maes/config.yaml agents: list           → maes-review + operational agents
  - .maes/evals/scenarios/*.eval.yaml        agent: {removed} → maes-review

The `maes-review.agent.yaml` template itself is (re)deployed by the upgrade flow's
_copy_templates() step that runs after migrations.

NOTE (HEAD fallback): migrations are version-gated, so a project already stamped
>= 1.1.0 will NOT run this. Such projects can clean up manually with
`maes agent remove backend-architect frontend-engineer security-engineer \
 migration-guardian metrics-architect code-reviewer` followed by `maes sync`.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from maes.migrations import Migration

_REMOVED_AGENTS = (
    "backend-architect",
    "frontend-engineer",
    "security-engineer",
    "migration-guardian",
    "metrics-architect",
    "code-reviewer",
)
_TARGET_AGENTS = ["maes-review", "maes-analyze", "maes-context-add", "maes-eval"]

# (dir relative to project root, filename suffix) for per-agent generated files.
_GENERATED_PATTERNS = (
    (".claude/commands", ".md"),
    (".cursor/rules", ".mdc"),
    (".continue/rules", ".md"),
    (".github/instructions", ".instructions.md"),
    (".github/skills", ".md"),
)


def _remove_source_agents(maes_dir: Path) -> None:
    agents_dir = maes_dir / "agents"
    for agent_id in _REMOVED_AGENTS:
        f = agents_dir / f"{agent_id}.agent.yaml"
        if f.exists():
            f.unlink()


def _remove_generated(project_dir: Path) -> None:
    for rel_dir, suffix in _GENERATED_PATTERNS:
        d = project_dir / rel_dir
        if not d.exists():
            continue
        for agent_id in _REMOVED_AGENTS:
            f = d / f"{agent_id}{suffix}"
            if f.exists():
                f.unlink(missing_ok=True)
            # skills may be a per-agent directory
            sk = d / agent_id
            if sk.is_dir():
                shutil.rmtree(sk, ignore_errors=True)


def _clean_staging(maes_dir: Path) -> None:
    staging = maes_dir / "adapters"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)


def _fix_config(maes_dir: Path) -> None:
    config_path = maes_dir / "config.yaml"
    if not config_path.exists():
        return
    try:
        import yaml
    except ImportError:
        return
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return
    current = data.get("agents") or []
    kept = [a for a in current if a not in _REMOVED_AGENTS]
    for a in _TARGET_AGENTS:
        if a not in kept:
            kept.append(a)
    data["agents"] = kept
    config_path.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def _fix_eval_scenarios(maes_dir: Path) -> None:
    scenarios = maes_dir / "evals" / "scenarios"
    if not scenarios.exists():
        return
    for f in scenarios.glob("*.eval.yaml"):
        lines = f.read_text(encoding="utf-8").splitlines(keepends=True)
        changed = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("agent:"):
                value = stripped.split(":", 1)[1].strip()
                if value in _REMOVED_AGENTS:
                    indent = line[: len(line) - len(line.lstrip())]
                    lines[i] = f"{indent}agent: maes-review\n"
                    changed = True
        if changed:
            f.write_text("".join(lines), encoding="utf-8")


def _run(maes_dir: Path) -> None:
    project_dir = maes_dir.parent
    _remove_source_agents(maes_dir)
    _remove_generated(project_dir)
    _clean_staging(maes_dir)
    _fix_config(maes_dir)
    _fix_eval_scenarios(maes_dir)


MIGRATION = Migration(
    from_version="1.0.0",
    to_version="1.1.0",
    description="Consolidate 6 specialist agents into maes-review; clean sources, generated files, config and eval scenarios",
    run=_run,
)
