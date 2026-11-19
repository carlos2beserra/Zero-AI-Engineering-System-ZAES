#!/usr/bin/env python3
"""MAES Staleness — git-aware staleness scoring for Assertions."""

from __future__ import annotations

import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

from .models import Assertion

# ─── TTL parsing ──────────────────────────────────────────────────────────────

_TTL_FALLBACK = 730  # "on-major-refactor" → treat as 2 years


def _parse_ttl(ttl: str) -> int:
    """Return TTL in days. "90d" → 90, "365d" → 365, unknown → 730."""
    if not ttl:
        return _TTL_FALLBACK
    m = re.match(r"^(\d+)d$", ttl.strip().lower())
    if m:
        return int(m.group(1))
    return _TTL_FALLBACK


# ─── Git helpers ──────────────────────────────────────────────────────────────

_DEP_FILES = [
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "prisma/schema.prisma",
    "pyproject.toml",
    "requirements.txt",
    "Pipfile",
    "Pipfile.lock",
    "go.mod",
    "go.sum",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Cargo.toml",
    "Gemfile",
    "Gemfile.lock",
    "composer.json",
    "composer.lock",
]


def _has_git(project_dir: Path) -> bool:
    return (project_dir / ".git").exists() or (project_dir.parent / ".git").exists()


def _git_commit_count(project_dir: Path, paths: list[str], since_days: int) -> int:
    """Count commits in `project_dir` touching any of `paths` within `since_days`."""
    since = (date.today() - timedelta(days=since_days)).isoformat()
    cmd = [
        "git", "-C", str(project_dir),
        "log", "--oneline", f"--since={since}",
        "--",
    ] + paths
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return 0
        return sum(1 for line in result.stdout.splitlines() if line.strip())
    except (subprocess.TimeoutExpired, OSError):
        return 0


def _git_path_activity(
    project_dir: Path,
    paths: list[str],
    window_days: int = 60,
) -> float:
    """Return 0.0–1.0 representing recent git activity on the given paths.

    Linear scale: 0 commits → 0.0, 50+ commits → 1.0.
    Returns 0.0 silently if project_dir has no git repo.
    """
    if not _has_git(project_dir):
        return 0.0
    # Expand glob-like paths to just their base component for git
    clean_paths = []
    for p in paths:
        if p == "**":
            continue
        clean = p.replace("/**", "").replace("/**/*", "").replace("/*", "")
        if clean:
            clean_paths.append(clean)
    if not clean_paths:
        return 0.0
    count = _git_commit_count(project_dir, clean_paths, window_days)
    return min(1.0, count / 50.0)


def _git_dep_activity(project_dir: Path, window_days: int = 60) -> float:
    """Return 0.0–1.0 representing recent commits touching dependency files.

    Linear scale: 0 commits → 0.0, 10+ commits → 1.0.
    """
    if not _has_git(project_dir):
        return 0.0
    existing = [f for f in _DEP_FILES if (project_dir / f).exists()]
    if not existing:
        return 0.0
    count = _git_commit_count(project_dir, existing, window_days)
    return min(1.0, count / 10.0)


# ─── Per-assertion staleness ──────────────────────────────────────────────────

def compute_staleness(
    assertion: Assertion,
    project_dir: Path,
    today: date,
) -> tuple[float, list[str]]:
    """Compute staleness score and reasons for a single assertion.

    Formula: age_factor×0.6 + path_activity×0.25 + dep_changes×0.15

    Returns (score 0.0–1.0, reasons list).
    """
    reasons: list[str] = []

    # Component 1 — age factor (how far past TTL we are)
    ttl_days = _parse_ttl(assertion.ttl)
    try:
        verified = date.fromisoformat(assertion.last_verified)
    except ValueError:
        verified = today
    age_days = max(0, (today - verified).days)
    age_factor = min(1.0, age_days / ttl_days)

    if age_factor >= 1.0:
        reasons.append("ttl_expired")
    elif age_factor >= 0.75:
        reasons.append("ttl_near_expiry")

    # Component 2 — path activity (recent git churn on covered paths)
    specific_paths = [p for p in assertion.paths if p != "**"]
    path_activity = (
        _git_path_activity(project_dir, specific_paths)
        if specific_paths else 0.0
    )
    if path_activity >= 0.5:
        reasons.append("high_git_activity_on_covered_paths")

    # Component 3 — dependency changes (package.json, prisma schema, etc.)
    dep_factor = _git_dep_activity(project_dir)
    if dep_factor >= 0.5:
        reasons.append("dependency_changes_detected")

    score = age_factor * 0.6 + path_activity * 0.25 + dep_factor * 0.15
    return min(1.0, score), reasons


# ─── Batch scoring ────────────────────────────────────────────────────────────

def compute_all(
    assertions: list[Assertion],
    project_dir: Path,
    today_str: str,
) -> list[tuple[Assertion, float, list[str]]]:
    """Return (assertion, score, reasons) for every assertion without mutation.

    Dep activity is computed once and reused across all assertions (same repo).
    Score is not stored on Assertion — staleness is a derived, not persisted, value.
    """
    try:
        today = date.fromisoformat(today_str)
    except ValueError:
        today = date.today()

    dep_factor = _git_dep_activity(project_dir)
    results: list[tuple[Assertion, float, list[str]]] = []

    for a in assertions:
        ttl_days = _parse_ttl(a.ttl)
        try:
            verified = date.fromisoformat(a.last_verified)
        except ValueError:
            verified = today
        age_days = max(0, (today - verified).days)
        age_factor = min(1.0, age_days / ttl_days)

        specific_paths = [p for p in a.paths if p != "**"]
        path_activity = (
            _git_path_activity(project_dir, specific_paths)
            if specific_paths else 0.0
        )

        score = min(1.0, round(age_factor * 0.6 + path_activity * 0.25 + dep_factor * 0.15, 4))

        reasons: list[str] = []
        if age_factor >= 1.0:
            reasons.append("ttl_expired")
        elif age_factor >= 0.75:
            reasons.append("ttl_near_expiry")
        if path_activity >= 0.5:
            reasons.append("high_git_activity_on_covered_paths")
        if dep_factor >= 0.5:
            reasons.append("dependency_changes_detected")

        results.append((a, score, reasons))

    return results
