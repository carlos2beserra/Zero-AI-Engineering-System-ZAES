"""maes inferred-to-canonical — format translation between agent output and compiler input.

Reads the five agent-produced files from context/inferred/ and writes the two
compiler-expected files (assertions.json, model.json) plus a structural report.

This command performs ONLY format translation. It never infers, enriches, classifies,
or creates information that is absent from the input files.

Invariants enforced here:
  I1 — If information is absent from input, it is absent from output (not invented).
  I2 — architecture_map.json is optional enrichment — absent = valid output, not error.
  I3 — --validate reports coverage; exits 1 only on compiler contract violations.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


# ─── File name constants ───────────────────────────────────────────────────────

_GAPS_FILE = "gaps.json"
_PATTERNS_FILE = "patterns.json"
_DATA_MODEL_FILE = "data-model.json"
_ARCH_MAP_FILE = "architecture_map.json"
_MODULES_FILE = "modules.json"
_STACK_FILE = "stack.json"

_ASSERTIONS_OUT = "assertions.json"
_MODEL_OUT = "model.json"
_REPORT_OUT = "canonicalization-report.json"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_json_file(path: Path) -> tuple[object, bool]:
    """Return (parsed_data, found). Returns (None, False) when file is absent."""
    if not path.exists():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def _read_arch_nodes(inferred_dir: Path) -> tuple[dict, ...] | None:
    """Read architecture_map.json nodes as plain dicts. Returns None when absent (I2)."""
    data, found = _load_json_file(inferred_dir / _ARCH_MAP_FILE)
    if not found or not isinstance(data, dict):
        return None
    nodes = tuple(
        n for n in data.get("nodes", [])
        if isinstance(n, dict) and n.get("path")
    )
    return nodes if nodes else None


def _read_arch_nodes_total(inferred_dir: Path) -> int:
    """Return total node count from architecture_map.json (structural fact, no filtering)."""
    data, found = _load_json_file(inferred_dir / _ARCH_MAP_FILE)
    if not found or not isinstance(data, dict):
        return 0
    nodes = data.get("nodes", [])
    return len(nodes) if isinstance(nodes, list) else 0


def _compute_unreferenced_nodes(arch_nodes: tuple | None, model: dict) -> list[str]:
    """Return arch node paths not referenced by any module path (exact match, slash-normalised).

    Purely structural observation — no semantic judgment.  The LLM or a human
    decides whether unreferenced nodes are significant; the framework only reports them.
    """
    if not arch_nodes:
        return []
    module_paths = {
        m["path"].rstrip("/")
        for m in model.get("modules", [])
        if isinstance(m, dict) and m.get("path")
    }
    return sorted(
        n["path"].rstrip("/")
        for n in arch_nodes
        if n.get("path") and n["path"].rstrip("/") not in module_paths
    )


def _validate_assertions_contract(assertions: list) -> list[str]:
    """Return list of structural violations against the compiler's contract."""
    errors = []
    for i, a in enumerate(assertions):
        d = a.to_dict() if hasattr(a, "to_dict") else a
        for field in ("id", "claim", "layer"):
            if not d.get(field):
                errors.append(f"assertion[{i}] missing required field '{field}'")
    return errors


def _warn_inferred_provenance(mode_label: str, assertions: list) -> None:
    """Provenance check (P0-A2b) for the inferred channel.

    Emits a WARNING — never an error — when an inferred assertion carries
    human/explicit provenance. Pilot policy: detect + warn, do not fail the
    pipeline. Post-pilot, promote these to ERROR and fail validation.
    """
    for a in assertions:
        d = a.to_dict() if hasattr(a, "to_dict") else a
        if d.get("confidence") == "explicit":
            print(
                f"{mode_label} WARNING: inferred assertion contains "
                f"confidence=explicit.",
                file=sys.stderr,
            )
        src = d.get("source", "")
        if isinstance(src, str) and src.startswith("human/"):
            print(
                f"{mode_label} WARNING: inferred assertion declares "
                f"source='{src}'.",
                file=sys.stderr,
            )


