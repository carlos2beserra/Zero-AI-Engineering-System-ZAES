#!/usr/bin/env python3
"""Zero-LLM static import analysis — Python AST + TypeScript regex layer violation detection."""

from __future__ import annotations

import ast
import re
from pathlib import Path

_IGNORED_DIRS = frozenset({
    "node_modules", ".git", "dist", "build", "__pycache__",
    ".next", "coverage", "venv", ".venv", "target", ".cache",
})

# ─── External module exclusion ────────────────────────────────────────────────
# These are never architectural layers — importing them is not a violation.

STDLIB_MODULES: frozenset[str] = frozenset({
    # builtins / runtime
    "os", "sys", "re", "json", "math", "typing", "uuid", "datetime", "enum",
    "collections", "pathlib", "abc", "dataclasses", "functools", "itertools",
    "logging", "time", "copy", "io", "hashlib", "base64", "traceback",
    "contextlib", "warnings", "inspect", "threading", "asyncio", "socket",
    "http", "urllib", "struct", "string", "textwrap", "shutil", "tempfile",
    "glob", "fnmatch", "pickle", "csv", "operator", "random", "secrets",
    "subprocess", "platform", "argparse", "configparser", "decimal", "fractions",
    "statistics", "heapq", "bisect", "array", "weakref", "types", "typing_extensions",
    "annotated_types", "zlib", "gzip", "zipfile", "tarfile", "sqlite3",
    "xml", "html", "cgi", "email", "smtplib", "ftplib", "imaplib",
    "unittest", "doctest", "pprint", "reprlib", "numbers", "cmath",
    "queue", "multiprocessing", "concurrent", "signal", "atexit",
})

FRAMEWORK_MODULES: frozenset[str] = frozenset({
    # Web / API
    "fastapi", "starlette", "uvicorn", "flask", "django", "aiohttp",
    # Data / ORM
    "pydantic", "sqlalchemy", "alembic", "sqlmodel", "tortoise",
    # Auth / Security
    "jose", "passlib", "cryptography", "bcrypt", "jwt",
    # AWS / Cloud
    "boto3", "botocore", "azure", "google",
    # AI / LLM
    "anthropic", "openai", "langchain", "transformers",
    # HTTP clients
    "httpx", "requests", "urllib3",
    # Queue / Cache
    "celery", "redis", "kombu", "pika",
    # Testing
    "pytest", "unittest", "mock", "hypothesis",
    # CLI
    "click", "typer", "argparse",
    # Serialization
    "marshmallow", "attrs", "cattrs",
    # Misc common
    "aiofiles", "anyio", "trio", "tenacity", "structlog",
    "prometheus_client", "sentry_sdk", "ddtrace",
})

# Union used for quick exclusion check in violation detection
_EXTERNAL_MODULES: frozenset[str] = STDLIB_MODULES | FRAMEWORK_MODULES

# Heuristic layer ordering: higher index = higher-level layer (closer to user)
_LAYER_ORDER = ["infrastructure", "data", "repository", "service", "domain",
                "usecase", "use_case", "controller", "api", "presentation", "ui", "web"]

_LAYER_SET = frozenset(_LAYER_ORDER)


