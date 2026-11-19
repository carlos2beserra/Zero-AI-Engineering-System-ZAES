#!/usr/bin/env python3
"""Zero-LLM architecture analysis — candidate extraction, collapse, node building.

Public API:
  build_candidates_from_paths(paths)         → list[ArchitectureCandidate]  (canonical)
  build_candidates(files)                    → list[ArchitectureCandidate]  (adapter)
  collapse_candidates(candidates, layer_map) → list[ArchitectureCandidate]
  candidates_to_nodes(candidates, layer_map, all_files) → list[ArchitectureNode]
  extract_entry_points(content)              → list[str]
  build_dependency_edges(nodes, files)       → dict[str, list[str]]
  infer_node_type(dir_name, layer_map)       → NodeType
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from .models import (
    ArchitectureCandidate,
    ArchitectureNode,
    CANONICAL_SOURCE_EXTENSIONS,
    IMPORT_PARSEABLE_EXTENSIONS,
    NODE_TYPE_ADAPTER,
    NODE_TYPE_CLI,
    NODE_TYPE_CONSUMER,
    NODE_TYPE_CONTROLLER,
    NODE_TYPE_DOMAIN,
    NODE_TYPE_FRONTEND,
    NODE_TYPE_GATEWAY,
    NODE_TYPE_INFRASTRUCTURE,
    NODE_TYPE_LAYER,
    NODE_TYPE_PRODUCER,
    NODE_TYPE_REPOSITORY,
    NODE_TYPE_SCHEDULER,
    NODE_TYPE_SERVICE,
    NODE_TYPE_WORKER,
    NodeType,
    _path_to_id,
)

# ─── Constants ────────────────────────────────────────────────────────────────

# Directories that are never modules (infrastructure, noise, generated)
_SKIP_DIRS = frozenset({
    "node_modules", ".git", ".maes", ".claude", "dist", "build", "__pycache__",
    ".next", "coverage", ".nyc_output", "vendor", "venv", ".venv",
    "target", "out", ".cache", ".turbo", "tmp", "temp", "logs",
    ".gradle", ".bundle", ".cargo", "bin", "obj", "migrations",
    "__tests__", "test", "tests", "spec", "specs", "fixtures", "mocks",
    "static", "assets", "public", "media", "images",
    "typings", "types", "__generated__", "generated",
})

# Layer-only directory names that should be collapsed into parent
_LAYER_DIR_NAMES = frozenset({
    "controllers", "controller", "services", "service",
    "repositories", "repository", "repos", "repo",
    "handlers", "handler", "resolvers", "resolver",
    "providers", "provider", "usecases", "usecase",
    "use_cases", "use_case", "interactors", "interactor",
    "presenters", "presenter", "serializers", "serializer",
    "validators", "validator", "schemas", "schema",
    "models", "entities", "entity", "domain",
    "middlewares", "middleware", "guards", "guard",
    "decorators", "decorator", "interceptors", "interceptor",
    "pipes", "filters", "exceptions", "errors",
    "helpers", "utils", "utilities", "shared", "common",
    "lib", "libs", "core", "base",
})

# Source file extensions to consider — ADR 0009: single canonical definition,
# imported (never redefined). A local copy here is what diverged from Stage 1.
_SOURCE_EXTS = CANONICAL_SOURCE_EXTENSIONS

# Thresholds for collapse rules
_COALESCE_UP_THRESHOLD = 3     # dirs with < N files coalesce up (if semantic_weight=0)
_SPLIT_DOWN_THRESHOLD  = 20    # dirs with > N files consider splitting


# ─── Entry-point extraction ───────────────────────────────────────────────────

_ENTRY_POINT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # Python FastAPI / Flask / Starlette
    (re.compile(r'@(?:app|router|blueprint)\.(get|post|put|patch|delete|options|head)\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE), "http"),
    (re.compile(r'@(?:app|router)\.(route)\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE), "http"),
    # TypeScript NestJS decorators
    (re.compile(r'@(?:Get|Post|Put|Patch|Delete|Options|Head)\s*\(\s*[\'"]([^\'"]*)[\'"]', re.IGNORECASE), "http_nest"),
    (re.compile(r'@Controller\s*\(\s*[\'"]([^\'"]*)[\'"]', re.IGNORECASE), "controller"),
    # Express / Fastify style
    (re.compile(r'(?:router|app|fastify)\.(get|post|put|patch|delete)\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE), "http"),
    # Queue / worker consumers
    (re.compile(r'@(?:Processor|Consumer|EventPattern|MessagePattern)\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE), "queue"),
    (re.compile(r'(?:queue|consumer|bus)\s*\.\s*(?:subscribe|listen|consume|process)\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE), "queue"),
    (re.compile(r'@app\.task\s*\(|@celery\.task\s*\(', re.IGNORECASE), "queue"),
    # Python worker / consumer decorators
    (re.compile(r'@(?:consumer|subscriber)\.(?:subscribe|listen)\s*\(\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE), "queue"),
]


def _format_entry_point(kind: str, groups: list[str]) -> str:
    """Format a single entry point string from regex match groups and kind."""
    if kind == "http":
        method = groups[0].upper() if len(groups) >= 2 else "GET"
        route  = groups[-1]
        return f"{method} {route}"
    if kind == "http_nest":
        route = groups[0] or "/"
        return f"HTTP /{route.lstrip('/')}"
    if kind == "controller":
        prefix = groups[0]
        return f"controller:{prefix}" if prefix else "controller"
    return f"queue:{groups[0]}"


def extract_entry_points(content: str) -> list[str]:
    """Extract entry points from file content via regex. Zero-LLM. Silent on failure."""
    results: list[str] = []
    seen: set[str] = set()

    for pattern, kind in _ENTRY_POINT_PATTERNS:
        for m in pattern.finditer(content):
            groups = [g for g in m.groups() if g]
            if not groups:
                continue
            ep = _format_entry_point(kind, groups)
            if ep not in seen:
                seen.add(ep)
                results.append(ep)

    return results[:10]  # cap to avoid noise


# ─── Frontend framework detection (zero-LLM, from DiscoveryResult.files) ─────

# config filename → canonical framework name (checked before package.json)
_CONFIG_FILE_TO_FRAMEWORK: dict[str, str] = {
    "next.config.js": "nextjs", "next.config.ts": "nextjs", "next.config.mjs": "nextjs",
    "nuxt.config.ts": "vue",    "nuxt.config.js": "vue",
    "angular.json":   "angular",
    "svelte.config.js": "svelte", "svelte.config.ts": "svelte",
    "vite.config.ts": "vite",   "vite.config.js": "vite",
}

# ordered list: first matching dep wins
_DEP_TO_FRAMEWORK: list[tuple[str, str]] = [
    ("next",           "nextjs"),
    ("nuxt",           "vue"),
    ("@nuxt/core",     "vue"),
    ("@angular/core",  "angular"),
    ("@sveltejs/kit",  "svelte"),
    ("svelte",         "svelte"),
    ("vue",            "vue"),
    ("react",          "react"),
    ("vite",           "vite"),
]


def _framework_from_package_json(content: str) -> str | None:
    """Return framework name from package.json content, or None."""
    import json as _json
    try:
        pkg = _json.loads(content)
        deps: set[str] = (
            set(pkg.get("dependencies", {}).keys())
            | set(pkg.get("devDependencies", {}).keys())
        )
        for dep, framework in _DEP_TO_FRAMEWORK:
            if dep in deps:
                return framework
    except (ValueError, AttributeError):
        pass
    return None


def _detect_frontend_framework(files: list[tuple[str, str]]) -> str | None:
    """Return framework name if project is frontend, else None. Zero-LLM.

    Matches on BASENAME, not full path: in a multirepo/monorepo workspace the
    manifest lives at apps/web/package.json, and exact-path matching made every
    such workspace report is_frontend_project=false regardless of its contents.

    Config files (next.config.*, angular.json, …) take priority over package.json
    dep scanning — so a config-only signal wins even if deps are ambiguous. Among
    competing manifests the first in the collection order wins, which is
    deterministic because the inventory is sorted.
    """
    normalized = [
        (rel.replace("\\", "/").lstrip("./").rsplit("/", 1)[-1], content)
        for rel, content in files
    ]
    # Pass 1 — config files. A single loop checking both per file would let a
    # package.json that happens to come first beat a config file, making the
    # documented priority depend on collection order.
    for basename in (b for b, _ in normalized):
        framework = _CONFIG_FILE_TO_FRAMEWORK.get(basename)
        if framework:
            return framework
    # Pass 2 — package.json dependency scanning.
    for basename, content in normalized:
        if basename == "package.json" and content:
            framework = _framework_from_package_json(content)
            if framework:
                return framework
    return None


def _tsx_jsx_ratio(candidate_files: list[str]) -> float:
    """Return fraction of .tsx/.jsx/.vue files among candidate_files."""
    if not candidate_files:
        return 0.0
    frontend_count = sum(
        1 for f in candidate_files
        if f.endswith((".tsx", ".jsx", ".vue"))
    )
    return frontend_count / len(candidate_files)


# ─── NodeType inference ───────────────────────────────────────────────────────

_TYPE_KEYWORDS: list[tuple[frozenset[str], NodeType]] = [
    (frozenset({"worker", "workers", "job", "jobs", "tasks", "task", "cron",
                "queue", "queues", "consumer", "consumers", "processor", "processors",
                "background", "async_task", "celery"}),
     NODE_TYPE_WORKER),
    (frozenset({"controller", "controllers", "handler", "handlers",
                "route", "routes", "router", "routers",
                "view", "views", "endpoint", "endpoints", "api", "rest"}),
     NODE_TYPE_CONTROLLER),
    (frozenset({"repository", "repositories", "repo", "repos",
                "store", "stores", "dao", "daos", "persistence", "database", "db"}),
     NODE_TYPE_REPOSITORY),
    (frozenset({"domain", "domains", "entity", "entities", "model", "models",
                "aggregate", "aggregates", "valueobject", "value_objects"}),
     NODE_TYPE_DOMAIN),
    (frozenset({"infrastructure", "infra", "external", "integration", "integrations",
                "adapter", "adapters", "provider", "providers", "client", "clients",
                "sdk", "third_party", "thirdparty", "vendor"}),
     NODE_TYPE_INFRASTRUCTURE),
    (frozenset({"gateway", "gateways", "proxy", "proxies", "bff", "facade", "facades"}),
     NODE_TYPE_GATEWAY),
    (frozenset({"scheduler", "schedulers", "cron", "crons", "timer", "timers"}),
     NODE_TYPE_SCHEDULER),
    (frozenset({"cli", "cmd", "command", "commands", "console"}),
     NODE_TYPE_CLI),
    (frozenset({"service", "services", "usecase", "usecases", "use_case", "use_cases",
                "interactor", "interactors", "application", "app"}),
     NODE_TYPE_SERVICE),
]


def infer_node_type(dir_name: str, layer_map: dict[str, str]) -> NodeType:
    """Infer NodeType from directory name and layer_map."""
    lower = dir_name.lower()
    for keywords, node_type in _TYPE_KEYWORDS:
        if lower in keywords or any(kw in lower for kw in keywords):
            return node_type
    # Fallback: check layer_map
    layer = layer_map.get(dir_name, layer_map.get(lower, ""))
    if "controller" in layer or "api" in layer or "presentation" in layer:
        return NODE_TYPE_CONTROLLER
    if "repository" in layer or "data" in layer:
        return NODE_TYPE_REPOSITORY
    if "infrastructure" in layer:
        return NODE_TYPE_INFRASTRUCTURE
    if "domain" in layer:
        return NODE_TYPE_DOMAIN
    return NODE_TYPE_SERVICE


# ─── Domain heuristic inference ───────────────────────────────────────────────

# Directory names that signal their children are domains (high confidence)
_DOMAIN_PARENT_DIRS = frozenset({
    "modules", "module", "domains", "domain", "contexts", "context",
    "features", "feature", "bounded_contexts", "packages", "apps",
    "services",  # at top-level: services/auth → domain = auth
})

# Directory names that reduce domain confidence (ambiguous)
_AMBIGUOUS_DIRS = frozenset({
    "shared", "common", "lib", "libs", "core", "utils",
    "helpers", "base", "internal", "_internal",
})


def _infer_domain(path: str) -> tuple[str, float]:
    """Heuristic domain inference from path. Returns (domain_name, confidence)."""
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    if not parts:
        return "general", 0.5

    # Check for canonical domain-parent directory pattern
    for i, part in enumerate(parts[:-1]):
        if part.lower() in _DOMAIN_PARENT_DIRS and i + 1 < len(parts):
            return parts[i + 1], 0.90

    # Top-level: src/{X} or app/{X}
    if len(parts) >= 2 and parts[0].lower() in {"src", "app", "lib"}:
        child = parts[1]
        if child.lower() in _AMBIGUOUS_DIRS:
            return child, 0.35
        return child, 0.75

    # Single-level or unknown
    leaf = parts[-1]
    if leaf.lower() in _AMBIGUOUS_DIRS:
        return leaf, 0.35
    return leaf, 0.50


# ─── Candidate building ───────────────────────────────────────────────────────

def _rel_dir(file_path: str) -> str:
    """Return the immediate parent directory of a file path (normalized)."""
    p = PurePosixPath(file_path.replace("\\", "/"))
    return str(p.parent) if str(p.parent) != "." else ""


def _normalize_path(p: str) -> str:
    return p.replace("\\", "/").rstrip("/")


def _should_skip_dir(parts: list[str]) -> bool:
    return any(seg in _SKIP_DIRS for seg in parts)


def _build_parent_child_maps(
    all_dirs: set[str],
) -> tuple[dict[str, str | None], dict[str, list[str]]]:
    """Build parent and children maps from a set of directory paths."""
    from collections import defaultdict

    children_map: dict[str, list[str]] = defaultdict(list)
    parent_map: dict[str, str | None] = {}

    for d in sorted(all_dirs):
        # Find closest ancestor in all_dirs
        parts = d.split("/")
        found_parent: str | None = None
        for i in range(len(parts) - 1, 0, -1):
            candidate_parent = "/".join(parts[:i])
            if candidate_parent in all_dirs:
                found_parent = candidate_parent
                break
        parent_map[d] = found_parent
        if found_parent:
            children_map[found_parent].append(d)

    return parent_map, children_map


def build_candidates(
    files: list[tuple[str, str]],
) -> list[ArchitectureCandidate]:
    """Adapter for callers holding (path, content) tuples.

    TEMPORARY — the canonical implementation is build_candidates_from_paths; no
    structural rule may live here. Remove once every consumer is migrated
    (follow-up F2 in the findings). Never maintain two implementations.
    """
    return build_candidates_from_paths([p for p, _ in files])


def build_candidates_from_paths(
    paths: list[str],
) -> list[ArchitectureCandidate]:
    """Group source paths by directory hierarchy to build the initial candidate set.

    CANONICAL implementation: topology derives from the population of paths alone —
    file content is irrelevant here, which is why the whole structure can be built
    from the inventory instead of the budget-capped content sample.

    Each directory containing at least one source file becomes a candidate.
    Directories in _SKIP_DIRS are excluded entirely.
    """
    from collections import defaultdict

    # Map: dir_path → list of file paths
    dir_files: dict[str, list[str]] = defaultdict(list)
    for file_path in paths:
        norm = _normalize_path(file_path)
        ext = PurePosixPath(norm).suffix.lower()
        if ext not in _SOURCE_EXTS:
            continue
        parts = norm.split("/")
        if _should_skip_dir(parts):
            continue
        parent = "/".join(parts[:-1]) if len(parts) > 1 else ""
        if parent:
            dir_files[parent].append(norm)

    # Build parent–child relationships
    all_dirs = set(dir_files.keys())
    parent_map, children_map = _build_parent_child_maps(all_dirs)

    candidates = []
    for d, files_in_dir in sorted(dir_files.items()):
        candidates.append(ArchitectureCandidate(
            path=d,
            files=sorted(files_in_dir),
            file_count=len(files_in_dir),
            parent=parent_map.get(d),
            children=sorted(children_map.get(d, [])),
            collapsed_from=[],
            collapse_reason=None,
            semantic_weight=0,
        ))

    return candidates


# ─── Semantic weight ──────────────────────────────────────────────────────────

def build_content_index(files: list[tuple[str, str]]) -> dict[str, str]:
    """Normalized path → content for the sampled files. Build once, pass around."""
    return {_normalize_path(p): c for p, c in files}


def _compute_semantic_weights(
    candidates: list[ArchitectureCandidate],
    files: list[tuple[str, str]],
    layer_map: dict[str, str],
    content_by_path: dict[str, str] | None = None,
) -> None:
    """Mutate candidates in-place to set semantic_weight."""
    if content_by_path is None:
        content_by_path = build_content_index(files)

    # Build fan-in map: file_path → count of other files that import it
    # (approximation: count how many files' content contains the dir name)
    dir_name_counts: dict[str, int] = {}
    all_content = " ".join(content_by_path.values())
    for cand in candidates:
        leaf = cand.path.rsplit("/", 1)[-1]
        dir_name_counts[cand.path] = all_content.count(leaf)

    for cand in candidates:
        weight = 0
        leaf = cand.path.rsplit("/", 1)[-1].lower()

        # Signal: has entry_points in any of its files
        for f in cand.files[:10]:
            content = content_by_path.get(f, "")
            if extract_entry_points(content):
                weight += 2
                break

        # Signal: imported by many other files (high fan-in approximation)
        if dir_name_counts.get(cand.path, 0) >= 3:
            weight += 2

        # Signal: name appears in layer_map as canonical layer
        if leaf in layer_map.values() or leaf + "s" in layer_map.values():
            weight += 1

        cand.semantic_weight = weight


# ─── Collapse ─────────────────────────────────────────────────────────────────

def _is_layer_group(candidate: ArchitectureCandidate) -> bool:
    """True if all children are layer-only dirs (controllers, services, repos, etc.)."""
    if not candidate.children:
        return False
    child_leaves = {c.rsplit("/", 1)[-1].lower() for c in candidate.children}
    return bool(child_leaves) and child_leaves.issubset(_LAYER_DIR_NAMES)


def _coalesce_up(
    candidates: list[ArchitectureCandidate],
    by_path: dict[str, ArchitectureCandidate],
    absorbed: set[str],
) -> None:
    """Pass 1 — merge tiny candidates without semantic weight into their parent."""
    for cand in sorted(candidates, key=lambda c: len(c.path.split("/")), reverse=True):
        if cand.path in absorbed or cand.semantic_weight > 0:
            continue
        if cand.file_count < _COALESCE_UP_THRESHOLD and cand.parent and cand.parent in by_path:
            parent = by_path[cand.parent]
            if parent.path not in absorbed:
                parent.files.extend(cand.files)
                parent.file_count += cand.file_count
                parent.collapsed_from.append(cand.path)
                parent.collapse_reason = parent.collapse_reason or "too_small"
                parent.children = [c for c in parent.children if c != cand.path]
                absorbed.add(cand.path)


def _flatten_layer_groups(
    candidates: list[ArchitectureCandidate],
    by_path: dict[str, ArchitectureCandidate],
    absorbed: set[str],
) -> None:
    """Pass 2 — flatten layer-only children into their parent."""
    for cand in candidates:
        if cand.path in absorbed or cand.semantic_weight > 0:
            continue
        if _is_layer_group(cand):
            for child_path in cand.children:
                child = by_path.get(child_path)
                if child and child.path not in absorbed:
                    cand.files.extend(child.files)
                    cand.file_count += child.file_count
                    cand.collapsed_from.append(child_path)
                    cand.collapse_reason = cand.collapse_reason or "layer_group"
                    absorbed.add(child_path)


def _split_down_candidates(
    candidates: list[ArchitectureCandidate],
    by_path: dict[str, ArchitectureCandidate],
    absorbed: set[str],
) -> list[ArchitectureCandidate]:
    """Pass 3 — promote qualifying children from large monolithic candidates."""
    result: list[ArchitectureCandidate] = []
    for cand in candidates:
        if cand.path in absorbed:
            continue
        qualifying_children = [
            ch for ch in cand.children
            if ch in by_path and ch not in absorbed
            and by_path[ch].semantic_weight > 0
            and by_path[ch].file_count >= 3
        ]
        if (cand.file_count > _SPLIT_DOWN_THRESHOLD
                and cand.semantic_weight == 0
                and qualifying_children):
            # Promote qualifying children; keep parent only if it has orphan files
            for ch in qualifying_children:
                child = by_path[ch]
                child.collapse_reason = child.collapse_reason or "split_down"
                # Remove from absorbed (they were never absorbed, but mark parent change)
                cand.collapsed_from.append(f"split:{ch}")
                cand.collapse_reason = cand.collapse_reason or "split_down"
            # Keep parent only if it still has files not in any qualifying child
            child_files = {f for ch in qualifying_children for f in by_path[ch].files}
            orphan_files = [f for f in cand.files if f not in child_files]
            if orphan_files:
                cand.files = orphan_files
                cand.file_count = len(orphan_files)
                result.append(cand)
            continue  # qualifying children added on their own pass

        result.append(cand)

    return result


def collapse_candidates(
    candidates: list[ArchitectureCandidate],
    layer_map: dict[str, str],
    files: list[tuple[str, str]] | None = None,
    content_by_path: dict[str, str] | None = None,
) -> list[ArchitectureCandidate]:
    """Apply collapse rules to reduce candidates to module-level granularity.

    Rules applied in order (only when semantic_weight == 0):
      1. Coalesce up:      file_count < threshold AND no semantic weight → merge into parent
      2. Flatten layers:   all children are layer-only dirs → collapse children into parent
      3. Split down:       file_count > threshold AND children have semantic weight → promote children

    Returns the final list of candidates that become ArchitectureNodes.
    """
    if files or content_by_path:
        _compute_semantic_weights(
            candidates, files or [], layer_map, content_by_path
        )
    by_path = {c.path: c for c in candidates}
    absorbed: set[str] = set()
    _coalesce_up(candidates, by_path, absorbed)
    _flatten_layer_groups(candidates, by_path, absorbed)
    return _split_down_candidates(candidates, by_path, absorbed)


# ─── Dependency map ───────────────────────────────────────────────────────────

def _extract_file_imports(content: str, ext: str) -> list[str]:
    """Write content to a temp file, extract imports, delete temp file, return list."""
    from pathlib import Path
    import tempfile
    import os
    from .dep_analysis import _extract_python_imports, _extract_ts_imports

    with tempfile.NamedTemporaryFile(mode="w", suffix=ext,
                                     delete=False, encoding="utf-8") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        if ext == ".py":
            return _extract_python_imports(Path(tmp_path))
        return _extract_ts_imports(Path(tmp_path))
    finally:
        os.unlink(tmp_path)


def _add_import_edges(
    imp: str,
    prefix_index: list[tuple[str, str]],
    src_key: str,
    edges: dict[str, list[str]],
) -> None:
    """Resolve a single import string to a node edge and add it to edges."""
    imp_norm = imp.replace(".", "/")
    for prefix, tgt_key in prefix_index:
        if prefix.endswith(imp_norm) or imp_norm in prefix:
            if tgt_key != src_key and tgt_key not in edges[src_key]:
                edges[src_key].append(tgt_key)
            break


def build_dependency_edges(
    nodes: list[ArchitectureNode],
    files: list[tuple[str, str]],
) -> dict[str, list[str]]:
    """Build stable_key → [stable_keys] dependency edges from import analysis.

    Reuses dep_analysis import extractors. Returns empty dict on any error.
    """
    try:
        import importlib
        importlib.import_module(".dep_analysis", package=__name__.rsplit(".", 1)[0])
    except ImportError:
        return {}

    # Build index: path_prefix → node stable_key (longest match wins)
    prefix_index: list[tuple[str, str]] = sorted(
        [(n.path, n.stable_key) for n in nodes],
        key=lambda x: len(x[0]),
        reverse=True,
    )

    def _resolve(file_path: str) -> str | None:
        norm = _normalize_path(file_path)
        for prefix, key in prefix_index:
            if norm.startswith(prefix):
                return key
        return None

    edges: dict[str, list[str]] = {n.stable_key: [] for n in nodes}

    for file_path, content in files:
        norm = _normalize_path(file_path)
        src_key = _resolve(norm)
        if src_key is None:
            continue

        ext = PurePosixPath(norm).suffix.lower()
        if ext not in IMPORT_PARSEABLE_EXTENSIONS:
            continue
        try:
            imported = _extract_file_imports(content, ext)
        except Exception:
            continue

        for imp in imported:
            _add_import_edges(imp, prefix_index, src_key, edges)

    return edges


# ─── Candidates → ArchitectureNodes ──────────────────────────────────────────

def _unique_entry_points(entry_points: list[str]) -> list[str]:
    """Deduplicate entry points, preserving insertion order."""
    seen: set[str] = set()
    result = []
    for ep in entry_points:
        if ep not in seen:
            seen.add(ep)
            result.append(ep)
    return result


def candidates_to_nodes(
    candidates: list[ArchitectureCandidate],
    layer_map: dict[str, str],
    all_files: list[tuple[str, str]],
    is_frontend_project: bool = False,
    content_by_path: dict[str, str] | None = None,
) -> list[ArchitectureNode]:
    """Convert final candidates into ArchitectureNode list.

    `content_by_path` may be passed in so it is built once per run instead of
    rebuilt identically here and in _compute_semantic_weights.
    """
    if content_by_path is None:
        content_by_path = build_content_index(all_files)
    nodes: list[ArchitectureNode] = []

    for cand in candidates:
        if not cand.path:
            continue
        leaf = cand.path.rsplit("/", 1)[-1]
        if is_frontend_project and _tsx_jsx_ratio(cand.files) >= 0.60:
            node_type: NodeType = NODE_TYPE_FRONTEND
        else:
            node_type = infer_node_type(leaf, layer_map)
        domain, domain_confidence = _infer_domain(cand.path)

        # Extract entry_points from files in this candidate
        entry_points: list[str] = []
        for f in cand.files[:15]:
            content = content_by_path.get(f, "")
            entry_points.extend(extract_entry_points(content))
            if len(entry_points) >= 10:
                break
        unique_eps = _unique_entry_points(entry_points)

        node_id = _path_to_id(cand.path)
        name = leaf
        nodes.append(ArchitectureNode(
            id=node_id,
            stable_key=node_id,
            name=name,
            path=cand.path,
            type=node_type,
            domain=domain,
            domain_confidence=round(max(0.0, min(1.0, domain_confidence)), 2),
            visibility="obvious",
            entry_points=unique_eps[:10],
            dependencies=[],  # filled by build_dependency_edges after node list is built
            file_count=cand.file_count,
            files_sampled=sum(1 for f in cand.files if f in content_by_path),
        ))

    return nodes