def _validate_model_contract(model: dict) -> list[str]:
    """Return list of structural violations against the compiler's model contract."""
    errors = []
    if "modules" not in model:
        errors.append("model.json missing required key 'modules'")
    return errors


# ─── Private orchestration helpers (extracted to keep S3776 ≤ 15) ─────────────


def _read_source_files(
    inferred_dir: Path,
) -> tuple[list[str], list[str], dict, list[dict], object]:
    """Read all agent-produced source files from inferred/.

    Returns (source_present, source_absent, analysis_dict, modules_raw, stack_data).
    All files are optional — absences are recorded in source_absent (I2).
    """
    source_present: list[str] = []
    source_absent: list[str] = []

    def _read(filename: str) -> tuple[object, bool]:
        data, found = _load_json_file(inferred_dir / filename)
        (source_present if found else source_absent).append(filename)
        return data, found

    gaps_data, _     = _read(_GAPS_FILE)
    patterns_data, _ = _read(_PATTERNS_FILE)
    dm_data, _       = _read(_DATA_MODEL_FILE)
    modules_data, _  = _read(_MODULES_FILE)
    stack_data, _    = _read(_STACK_FILE)

    analysis = _build_analysis(gaps_data, patterns_data, dm_data)
    modules_raw = _extract_modules_raw(modules_data)
    return source_present, source_absent, analysis, modules_raw, stack_data


def _build_analysis(gaps_data: object, patterns_data: object, dm_data: object) -> dict:
    """Assemble the analysis dict consumed by build_assertions."""
    analysis: dict = {}
    if isinstance(gaps_data, dict):
        analysis["gaps"] = gaps_data
    if isinstance(patterns_data, dict):
        analysis["code_patterns"] = patterns_data
    if isinstance(dm_data, dict):
        analysis["data_model"] = dm_data
    return analysis


def _extract_modules_raw(modules_data: object) -> list[dict]:
    """Safely extract the modules list from modules.json content."""
    if not isinstance(modules_data, dict):
        return []
    raw = modules_data.get("modules", [])
    return raw if isinstance(raw, list) else []


def _stack_categories(stack_data: object) -> list[str]:
    """Return the list of category keys the agent provided in stack.json."""
    if isinstance(stack_data, dict):
        return [k for k, v in stack_data.items() if isinstance(v, list)]
    return []


def _print_coverage_report(
    mode_label: str,
    source_present: list[str],
    source_absent: list[str],
    arch_nodes: tuple | None,
    assertions: list,
    coverage: dict,
    model: dict,
) -> None:
    """Print the human-readable coverage summary to stdout."""
    print(f"{mode_label} Source files present : {', '.join(source_present) or 'none'}")
    if source_absent:
        print(f"{mode_label} Source files absent  : {', '.join(source_absent)}")
    arch_msg = (
        f"{len(arch_nodes)} nodes (node_id enrichment active)"
        if arch_nodes
        else "absent (assertions will have no node_id)"
    )
    print(f"{mode_label} architecture_map     : {arch_msg}")
    print(f"{mode_label} Assertions generated : {len(assertions)}")
    print(f"{mode_label} Modules              : {coverage['total']}")
    print(f"{mode_label}   With domain        : {coverage['with_domain']}")
    print(f"{mode_label}   Without domain     : {coverage['without_domain']}")
    print(f"{mode_label} Domains derived      : {len(model['domains'])}")
    if coverage["without_domain"] > 0:
        print(
            f"{mode_label} NOTE: {coverage['without_domain']} module(s) have no 'domain' field. "
            "This is an agent quality signal — see canonicalization-report.json."
        )


def _print_contract_errors(mode_label: str, contract_errors: list[str]) -> None:
    """Print compiler contract violations to stderr."""
    print(f"\n{mode_label} CONTRACT VIOLATIONS:", file=sys.stderr)
    for err in contract_errors:
        print(f"  ✗ {err}", file=sys.stderr)


