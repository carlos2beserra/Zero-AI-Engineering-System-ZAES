"""Canonical assertion builder — converts agent analysis dicts to Assertion objects.

This module is the authoritative transformation layer between raw agent output
(gaps.json, patterns.json, data-model.json) and the compiler's assertions.json.

Invariant (I1): if information is absent from the input, it is not created here.
Invariant (I2): arch_nodes is optional — absence means assertions are generated
                without node_id enrichment, which is valid compiler input.
"""
from __future__ import annotations

import re
from datetime import date

_STRIP_PREFIXES = re.compile(
    r"^\[(ERRO PROV[ÁA]VEL|ERRO PROBABLE|WARNING|WARN|INFERRED|INFER[IÊ]DO)\]\s*",
    re.IGNORECASE,
)

_INFERRED_SOURCE = "context/inferred/assertions.json"

# Mapping: gaps section → (confidence, layer)
_GAPS_SECTIONS = (
    ("ai_likely_mistakes",      "inferred-high",   7),
    ("behavior_contracts",      "inferred-high",   5),
    ("constraints",             "inferred-high",   4),
    ("warning_antipatterns",    "inferred-medium", 7),
    ("business_rules_inferred", "inferred-medium", 5),
)


def _clean_claim(text: str) -> str:
    return _STRIP_PREFIXES.sub("", text.strip())


def _claim_from(item: object) -> str:
    if isinstance(item, str):
        return _clean_claim(item)
    if isinstance(item, dict):
        raw = item.get("description", item.get("claim", str(item)))
        return _clean_claim(str(raw))
    return _clean_claim(str(item))


def _gaps_item_extras(
    section: str, item: object
) -> tuple[str, list[dict], list[str]]:
    """Return (claim_prefix, code_examples, paths) for a single gaps section item."""
    claim_prefix = ""
    code_examples: list[dict] = []
    paths: list[str] = []
    if not isinstance(item, dict):
        return claim_prefix, code_examples, paths
    if section == "ai_likely_mistakes":
        if item.get("code_wrong") or item.get("code_correct"):
            code_examples.append({
                "wrong": item.get("code_wrong", ""),
                "correct": item.get("code_correct", ""),
                "file": item.get("file_reference", ""),
            })
        if item.get("file_reference"):
            paths = [item["file_reference"]]
    elif section == "warning_antipatterns":
        claim_prefix = "ANTIPADRÃO existente — não replicar: "
        if item.get("file"):
            paths = [item["file"]]
    return claim_prefix, code_examples, paths


def _resolve_node_id(
    file_ref: str, arch_nodes: tuple[dict, ...]
) -> str | None:
    """Return stable_key of the node whose path is the longest prefix of file_ref."""
    if not file_ref or not arch_nodes:
        return None
    normalized = file_ref.replace("\\", "/").split(":")[0]
    for node in sorted(arch_nodes, key=lambda n: len(n.get("path", "")), reverse=True):
        node_path = node.get("path", "")
        if node_path and (
            normalized.startswith(node_path + "/") or normalized == node_path
        ):
            return node.get("stable_key")
    return None


def _localize_mistake(
    item: object,
    arch_nodes: tuple[dict, ...] | None,
) -> tuple[str | None, str | None, str]:
    """Return (evidence, node_id, scope_type) for an ai_likely_mistakes item."""
    if not isinstance(item, dict):
        return None, None, "global"
    file_ref = item.get("file_reference", "")
    if not file_ref:
        return None, None, "global"
    node_id = _resolve_node_id(file_ref, arch_nodes) if arch_nodes else None
    scope_type = "module" if node_id else "global"
    return file_ref, node_id, scope_type


