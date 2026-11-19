#!/usr/bin/env python3
"""maes agent — manage optional agents from the catalogue."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

_CATALOGUE_DIR = Path(__file__).parent / "templates" / "agents-catalogue"
_CORE_AGENTS_DIR = Path(__file__).parent / "templates" / "agents"
_AGENT_YAML_GLOB = "*.agent.yaml"
_AGENT_YAML_SUFFIX = ".agent.yaml"


def _catalogue_agents() -> list[dict]:
    if not _CATALOGUE_DIR.exists():
        return []
    try:
        import yaml
    except ImportError:
        return []
    agents = []
    for f in sorted(_CATALOGUE_DIR.glob(_AGENT_YAML_GLOB)):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            data["_file"] = f.name
            agents.append(data)
        except Exception:
            continue
    return agents


def _active_agent_ids(maes_dir: Path) -> set[str]:
    agents_dir = maes_dir / "agents"
    if not agents_dir.exists():
        return set()
    return {f.name.replace(_AGENT_YAML_SUFFIX, "") for f in agents_dir.glob(_AGENT_YAML_GLOB)}


def _is_core(agent_id: str) -> bool:
    return (_CORE_AGENTS_DIR / f"{agent_id}{_AGENT_YAML_SUFFIX}").exists()


def run_agent_list(maes_dir: Path) -> int:
    catalogue = _catalogue_agents()
    if not catalogue:
        print("No optional agents in catalogue.")
    else:
        active = _active_agent_ids(maes_dir)

        _G = "\033[32m"
        _X = "\033[0m"
        _D = "\033[2m"

        print("\nOptional agents (catalogue):\n")
        for agent in catalogue:
            aid = agent.get("id", agent["_file"].replace(_AGENT_YAML_SUFFIX, ""))
            name = agent.get("name", aid)
            desc = agent.get("description", "")
            if aid in active:
                status = f"{_G}✔ active   {_X}"
            else:
                status = f"{_D}  available{_X}"
            print(f"  {status}  {aid:<22} {name}")
            if desc:
                print(f"  {_D}             {desc}{_X}")

        print()
        print("Activate:   maes agent add <id>")
        print("Deactivate: maes agent remove <id>")
        print()
    return 0


def run_agent_add(maes_dir: Path, agent_id: str) -> int:
    src = _CATALOGUE_DIR / f"{agent_id}{_AGENT_YAML_SUFFIX}"
    if not src.exists():
        print(f"✗ Agent '{agent_id}' not found in catalogue.", file=sys.stderr)
        available = sorted(
            f.name.replace(_AGENT_YAML_SUFFIX, "") for f in _CATALOGUE_DIR.glob(_AGENT_YAML_GLOB)
        ) if _CATALOGUE_DIR.exists() else []
        if available:
            print(f"  Available: {', '.join(available)}", file=sys.stderr)
        else:
            print("  Run `maes agent list` to see available agents.", file=sys.stderr)
        return 1

    agents_dir = maes_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    dst = agents_dir / f"{agent_id}{_AGENT_YAML_SUFFIX}"

    if dst.exists():
        print(f"⚠ Agent '{agent_id}' is already active. Nothing to do.")
        return 0

    shutil.copy2(src, dst)
    print(f"✔ Agent '{agent_id}' added to .maes/agents/")
    return 0


def run_agent_remove(maes_dir: Path, agent_id: str) -> int:
    if _is_core(agent_id):
        print(f"✗ '{agent_id}' is a core agent and cannot be removed.", file=sys.stderr)
        print("  Core agents are installed by `maes init` and are always active.", file=sys.stderr)
        return 1

    target = maes_dir / "agents" / f"{agent_id}{_AGENT_YAML_SUFFIX}"
    if not target.exists():
        print(f"✗ Agent '{agent_id}' is not active in this project.", file=sys.stderr)
        return 1

    target.unlink()
    print(f"✔ Agent '{agent_id}' removed from .maes/agents/")
    return 0