def _in_ignored(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    return any(p in _IGNORED_DIRS for p in parts)


def _scan_one_level(root: Path, prefix: str = "") -> dict[str, str]:
    """Map immediate subdirectory names to layer labels (one level only)."""
    result: dict[str, str] = {}
    for p in sorted(root.iterdir()):
        if not p.is_dir() or p.name.startswith(".") or p.name in _IGNORED_DIRS:
            continue
        key = f"{prefix}{p.name}" if prefix else p.name
        name_lower = p.name.lower()
        for layer in _LAYER_ORDER:
            if layer in name_lower:
                result[key] = layer
                break
        else:
            result[key] = p.name
    return result


def _add_segment_compat(layer_map: dict[str, str]) -> dict[str, str]:
    """Add segment-level keys (without prefix) so _classify_path_layer() can
    match individual path segments like 'api' in addition to 'app/api'."""
    result = dict(layer_map)
    for full_key, layer_val in layer_map.items():
        segment = full_key.split("/")[-1]
        if segment not in result:
            result[segment] = layer_val
    return result


def _is_canonical_layer_dir(dir_name: str) -> bool:
    """True when dir_name is an unambiguous layer directory.

    Accepts names that ARE the layer keyword (exact) or its simple plural (+ "s").
    Rejects compound names like "my_service_utils" or "infrastructure_helpers"
    that contain a layer keyword as a substring but are not themselves layer dirs.

    Examples:
      "api"        → True   (exact match)
      "services"   → True   (service + "s")
      "domain"     → True   (exact match)
      "my_services" → False  (compound — too many components)
      "infrastructure_helpers" → False (compound)
    """
    name = dir_name.lower()
    for layer in _LAYER_ORDER:
        if name == layer or name == layer + "s":
            return True
    return False


def _infer_layer_map(project_dir: Path) -> dict[str, str]:
    """Scan directory hierarchy to map folder names to layer labels.

    First tries top-level directories. If fewer than 2 CANONICAL layer directories
    are found (unambiguous matches only — not compound names), scans one level deeper
    to detect the actual layer structure (e.g. app/api, app/services, app/domain).

    The canonical-match threshold prevents compound directory names like
    "my_service_utils" or "infrastructure_helpers" from triggering an early return
    and masking real layer directories nested inside a single source root.
    """
    top = _scan_one_level(project_dir)
    named = {k: v for k, v in top.items() if v in _LAYER_SET}
    # Only count canonical (unambiguous) layer dirs for the threshold
    canonical = {k: v for k, v in named.items() if _is_canonical_layer_dir(k.split("/")[-1])}
    if len(canonical) >= 2:
        return top

    # Second pass: look one level deeper for nested layer structure
    for top_dir in sorted(project_dir.iterdir()):
        if not top_dir.is_dir() or top_dir.name.startswith(".") or top_dir.name in _IGNORED_DIRS:
            continue
        sub = _scan_one_level(top_dir, prefix=f"{top_dir.name}/")
        sub_named = {k: v for k, v in sub.items() if v in _LAYER_SET}
        if len(sub_named) >= 2:
            return _add_segment_compat(sub)

    return top


def _classify_path_layer(file_rel: str, layer_map: dict[str, str]) -> str:
    parts = file_rel.replace("\\", "/").split("/")
    # Walk all segments (excluding filename) to find a meaningful layer match.
    # Avoids misclassifying files in `src/controllers/` as layer "src".
    for part in parts[:-1]:
        if part in layer_map:
            return layer_map[part]
        lower = part.lower()
        for layer in _LAYER_ORDER:
            if layer in lower:
                return layer
    return layer_map.get(parts[0], parts[0])


def _layer_index(layer: str) -> int:
    lower = layer.lower()
    for i, l in enumerate(_LAYER_ORDER):
        if l in lower:
            return i
    return -1


def _is_downward_violation(file_layer: str, imported_layer: str) -> bool:
    """True if `file_layer` (higher-level) imports directly from `imported_layer` (lower-level)
    skipping intermediate layers. Only flags violations for known layer pairs."""
    fi = _layer_index(file_layer)
    ii = _layer_index(imported_layer)
    if fi < 0 or ii < 0:
        return False
    # Higher-level (larger index) importing lower-level is allowed (normal direction)
    # Lower-level importing higher-level is always wrong
    if ii > fi:
        return True
    # UI/presentation importing infrastructure directly (skipping service) is a violation
    if fi >= _layer_index("controller") and ii <= _layer_index("infrastructure"):
        gap = fi - ii
        return gap >= 2
    return False


def _module_key(dotted: str) -> str:
    """Return 'first/second' when >=2 parts, else 'first'.

    Using two parts enables layer resolution for monorepo projects where all
    code lives under a single namespace (e.g. 'app.services.X' → 'app/services').
    """
    parts = dotted.split(".")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def _resolve_import_layer(imp: str, layer_map: dict[str, str]) -> str:
    """Resolve an import specifier to a layer label.

    Tries: full key ('app/services'), then second segment ('services'),
    then first segment ('app'). Falls back to the raw specifier (unknown layer).
    """
    if imp in layer_map:
        return layer_map[imp]
    if "/" in imp:
        second = imp.split("/")[1]
        if second in layer_map:
            return layer_map[second]
        first = imp.split("/")[0]
        if first in layer_map:
            return layer_map[first]
    return imp


def _extract_python_imports(path: Path) -> list[str]:
    """Return import specifiers as 'first/second' (>=2 parts) or 'first' (1 part)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(_module_key(node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(_module_key(alias.name))
    return imports


_TS_IMPORT_RE = re.compile(
    r"""(?:import|from|require)\s*[\(\s]*['"]([^'"]+)['"]"""
)


def _extract_ts_imports(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    imports: list[str] = []
    for m in _TS_IMPORT_RE.finditer(text):
        spec = m.group(1)
        # Only relative imports reveal layer relationships
        if spec.startswith("."):
            # normalize: ../../infrastructure/db → infrastructure
            parts = [p for p in spec.replace("\\", "/").split("/") if p and p != ".." and p != "."]
            if parts:
                imports.append(parts[0])
    return imports


def _violations_for_file(
    path: Path,
    project_dir: Path,
    layer_map: dict[str, str],
    ext: str,
) -> list[dict]:
    rel = str(path.relative_to(project_dir)).replace("\\", "/")
    file_layer = _classify_path_layer(rel, layer_map)

    if ext == ".py":
        imported_names = _extract_python_imports(path)
    else:
        imported_names = _extract_ts_imports(path)

    violations = []
    seen: set[str] = set()
    for imp in imported_names:
        # Skip stdlib and framework imports — not architectural layers
        if imp.split("/")[0] in _EXTERNAL_MODULES:
            continue
        imp_layer = _resolve_import_layer(imp, layer_map)
        key = f"{file_layer}→{imp_layer}"
        if key in seen:
            continue
        seen.add(key)
        if _is_downward_violation(file_layer, imp_layer):
            violations.append({
                "type": "layer-violation",
                "file": rel,
                "imported": imp,
                "description": f"{file_layer} importando {imp_layer} diretamente",
                "do_not_replicate": True,
            })
    return violations


def analyze_imports(project_dir: Path, layer_map: dict[str, str] | None = None) -> dict:
    """Detect import-level layer violations. Returns violations + boundary_map.

    Zero LLM. Uses Python AST for .py files and regex for .ts/.js files.
    Returns {} silently when no source files are found.
    """
    if layer_map is None:
        layer_map = _infer_layer_map(project_dir)

    violations: list[dict] = []
    # Capability subset (ADR 0009): languages whose imports we can extract.
    # Derived from the canonical source definition — never a local literal.
    from .models import IMPORT_PARSEABLE_EXTENSIONS as _SUPPORTED

    for path in sorted(project_dir.rglob("*")):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext not in _SUPPORTED:
            continue
        rel = str(path.relative_to(project_dir)).replace("\\", "/")
        if _in_ignored(rel):
            continue
        violations.extend(_violations_for_file(path, project_dir, layer_map, ext))

    return {
        "layer_violations": violations[:50],  # cap to avoid noise
        "boundary_map": layer_map,
    }