def _write_outputs(
    inferred_dir: Path,
    assertions: list,
    model: dict,
    coverage: dict,
    source_present: list[str],
    source_absent: list[str],
    stack_data: object,
    arch_nodes: tuple | None,
) -> None:
    """Write assertions.json, model.json, and canonicalization-report.json."""
    if assertions:
        (inferred_dir / _ASSERTIONS_OUT).write_text(
            json.dumps([a.to_dict() for a in assertions], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if model["modules"] or model["domains"]:
        # Translate None domain → "" for compiler compatibility.
        # The compiler does str(domain).strip() or "general"; None→str→"None" is wrong.
        # Empty string correctly triggers the "general" fallback in _parse_modules_from_data.
        compiler_model = {
            "modules": [
                {**m, "domain": m["domain"] if m["domain"] is not None else ""}
                for m in model["modules"]
            ],
            "domains": model["domains"],
        }
        (inferred_dir / _MODEL_OUT).write_text(
            json.dumps(compiler_model, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    report = {
        "generated": {
            "assertions": len(assertions),
            "modules": coverage["total"],
            "domains": len(model["domains"]),
            "unclassified_modules": coverage["without_domain"],
        },
        "source_files_present": source_present,
        "source_files_absent": source_absent,
        "stack_categories": _stack_categories(stack_data),
        "arch_nodes_used": len(arch_nodes) if arch_nodes else 0,
        "arch_nodes_total": _read_arch_nodes_total(inferred_dir),
        "structural_nodes_not_referenced_by_modules": _compute_unreferenced_nodes(arch_nodes, model),
    }
    (inferred_dir / _REPORT_OUT).write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─── Public entry point ───────────────────────────────────────────────────────

def run_inferred_to_canonical(
    maes_dir: Path,
    validate_only: bool = False,
) -> int:
    """Translate agent-produced inferred/ files into compiler-expected format.

    Parameters
    ----------
    maes_dir:
        Path to the .maes/ directory of the target project.
    validate_only:
        When True, runs all logic in memory, prints a coverage report, validates
        compiler contracts, and returns 0/1 — without writing any files.

    Returns
    -------
    int
        0 on success, 1 on structural contract violation.
    """
    from .canonicalization.assertions import build_assertions
    from .canonicalization.model import build_model, count_domain_coverage

    inferred_dir = maes_dir / "context" / "inferred"
    if not inferred_dir.exists():
        print(f"[inferred-to-canonical] context/inferred/ not found at {inferred_dir}", file=sys.stderr)
        print("[inferred-to-canonical] Invoke the /maes-analyze agent first.", file=sys.stderr)
        return 1

    source_present, source_absent, analysis, modules_raw, stack_data = _read_source_files(inferred_dir)
    arch_nodes = _read_arch_nodes(inferred_dir)

    assertions = build_assertions(analysis, arch_nodes)
    model = build_model(modules_raw)
    coverage = count_domain_coverage(model["modules"])

    mode_label = "[validate]" if validate_only else "[inferred-to-canonical]"
    _print_coverage_report(mode_label, source_present, source_absent, arch_nodes, assertions, coverage, model)

    contract_errors = _validate_assertions_contract(assertions) + _validate_model_contract(model)
    if contract_errors:
        _print_contract_errors(mode_label, contract_errors)
        return 1

    # Provenance guard (P0-A2b) — warn only, never fail the pipeline (pilot).
    _warn_inferred_provenance(mode_label, assertions)

    if validate_only:
        cats = _stack_categories(stack_data)
        print(f"{mode_label} Stack categories     : {', '.join(cats) or 'none'}")
        print(f"\n{mode_label} ✓ Compiler contracts satisfied — no files written (--validate mode)")
        return 0

    _write_outputs(inferred_dir, assertions, model, coverage, source_present, source_absent, stack_data, arch_nodes)
    print(f"{mode_label} ✓ Written: {_ASSERTIONS_OUT}, {_MODEL_OUT}, {_REPORT_OUT}")
    return 0
