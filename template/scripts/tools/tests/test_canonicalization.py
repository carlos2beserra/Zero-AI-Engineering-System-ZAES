"""Tests for the maes.canonicalization package.

Coverage:
  - canonicalization/model.py      — build_model, count_domain_coverage
  - canonicalization/assertions.py — build_assertions and section helpers
  - canonicalization/stack_signal.py — build_stack_signal
  - inferred_canonical_cmd.py      — run_inferred_to_canonical (integration)

Design contract validated by these tests:
  I1  Framework never invents information absent from agent input.
  I2  architecture_map.json is optional — absent means valid output, not error.
  I3  --validate reports coverage; exits 1 ONLY on structural contract violations.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maes.canonicalization.model import build_model, count_domain_coverage
from maes.canonicalization.assertions import build_assertions
from maes.canonicalization.stack_signal import build_stack_signal


# ═══════════════════════════════════════════════════════════════════════════════
# build_model — domain preservation and null handling (I1)
# ═══════════════════════════════════════════════════════════════════════════════


def test_build_model_preserves_agent_domain():
    """Agent-provided domain is passed through to output unchanged."""
    modules = [{"name": "InvoiceModule", "domain": "billing", "path": "src/billing"}]
    result = build_model(modules)
    assert result["modules"][0]["domain"] == "billing"


def test_build_model_preserves_project_specific_domain_vocabulary():
    """Framework does not rename or normalise project-specific domain names."""
    modules = [
        {"name": "CatalogService", "domain": "product-catalog"},
        {"name": "IdentityService", "domain": "identity_platform"},
    ]
    result = build_model(modules)
    domains_out = {m["domain"] for m in result["modules"]}
    assert "product-catalog" in domains_out
    assert "identity_platform" in domains_out


def test_build_model_null_domain_when_absent():
    """Absent domain field is preserved as null — framework does NOT invent a value.

    Specifically rejected values: 'general', 'backend', 'core', 'pipeline',
    or any keyword-derived string. The module is unclassified; that is an agent
    quality signal, not a framework responsibility.
    """
    modules = [{"name": "UnknownModule", "path": "src/unknown"}]
    result = build_model(modules)
    domain_val = result["modules"][0]["domain"]

    assert domain_val is None, (
        f"Expected null domain for absent field, got {domain_val!r}. "
        "Framework must not invent domain values."
    )

    # Guard: explicitly reject the most common false positives
    for forbidden in ("general", "backend", "core", "pipeline", "frontend"):
        assert domain_val != forbidden


def test_build_model_null_domain_excluded_from_domains_list():
    """Modules with null domain must not create entries in the domains list."""
    modules = [
        {"name": "InvoiceModule", "domain": "billing"},
        {"name": "UnknownModule"},          # no domain — must not appear in domains
    ]
    result = build_model(modules)
    domain_names = [d["name"] for d in result["domains"]]
    assert "billing" in domain_names
    assert len(domain_names) == 1           # only billing, not a phantom domain


def test_build_model_domains_derived_only_from_agent_field():
    """Domains list is built exclusively from agent-provided domain values."""
    modules = [
        {"name": "PaymentService",  "domain": "payments", "path": "src/payments"},
        {"name": "RefundService",   "domain": "payments", "path": "src/refunds"},
        {"name": "InventoryService","domain": "stock",    "path": "src/inventory"},
    ]
    result = build_model(modules)
    domain_names = {d["name"] for d in result["domains"]}
    assert domain_names == {"payments", "stock"}

    payments_domain = next(d for d in result["domains"] if d["name"] == "payments")
    assert set(payments_domain["modules"]) == {"PaymentService", "RefundService"}


def test_build_model_paths_normalized_from_singular_path_field():
    """path (singular) is normalised to paths (list) when paths is absent."""
    modules = [{"name": "AuthModule", "domain": "identity", "path": "src/auth"}]
    result = build_model(modules)
    assert result["modules"][0]["paths"] == ["src/auth"]


def test_build_model_paths_plural_takes_precedence_over_singular():
    modules = [
        {"name": "AuthModule", "domain": "identity",
         "paths": ["src/auth", "src/session"], "path": "src/auth"}
    ]
    result = build_model(modules)
    assert result["modules"][0]["paths"] == ["src/auth", "src/session"]


def test_build_model_skips_entries_without_name():
    """Invalid entries (no name, non-dict) are skipped silently."""
    modules = [
        None,
        "just a string",
        {},
        {"domain": "billing"},             # missing name
        {"name": "Valid", "domain": "ok"},
    ]
    result = build_model(modules)
    assert len(result["modules"]) == 1
    assert result["modules"][0]["name"] == "Valid"


def test_build_model_returns_modules_and_domains_keys():
    result = build_model([])
    assert "modules" in result
    assert "domains" in result
    assert result["modules"] == []
    assert result["domains"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# count_domain_coverage — observability helper
# ═══════════════════════════════════════════════════════════════════════════════


def test_count_domain_coverage_correct_counts():
    modules = [
        {"name": "A", "domain": "billing"},
        {"name": "B", "domain": "identity"},
        {"name": "C", "domain": None},
        {"name": "D"},                      # domain key absent → treated as None
    ]
    cov = count_domain_coverage(modules)
    assert cov["total"] == 4
    assert cov["with_domain"] == 2
    assert cov["without_domain"] == 2


def test_count_domain_coverage_all_classified():
    modules = [{"name": "A", "domain": "x"}, {"name": "B", "domain": "y"}]
    cov = count_domain_coverage(modules)
    assert cov["with_domain"] == 2
    assert cov["without_domain"] == 0


def test_count_domain_coverage_none_classified():
    modules = [{"name": "A"}, {"name": "B"}]
    cov = count_domain_coverage(modules)
    assert cov["with_domain"] == 0
    assert cov["without_domain"] == 2


def test_count_domain_coverage_empty_list():
    cov = count_domain_coverage([])
    assert cov == {"total": 0, "with_domain": 0, "without_domain": 0}


# ═══════════════════════════════════════════════════════════════════════════════
# build_assertions — gaps section → layer / confidence mapping
# ═══════════════════════════════════════════════════════════════════════════════


def _make_analysis(*, section: str, items: list) -> dict:
    return {"gaps": {section: items}}


_SECTION_EXPECTATIONS = [
    # (section, expected_confidence, expected_layer)
    ("ai_likely_mistakes",      "inferred-high",   7),
    ("behavior_contracts",      "inferred-high",   5),
    ("constraints",             "inferred-high",   4),
    ("warning_antipatterns",    "inferred-medium", 7),
    ("business_rules_inferred", "inferred-medium", 5),
]


@pytest.mark.parametrize("section,expected_confidence,expected_layer", _SECTION_EXPECTATIONS)
def test_build_assertions_layer_and_confidence_per_section(
    section, expected_confidence, expected_layer
):
    """Each gaps section maps to the correct layer and confidence value."""
    claim_text = f"This is a test assertion for {section} section validation"
    analysis = _make_analysis(section=section, items=[claim_text])
    assertions = build_assertions(analysis)
    assert len(assertions) >= 1, f"Expected at least 1 assertion from {section}"
    a = assertions[0].to_dict()
    assert a["layer"] == expected_layer, f"{section}: expected layer {expected_layer}, got {a['layer']}"
    assert a["confidence"] == expected_confidence, (
        f"{section}: expected confidence {expected_confidence!r}, got {a['confidence']!r}"
    )


def test_build_assertions_claim_is_preserved():
    """The claim text from the agent is preserved (after stripping prefix markers)."""
    analysis = _make_analysis(
        section="behavior_contracts",
        items=["All write operations must be idempotent"],
    )
    assertions = build_assertions(analysis)
    assert any("idempotent" in a.to_dict()["claim"] for a in assertions)


def test_build_assertions_strips_prefix_markers():
    """[ERRO PROVÁVEL] and similar LLM-generated prefixes are stripped from claims."""
    analysis = _make_analysis(
        section="ai_likely_mistakes",
        items=[{"description": "[ERRO PROVÁVEL] Missing null check before accessing user.email"}],
    )
    assertions = build_assertions(analysis)
    claim = assertions[0].to_dict()["claim"]
    assert not claim.startswith("[ERRO")
    assert "null check" in claim


def test_build_assertions_skips_claims_shorter_than_threshold():
    """Claims shorter than 10 characters are skipped — they carry no useful signal."""
    analysis = _make_analysis(section="behavior_contracts", items=["ok", "short"])
    assertions = build_assertions(analysis)
    assert assertions == []


def test_build_assertions_dict_item_uses_description_field():
    """Dict items use 'description' as the claim source."""
    analysis = _make_analysis(
        section="behavior_contracts",
        items=[{"description": "The payment service must validate amounts before processing"}],
    )
    assertions = build_assertions(analysis)
    assert len(assertions) == 1
    assert "validate amounts" in assertions[0].to_dict()["claim"]


def test_build_assertions_antipattern_prepends_prefix():
    """warning_antipatterns dict items include the ANTIPADRÃO prefix.

    The prefix is applied only to structured (dict) items, where _gaps_item_extras
    can detect the section type. Plain string items are treated as-is.
    """
    analysis = _make_analysis(
        section="warning_antipatterns",
        items=[{"description": "Using raw SQL strings without parameterisation across all repositories"}],
    )
    assertions = build_assertions(analysis)
    claim = assertions[0].to_dict()["claim"]
    assert "ANTIPADRÃO" in claim


def test_build_assertions_from_code_patterns():
    """notable_patterns → PATTERN type, layer 7, inferred-medium."""
    analysis = {
        "code_patterns": {
            "notable_patterns": [
                {"description": "All controllers use constructor injection for dependency resolution"}
            ]
        }
    }
    assertions = build_assertions(analysis)
    assert len(assertions) == 1
    a = assertions[0].to_dict()
    assert a["type"] == "PATTERN"
    assert a["layer"] == 7
    assert a["confidence"] == "inferred-medium"
    assert "constructor injection" in a["claim"]


def test_build_assertions_naming_conventions_are_patterns():
    """naming_conventions also produce PATTERN assertions."""
    analysis = {
        "code_patterns": {
            "naming_conventions": [
                "Services are suffixed with Service (e.g. PaymentService, UserService)"
            ]
        }
    }
    assertions = build_assertions(analysis)
    assert len(assertions) == 1
    a = assertions[0].to_dict()
    assert a["type"] == "PATTERN"
    assert "suffixed" in a["claim"]


def test_build_assertions_from_data_model_special_fields():
    """special_fields → CONSTRAINT type, layer 5, inferred-high."""
    analysis = {
        "data_model": {
            "special_fields": [
                {"name": "deleted_at", "note": "Soft delete marker — never truly removed"}
            ]
        }
    }
    assertions = build_assertions(analysis)
    assert len(assertions) == 1
    a = assertions[0].to_dict()
    assert a["type"] == "CONSTRAINT"
    assert a["layer"] == 5
    assert a["confidence"] == "inferred-high"
    assert "deleted_at" in a["claim"]


def test_build_assertions_empty_analysis_returns_empty():
    """Empty analysis dict produces no assertions without raising."""
    assert build_assertions({}) == []


def test_build_assertions_missing_gaps_key_is_safe():
    """Missing sections are handled gracefully."""
    analysis = {"code_patterns": {}, "data_model": {}}
    result = build_assertions(analysis)
    assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════════
# build_assertions — arch_nodes enrichment (I2)
# ═══════════════════════════════════════════════════════════════════════════════


def test_build_assertions_receives_arch_nodes_and_populates_node_id():
    """When arch_nodes is provided, ai_likely_mistakes assertions get node_id (I2).

    The stable_key of the arch node whose path is a prefix of the file_reference
    is assigned to the assertion's node_id field.
    """
    analysis = {
        "gaps": {
            "ai_likely_mistakes": [
                {
                    "description": "Missing input validation on registration endpoint",
                    "file_reference": "src/auth/auth.service.py",
                }
            ]
        }
    }
    arch_nodes = (
        {"stable_key": "src_auth", "path": "src/auth"},
        {"stable_key": "src_payments", "path": "src/payments"},
    )
    assertions = build_assertions(analysis, arch_nodes=arch_nodes)
    assert len(assertions) == 1
    assert assertions[0].to_dict()["node_id"] == "src_auth"


def test_build_assertions_without_architecture_map_still_generates():
    """When arch_nodes is absent (I2), assertions are generated without node_id.

    This is correct behaviour — the presence of architecture_map.json only
    adds warm-context enrichment; it is never required for valid output.
    """
    analysis = {
        "gaps": {
            "ai_likely_mistakes": [
                {
                    "description": "Missing null check before accessing user.email field",
                    "file_reference": "src/auth/auth.service.py",
                }
            ]
        }
    }
    # No arch_nodes argument (defaults to None)
    assertions = build_assertions(analysis)
    assert len(assertions) == 1
    a = assertions[0].to_dict()
    assert "null check" in a["claim"]
    # node_id must be absent or null — not a fabricated string
    assert a.get("node_id") is None


def test_build_assertions_arch_nodes_longest_prefix_wins():
    """When multiple arch nodes match, the one with the longest path wins."""
    analysis = {
        "gaps": {
            "ai_likely_mistakes": [
                {
                    "description": "Rate limiter is not applied to the admin auth endpoint",
                    "file_reference": "src/auth/admin/admin.service.py",
                }
            ]
        }
    }
    arch_nodes = (
        {"stable_key": "src",           "path": "src"},
        {"stable_key": "src_auth",      "path": "src/auth"},
        {"stable_key": "src_auth_admin","path": "src/auth/admin"},
    )
    assertions = build_assertions(analysis, arch_nodes=arch_nodes)
    assert assertions[0].to_dict()["node_id"] == "src_auth_admin"


def test_build_assertions_arch_nodes_no_match_gives_null_node_id():
    """When no arch node path is a prefix of the file_reference, node_id is null."""
    analysis = {
        "gaps": {
            "ai_likely_mistakes": [
                {
                    "description": "Unhandled exception in payment confirmation handler",
                    "file_reference": "src/payments/payment.service.py",
                }
            ]
        }
    }
    arch_nodes = (
        {"stable_key": "src_auth", "path": "src/auth"},
    )
    assertions = build_assertions(analysis, arch_nodes=arch_nodes)
    assert assertions[0].to_dict()["node_id"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# build_stack_signal — pure pass-through (I1)
# ═══════════════════════════════════════════════════════════════════════════════


def test_build_stack_signal_pass_through():
    """Agent category names are preserved exactly — no renaming or filtering."""
    stack = {
        "rendering": ["vulkan", "wgpu"],
        "physics": ["bullet"],
        "audio": [],
    }
    result = build_stack_signal(stack)
    assert result == {"rendering": True, "physics": True, "audio": False}


def test_build_stack_signal_preserves_project_specific_categories():
    """Framework does not rename agent-defined categories to a fixed taxonomy.

    Specifically rejected: mapping 'ui_framework' → 'frontend', 'db' → 'persistence',
    'ml_libs' → 'data_engineering', or any other fixed capability name.
    """
    stack = {
        "ui_framework": ["react"],
        "ml_libs": ["torch"],
        "job_queues": ["celery"],
    }
    result = build_stack_signal(stack)
    assert set(result.keys()) == {"ui_framework", "ml_libs", "job_queues"}
    # Explicitly assert no fixed taxonomy leakage
    for forbidden in ("frontend", "backend", "data_engineering", "mobile", "security"):
        assert forbidden not in result


def test_build_stack_signal_non_list_values_skipped():
    """Non-list values (string, bool, null, int) are excluded from the output (I1).

    Only explicit list entries represent 'the agent declared this category'.
    """
    stack = {
        "rendering": ["vulkan"],
        "version": "1.0",          # non-list → excluded
        "enabled": True,           # non-list → excluded
        "count": 42,               # non-list → excluded
        "notes": None,             # non-list → excluded
    }
    result = build_stack_signal(stack)
    assert set(result.keys()) == {"rendering"}


def test_build_stack_signal_empty_dict_returns_empty():
    assert build_stack_signal({}) == {}


def test_build_stack_signal_all_empty_lists():
    """All empty lists → all False — no implicit removal."""
    stack = {"a": [], "b": [], "c": []}
    result = build_stack_signal(stack)
    assert result == {"a": False, "b": False, "c": False}


# ═══════════════════════════════════════════════════════════════════════════════
# run_inferred_to_canonical — integration tests
# ═══════════════════════════════════════════════════════════════════════════════


def _make_maes_dir(tmp_path: Path, *, with_arch_map: bool = False) -> Path:
    """Create a minimal .maes/ directory with agent-produced fixture files."""
    maes = tmp_path / ".maes"
    inferred = maes / "context" / "inferred"
    inferred.mkdir(parents=True)

    gaps = {
        "ai_likely_mistakes": [
            {"description": "Missing input validation before processing payment amount",
             "file_reference": "src/payments/payment.service.py"},
        ],
        "behavior_contracts": [
            "All API endpoints must return structured error responses",
        ],
    }
    patterns = {
        "notable_patterns": [
            {"description": "Repository pattern used consistently across data access layers"}
        ],
        "naming_conventions": [],
    }
    modules = {
        "modules": [
            {"name": "PaymentModule",  "domain": "payments",  "path": "src/payments"},
            {"name": "UnknownModule",                          "path": "src/unknown"},
        ]
    }

    (inferred / "gaps.json").write_text(json.dumps(gaps), encoding="utf-8")
    (inferred / "patterns.json").write_text(json.dumps(patterns), encoding="utf-8")
    (inferred / "modules.json").write_text(json.dumps(modules), encoding="utf-8")

    if with_arch_map:
        arch = {
            "nodes": [
                {"id": "src_payments", "stable_key": "src_payments",
                 "name": "payments", "path": "src/payments", "type": "Service"},
            ]
        }
        (inferred / "architecture_map.json").write_text(json.dumps(arch), encoding="utf-8")

    return maes


def test_validate_mode_no_writes(tmp_path):
    """--validate mode must not write any files to disk (I3).

    Even when input is valid, assertions.json, model.json, and
    canonicalization-report.json must NOT be created.
    """
    from maes.inferred_canonical_cmd import run_inferred_to_canonical

    maes = _make_maes_dir(tmp_path)
    inferred = maes / "context" / "inferred"

    rc = run_inferred_to_canonical(maes, validate_only=True)

    assert rc == 0
    assert not (inferred / "assertions.json").exists(), "assertions.json must not be written in --validate"
    assert not (inferred / "model.json").exists(), "model.json must not be written in --validate"
    assert not (inferred / "canonicalization-report.json").exists(), "report must not be written in --validate"


def test_validate_mode_returns_0_on_valid_input(tmp_path):
    """--validate returns exit code 0 when no compiler contract is violated (I3)."""
    from maes.inferred_canonical_cmd import run_inferred_to_canonical

    maes = _make_maes_dir(tmp_path)
    rc = run_inferred_to_canonical(maes, validate_only=True)
    assert rc == 0


def test_inferred_to_canonical_writes_three_files(tmp_path):
    """Write mode produces assertions.json, model.json, and canonicalization-report.json."""
    from maes.inferred_canonical_cmd import run_inferred_to_canonical

    maes = _make_maes_dir(tmp_path)
    inferred = maes / "context" / "inferred"

    rc = run_inferred_to_canonical(maes, validate_only=False)

    assert rc == 0
    assert (inferred / "assertions.json").exists()
    assert (inferred / "model.json").exists()
    assert (inferred / "canonicalization-report.json").exists()


def test_inferred_to_canonical_assertions_are_valid_json(tmp_path):
    """Written assertions.json is valid JSON containing a list of assertion dicts."""
    from maes.inferred_canonical_cmd import run_inferred_to_canonical

    maes = _make_maes_dir(tmp_path)
    inferred = maes / "context" / "inferred"
    run_inferred_to_canonical(maes, validate_only=False)

    data = json.loads((inferred / "assertions.json").read_text())
    assert isinstance(data, list)
    assert len(data) >= 1
    # Each assertion must have the required compiler fields
    for a in data:
        assert "id" in a
        assert "claim" in a
        assert "layer" in a


def test_inferred_to_canonical_model_json_domains_are_strings(tmp_path):
    """model.json must write domain as empty string (not null) for absent domain.

    The compiler does str(domain).strip() or 'general'. Writing null would
    produce 'None' (the string), which would NOT fall back to 'general'.
    """
    from maes.inferred_canonical_cmd import run_inferred_to_canonical

    maes = _make_maes_dir(tmp_path)
    inferred = maes / "context" / "inferred"
    run_inferred_to_canonical(maes, validate_only=False)

    data = json.loads((inferred / "model.json").read_text())
    for m in data["modules"]:
        assert isinstance(m["domain"], str), (
            f"domain must be a string in model.json (compiler compat), got {m['domain']!r}"
        )
        assert m["domain"] != "None", "JSON null → str(None) = 'None' is a known bug — must write '' instead"


def test_inferred_to_canonical_with_arch_nodes_populates_node_id(tmp_path):
    """When architecture_map.json is present, ai_likely_mistakes assertions get node_id."""
    from maes.inferred_canonical_cmd import run_inferred_to_canonical

    maes = _make_maes_dir(tmp_path, with_arch_map=True)
    inferred = maes / "context" / "inferred"
    run_inferred_to_canonical(maes, validate_only=False)

    assertions = json.loads((inferred / "assertions.json").read_text())
    # The mistake for src/payments/payment.service.py should match the src_payments node
    mistakes = [a for a in assertions if "payment" in a.get("claim", "").lower()]
    assert len(mistakes) >= 1
    assert mistakes[0]["node_id"] == "src_payments"


def test_inferred_to_canonical_without_architecture_map_succeeds(tmp_path):
    """When architecture_map.json is absent, command exits 0 and writes valid files (I2)."""
    from maes.inferred_canonical_cmd import run_inferred_to_canonical

    maes = _make_maes_dir(tmp_path, with_arch_map=False)
    inferred = maes / "context" / "inferred"

    # Confirm no arch map
    assert not (inferred / "architecture_map.json").exists()

    rc = run_inferred_to_canonical(maes, validate_only=False)
    assert rc == 0

    assertions = json.loads((inferred / "assertions.json").read_text())
    assert len(assertions) >= 1
    # node_id must be null when arch map is absent — not a fabricated value
    for a in assertions:
        if a.get("node_id") is not None:
            # A node_id may be non-null only if a file_reference matched something
            # but without arch nodes, there's nothing to match against
            pytest.fail(f"Unexpected node_id without arch map: {a['node_id']!r}")


def test_inferred_to_canonical_missing_inferred_dir_returns_1(tmp_path):
    """When context/inferred/ does not exist, command exits 1 with an error message."""
    from maes.inferred_canonical_cmd import run_inferred_to_canonical

    maes = tmp_path / ".maes"
    maes.mkdir()
    # Do NOT create context/inferred/

    rc = run_inferred_to_canonical(maes, validate_only=False)
    assert rc == 1


def test_inferred_to_canonical_report_structure(tmp_path):
    """canonicalization-report.json has the expected keys."""
    from maes.inferred_canonical_cmd import run_inferred_to_canonical

    maes = _make_maes_dir(tmp_path)
    inferred = maes / "context" / "inferred"
    run_inferred_to_canonical(maes, validate_only=False)

    report = json.loads((inferred / "canonicalization-report.json").read_text())
    assert "generated" in report
    assert "source_files_present" in report
    assert "source_files_absent" in report
    assert "arch_nodes_used" in report

    gen = report["generated"]
    assert "assertions" in gen
    assert "modules" in gen
    assert "domains" in gen
    assert "unclassified_modules" in gen