def _assertions_from_gaps(
    analysis: dict,
    today: str,
    arch_nodes: tuple[dict, ...] | None = None,
) -> list:
    from ..models import Assertion
    from ..compiler import _classify_type, _extract_paths

    result = []
    for section, confidence, layer in _GAPS_SECTIONS:
        items = analysis.get("gaps", {}).get(section, [])
        if not isinstance(items, list):
            continue
        for item in items:
            claim = _claim_from(item).strip()
            if not claim or len(claim) < 10:
                continue
            prefix, code_examples, paths = _gaps_item_extras(section, item)
            claim = prefix + claim
            atype = _classify_type(claim)

            if section == "ai_likely_mistakes":
                evidence, node_id, scope_type = _localize_mistake(item, arch_nodes)
            else:
                evidence, node_id, scope_type = None, None, "global"

            result.append(Assertion(
                id=Assertion.make_id(claim),
                claim=claim,
                type=atype,
                layer=layer,
                subject=None,
                paths=paths or _extract_paths(claim),
                confidence=confidence,
                source=_INFERRED_SOURCE,
                ttl="90d",
                last_verified=today,
                owner="",
                code_examples=code_examples,
                evidence=evidence,
                node_id=node_id,
                scope_type=scope_type,
            ))
    return result


def _assertions_from_code_patterns(analysis: dict, today: str) -> list:
    from ..models import Assertion

    result = []
    code_patterns = analysis.get("code_patterns", {})
    if not isinstance(code_patterns, dict):
        return result
    for item in code_patterns.get("notable_patterns", []):
        claim = _clean_claim(
            item.get("description", str(item)) if isinstance(item, dict) else str(item)
        ).strip()
        if not claim:
            continue
        result.append(Assertion(
            id=Assertion.make_id(claim),
            claim=claim,
            type="PATTERN",
            layer=7,
            subject=None,
            paths=[],
            confidence="inferred-medium",
            source=_INFERRED_SOURCE,
            ttl="90d",
            last_verified=today,
            owner="",
        ))
    for item in code_patterns.get("naming_conventions", []):
        claim = _clean_claim(_claim_from(item)).strip()
        if not claim:
            continue
        result.append(Assertion(
            id=Assertion.make_id(claim),
            claim=claim,
            type="PATTERN",
            layer=7,
            subject=None,
            paths=[],
            confidence="inferred-medium",
            source=_INFERRED_SOURCE,
            ttl="90d",
            last_verified=today,
            owner="",
        ))
    return result


def _assertions_from_data_model(analysis: dict, today: str) -> list:
    from ..models import Assertion

    result = []
    data_model = analysis.get("data_model", {})
    if not isinstance(data_model, dict):
        return result
    for field_info in data_model.get("special_fields", []):
        if not isinstance(field_info, dict):
            continue
        name = field_info.get("name", "")
        note = field_info.get("note", field_info.get("behavior", ""))
        if not (name and note):
            continue
        claim = f"Campo {name}: {note}"
        result.append(Assertion(
            id=Assertion.make_id(claim),
            claim=claim,
            type="CONSTRAINT",
            layer=5,
            subject=None,
            paths=[],
            confidence="inferred-high",
            source=_INFERRED_SOURCE,
            ttl="90d",
            last_verified=today,
            owner="",
        ))
    return result


def build_assertions(
    analysis: dict,
    arch_nodes: tuple[dict, ...] | None = None,
) -> list:
    """Convert an analysis dict into canonical Assertion objects.

    Parameters
    ----------
    analysis:
        Dict with keys ``gaps``, ``code_patterns``, ``data_model`` — each
        corresponding to the contents of gaps.json, patterns.json, data-model.json.
    arch_nodes:
        Optional tuple of raw node dicts from architecture_map.json. When provided,
        assertions for ai_likely_mistakes gain node_id for warm-context relevance
        scoring. When absent, assertions are still valid — node_id is simply omitted.

    Returns
    -------
    list[Assertion]
        Canonical assertion objects ready for serialisation to assertions.json.
    """
    today = date.today().isoformat()
    return (
        _assertions_from_gaps(analysis, today, arch_nodes=arch_nodes)
        + _assertions_from_code_patterns(analysis, today)
        + _assertions_from_data_model(analysis, today)
    )
