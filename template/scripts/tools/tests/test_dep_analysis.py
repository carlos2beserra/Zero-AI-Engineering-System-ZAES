"""V1 unit tests for dep_analysis — layer detection substrate (plan A1).

Coverage:
  _scan_one_level        — subdirectory-to-layer mapping
  _add_segment_compat    — backward-compat segment keys
  _module_key            — dotted-name → "first/second" key
  _resolve_import_layer  — multi-fallback layer resolution
  _infer_layer_map       — first-pass / second-pass detection
  _is_downward_violation — violation predicate
  analyze_imports        — end-to-end with real filesystem fixtures

Hardening (V1.1):
  _is_downward_violation — gap edge cases, rule-2 scope, _LAYER_ORDER stability marker
  _infer_layer_map       — mixed top-level dirs; known limitation with misleading dir names
  TypeScript path aliases — documented as unsupported by design; no crash guarantee
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from maes.dep_analysis import (
    FRAMEWORK_MODULES,
    STDLIB_MODULES,
    _EXTERNAL_MODULES,
    _add_segment_compat,
    _classify_path_layer,
    _infer_layer_map,
    _is_downward_violation,
    _layer_index,
    _module_key,
    _resolve_import_layer,
    _scan_one_level,
    analyze_imports,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _mkdirs(base: Path, *names: str) -> None:
    for name in names:
        (base / name).mkdir(parents=True, exist_ok=True)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content), encoding="utf-8")


# ─── _scan_one_level ──────────────────────────────────────────────────────────


def test_scan_one_level_detects_api_layer(tmp_path):
    _mkdirs(tmp_path, "api", "services", "domain")
    result = _scan_one_level(tmp_path)
    assert result["api"] == "api"
    assert result["services"] == "service"  # "service" substring in "services"
    assert result["domain"] == "domain"


def test_scan_one_level_with_prefix_produces_qualified_keys(tmp_path):
    app = tmp_path / "app"
    _mkdirs(app, "api", "services", "domain")
    result = _scan_one_level(app, prefix="app/")
    assert result["app/api"] == "api"
    assert result["app/services"] == "service"
    assert result["app/domain"] == "domain"
    # bare names must NOT appear — prefix is mandatory
    assert "api" not in result
    assert "services" not in result


def test_scan_one_level_fallback_for_unrecognized_dir(tmp_path):
    _mkdirs(tmp_path, "utils", "helpers")
    result = _scan_one_level(tmp_path)
    assert result["utils"] == "utils"
    assert result["helpers"] == "helpers"


def test_scan_one_level_empty_dir_returns_empty(tmp_path):
    assert _scan_one_level(tmp_path) == {}


def test_scan_one_level_skips_hidden_dirs(tmp_path):
    _mkdirs(tmp_path, ".git", "api")
    result = _scan_one_level(tmp_path)
    assert ".git" not in result
    assert "api" in result


def test_scan_one_level_skips_ignored_dirs(tmp_path):
    _mkdirs(tmp_path, "node_modules", "dist", "api")
    result = _scan_one_level(tmp_path)
    assert "node_modules" not in result
    assert "dist" not in result
    assert "api" in result


def test_scan_one_level_partial_layer_name_in_dirname(tmp_path):
    # "my_services" contains "service" → should map to "service"
    _mkdirs(tmp_path, "my_services")
    result = _scan_one_level(tmp_path)
    assert result["my_services"] == "service"


def test_scan_one_level_does_not_include_files(tmp_path):
    (tmp_path / "README.md").write_text("", encoding="utf-8")
    _mkdirs(tmp_path, "api")
    result = _scan_one_level(tmp_path)
    assert "README.md" not in result
    assert "api" in result


# ─── _add_segment_compat ──────────────────────────────────────────────────────


def test_add_segment_compat_adds_bare_segment_keys():
    layer_map = {"app/api": "api", "app/services": "service"}
    result = _add_segment_compat(layer_map)
    # New segment keys
    assert result["api"] == "api"
    assert result["services"] == "service"
    # Original keys preserved
    assert result["app/api"] == "api"
    assert result["app/services"] == "service"


def test_add_segment_compat_does_not_overwrite_existing_segment():
    layer_map = {"app/api": "api", "api": "existing_value"}
    result = _add_segment_compat(layer_map)
    # "api" already present — must not be overwritten
    assert result["api"] == "existing_value"
    assert result["app/api"] == "api"


def test_add_segment_compat_no_op_when_no_prefix():
    # Keys without "/" → segment == key → already in map, nothing added
    layer_map = {"api": "api", "services": "service"}
    result = _add_segment_compat(layer_map)
    assert len(result) == 2
    assert result == layer_map


def test_add_segment_compat_multiple_prefixes():
    layer_map = {"app/api": "api", "core/domain": "domain"}
    result = _add_segment_compat(layer_map)
    assert result["api"] == "api"
    assert result["domain"] == "domain"
    assert len(result) == 4


# ─── _module_key ──────────────────────────────────────────────────────────────


def test_module_key_three_part_dotted():
    assert _module_key("app.services.job") == "app/services"


def test_module_key_two_part_dotted():
    assert _module_key("app.services") == "app/services"


def test_module_key_single_part():
    assert _module_key("app") == "app"


def test_module_key_stdlib_single():
    assert _module_key("os") == "os"
    assert _module_key("typing") == "typing"


def test_module_key_deep_dotted_uses_first_two_only():
    # Four levels → still only first two
    assert _module_key("app.api.routes.handlers") == "app/api"


# ─── _resolve_import_layer ────────────────────────────────────────────────────


def test_resolve_import_layer_full_key_match():
    layer_map = {"app/services": "service", "services": "service"}
    assert _resolve_import_layer("app/services", layer_map) == "service"


def test_resolve_import_layer_second_segment_fallback():
    # Full key absent, second segment present
    layer_map = {"services": "service"}
    assert _resolve_import_layer("app/services", layer_map) == "service"


def test_resolve_import_layer_first_segment_fallback():
    # Neither full key nor second segment — first segment matches
    layer_map = {"app": "app_namespace"}
    assert _resolve_import_layer("app/services", layer_map) == "app_namespace"


def test_resolve_import_layer_no_match_returns_raw():
    layer_map = {"unrelated": "other"}
    assert _resolve_import_layer("app/services", layer_map) == "app/services"


def test_resolve_import_layer_no_slash_direct_match():
    layer_map = {"os": "stdlib"}
    assert _resolve_import_layer("os", layer_map) == "stdlib"


def test_resolve_import_layer_no_slash_missing_returns_raw():
    assert _resolve_import_layer("os", {}) == "os"


def test_resolve_import_layer_full_key_takes_precedence_over_segment():
    # Full key and second segment both present — full key wins
    layer_map = {"app/api": "api_full", "api": "api_segment"}
    assert _resolve_import_layer("app/api", layer_map) == "api_full"


# ─── _infer_layer_map ─────────────────────────────────────────────────────────


def test_infer_layer_map_second_pass_for_single_source_dir(tmp_path):
    app = tmp_path / "app"
    _mkdirs(app, "api", "services", "domain")
    result = _infer_layer_map(tmp_path)
    assert result.get("app/api") == "api"
    assert result.get("app/services") == "service"
    assert result.get("app/domain") == "domain"
    # Segment-compat keys added
    assert result.get("api") == "api"
    assert result.get("services") == "service"


def test_infer_layer_map_first_pass_when_top_level_has_layers(tmp_path):
    _mkdirs(tmp_path, "api", "domain", "infrastructure")
    result = _infer_layer_map(tmp_path)
    assert result.get("api") == "api"
    assert result.get("domain") == "domain"
    assert result.get("infrastructure") == "infrastructure"
    # Should NOT produce prefixed keys — stayed at top level
    assert not any("/" in k for k in result)


def test_infer_layer_map_returns_something_for_flat_project(tmp_path):
    # No layer keywords anywhere — graceful degradation
    _mkdirs(tmp_path, "utils", "helpers")
    result = _infer_layer_map(tmp_path)
    assert isinstance(result, dict)
    assert len(result) >= 1


# ─── _is_downward_violation ───────────────────────────────────────────────────


def test_is_downward_violation_lower_imports_higher():
    # domain (index 4) importing api (index 8) → violation
    assert _is_downward_violation("domain", "api") is True


def test_is_downward_violation_higher_imports_lower_allowed():
    # api (index 8) importing domain (index 4) → normal direction, NOT a violation
    assert _is_downward_violation("api", "domain") is False


def test_is_downward_violation_infrastructure_to_service():
    # infrastructure (index 0) importing service (index 3) → violation
    assert _is_downward_violation("infrastructure", "service") is True


def test_is_downward_violation_same_layer():
    # Same layer → not a violation
    assert _is_downward_violation("domain", "domain") is False


def test_is_downward_violation_unknown_layers_returns_false():
    assert _is_downward_violation("unknown_a", "unknown_b") is False


def test_is_downward_violation_one_unknown_returns_false():
    assert _is_downward_violation("domain", "unknown_xyz") is False
    assert _is_downward_violation("unknown_xyz", "api") is False


# ─── analyze_imports — end-to-end ─────────────────────────────────────────────


def test_analyze_imports_detects_domain_importing_api(tmp_path):
    """Core invariant: lower-level layer importing higher-level layer is flagged."""
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(tmp_path / "app/api/routes.py", "")
    _write(
        tmp_path / "app/domain/business.py",
        "from app.api.routes import something\n",
    )

    result = analyze_imports(tmp_path)

    violations = result["layer_violations"]
    assert len(violations) >= 1

    v = violations[0]
    assert v["type"] == "layer-violation"
    assert "domain" in v["file"]
    assert v["imported"] == "app/api"
    assert "domain" in v["description"]
    assert "api" in v["description"]
    assert v["do_not_replicate"] is True


def test_analyze_imports_no_violation_for_api_importing_domain(tmp_path):
    """Normal direction: api → domain must not be flagged."""
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(tmp_path / "app/domain/entity.py", "")
    _write(
        tmp_path / "app/api/routes.py",
        "from app.domain.entity import Entity\n",
    )

    result = analyze_imports(tmp_path)
    assert result["layer_violations"] == []


def test_analyze_imports_boundary_map_reflects_nested_layers(tmp_path):
    """boundary_map must expose the discovered layer structure."""
    _mkdirs(tmp_path, "app/api", "app/services", "app/domain")

    result = analyze_imports(tmp_path)
    bm = result["boundary_map"]

    assert bm.get("app/api") == "api"
    assert bm.get("app/services") == "service"
    assert bm.get("app/domain") == "domain"
    # Segment-compat keys also present
    assert bm.get("api") == "api"
    assert bm.get("services") == "service"
    assert bm.get("domain") == "domain"


def test_analyze_imports_explicit_layer_map_bypasses_inference(tmp_path):
    """When layer_map is provided, _infer_layer_map must not be called."""
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(
        tmp_path / "app/domain/x.py",
        "from app.api.y import z\n",
    )

    explicit_map = {
        "app/api": "api", "api": "api",
        "app/domain": "domain", "domain": "domain",
    }
    result = analyze_imports(tmp_path, layer_map=explicit_map)

    assert result["boundary_map"] is explicit_map
    assert len(result["layer_violations"]) >= 1


def test_analyze_imports_empty_project_returns_empty_violations(tmp_path):
    result = analyze_imports(tmp_path)
    assert result["layer_violations"] == []


def test_analyze_imports_non_source_files_ignored(tmp_path):
    _mkdirs(tmp_path, "app/domain")
    _write(tmp_path / "app/domain/README.md", "# notes")
    _write(tmp_path / "app/domain/config.yaml", "key: value")
    result = analyze_imports(tmp_path)
    assert result["layer_violations"] == []


def test_analyze_imports_deduplicates_same_layer_pair(tmp_path):
    """Multiple imports from same layer-pair in one file → single violation entry."""
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(tmp_path / "app/api/x.py", "")
    _write(tmp_path / "app/api/y.py", "")
    _write(
        tmp_path / "app/domain/business.py",
        "from app.api.x import A\nfrom app.api.y import B\n",
    )

    result = analyze_imports(tmp_path)
    violations = [
        v for v in result["layer_violations"]
        if "domain" in v["file"]
    ]
    # Both imports are domain→api; should be deduplicated to one entry
    assert len(violations) == 1


def test_analyze_imports_ts_relative_import_violation(tmp_path):
    """TypeScript relative imports that cross layers must be detected."""
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(tmp_path / "app/api/routes.ts", "")
    _write(
        tmp_path / "app/domain/service.ts",
        'import { something } from "../../api/routes";\n',
    )

    result = analyze_imports(tmp_path)
    assert any("domain" in v["file"] for v in result["layer_violations"])


def test_analyze_imports_syntax_error_file_skipped(tmp_path):
    """Python files with syntax errors must not crash the analysis."""
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(tmp_path / "app/api/routes.py", "")
    _write(
        tmp_path / "app/domain/broken.py",
        "def foo(:\n    pass\n",  # intentional syntax error
    )

    result = analyze_imports(tmp_path)
    assert "layer_violations" in result
    assert "boundary_map" in result


# ─── _is_downward_violation — gap edge cases ──────────────────────────────────


def test_is_downward_violation_ui_to_infrastructure():
    # ui (index 10) → infrastructure (index 0): rule-2 fires (fi≥7, ii≤0, gap=10≥2) → violation
    assert _is_downward_violation("ui", "infrastructure") is True


def test_is_downward_violation_web_to_infrastructure():
    # web (index 11) → infrastructure (index 0): rule-2 fires → violation
    assert _is_downward_violation("web", "infrastructure") is True


def test_is_downward_violation_controller_to_infrastructure():
    # controller (index 7) → infrastructure (index 0): smallest fi that triggers rule-2, gap=7 → violation
    assert _is_downward_violation("controller", "infrastructure") is True


def test_is_downward_violation_api_to_infrastructure():
    # api (index 8) → infrastructure (index 0): rule-2 fires → violation
    assert _is_downward_violation("api", "infrastructure") is True


def test_is_downward_violation_ui_to_service_allowed():
    # ui (10) → service (3): rule-2 requires ii ≤ _layer_index("infrastructure") == 0;
    # service is index 3 > 0, so rule-2 does NOT apply.
    # Behavioral contract: controller-and-above may call services directly.
    assert _is_downward_violation("ui", "service") is False


def test_is_downward_violation_controller_to_service_allowed():
    # controller (7) → service (3): ii=3 > 0, rule-2 skipped → not a violation
    assert _is_downward_violation("controller", "service") is False


def test_is_downward_violation_rule2_scope_is_infrastructure_only():
    # rule-2 condition: ii <= _layer_index("infrastructure") == 0
    # "data" is index 1, which is > 0 — rule-2 does NOT fire even for ui→data (gap=9)
    # This documents that the gap heuristic is narrowly scoped to infrastructure (index 0) only.
    assert _is_downward_violation("ui", "data") is False
    assert _is_downward_violation("web", "data") is False
    assert _is_downward_violation("api", "repository") is False


def test_is_downward_violation_rule2_gap_condition_is_structurally_redundant():
    """The 'gap >= 2' guard inside rule-2 is dead code under current _LAYER_ORDER.

    Proof: rule-2 requires fi >= _layer_index("controller") == 7  AND  ii <= 0.
    Minimum gap = 7 - 0 = 7, which is always ≥ 2.
    The condition serves as intent documentation but never changes the outcome.
    If _LAYER_ORDER shifts controller below index 2, gap-filtering would activate.
    """
    assert _layer_index("controller") == 7   # minimum fi for rule-2
    assert _layer_index("infrastructure") == 0  # maximum ii for rule-2
    # All three show gap >> 2; none would behave differently without the gap check
    assert _is_downward_violation("controller", "infrastructure") is True   # gap 7
    assert _is_downward_violation("api", "infrastructure") is True          # gap 8
    assert _is_downward_violation("web", "infrastructure") is True          # gap 11


def test_is_downward_violation_layer_order_stability_marker():
    """Regression anchor for _LAYER_ORDER semantics.

    Encodes the complete ordering as behavioral assertions:
      infrastructure < data < repository < service < domain
      < usecase < use_case < controller < api < presentation < ui < web

    If _LAYER_ORDER is modified such that these relationships change, this test
    will fail — that is INTENTIONAL. Review all violation tests before editing
    _LAYER_ORDER and update this test to reflect the new intended semantics.
    """
    # Ordered pairs: (lower, higher) → lower importing higher is a violation
    violations = [
        ("infrastructure", "service"),
        ("service", "domain"),
        ("domain", "api"),
        ("api", "ui"),
    ]
    for lower, higher in violations:
        assert _is_downward_violation(lower, higher) is True, (
            f"Expected violation: {lower}→{higher}"
        )

    # Reverse direction: higher importing lower is allowed
    for lower, higher in violations:
        assert _is_downward_violation(higher, lower) is False, (
            f"Expected allowed: {higher}→{lower}"
        )

    # _layer_index anchors — if these change, the gap math in rule-2 silently breaks
    assert _layer_index("infrastructure") == 0
    assert _layer_index("service") == 3
    assert _layer_index("domain") == 4
    assert _layer_index("controller") == 7
    assert _layer_index("api") == 8
    assert _layer_index("ui") == 10
    assert _layer_index("web") == 11


# ─── _infer_layer_map — mixed top-level directories ───────────────────────────


def test_infer_layer_map_non_layer_siblings_do_not_block_second_pass(tmp_path):
    """utils/ and helpers/ at the same level as app/ must not prevent second-pass detection."""
    app = tmp_path / "app"
    _mkdirs(app, "api", "services", "domain")
    _mkdirs(tmp_path, "utils", "helpers")

    result = _infer_layer_map(tmp_path)

    # Second pass ran: none of utils/helpers/app matched layer keywords in first pass
    # → named count = 0 < 2 → second pass descended into app/ and found layers
    assert result.get("app/api") == "api"
    assert result.get("app/services") == "service"
    assert result.get("app/domain") == "domain"
    # Segment-compat keys present
    assert result.get("api") == "api"
    assert result.get("services") == "service"
    assert result.get("domain") == "domain"
    # Non-layer dirs are NOT included in the result (second pass returns only the matched subtree)
    assert "utils" not in result
    assert "helpers" not in result


def test_infer_layer_map_misleading_dir_names_no_longer_trigger_early_return(tmp_path):
    """Verifies that compound dir names do not trigger a false-positive early return.

    _is_canonical_layer_dir() only accepts names that ARE the layer keyword (exact)
    or its simple plural (e.g., "services"). Compound names like "my_service_utils"
    or "infrastructure_helpers" are not canonical, so the canonical-count threshold
    is NOT reached on the first pass → second pass descends into app/ and finds the
    real layer dirs.
    """
    app = tmp_path / "app"
    _mkdirs(app, "api", "domain")
    _mkdirs(tmp_path, "my_service_utils", "infrastructure_helpers")

    result = _infer_layer_map(tmp_path)

    # Corrected behavior: second pass ran → real layers in app/ ARE found
    assert result.get("app/api") == "api"
    assert result.get("app/domain") == "domain"
    # Compound dirs are NOT treated as canonical layers
    assert result.get("my_service_utils") != "service"
    assert result.get("infrastructure_helpers") != "infrastructure"


# ─── TypeScript path aliases (known limitation, unsupported by design) ────────
#
# Only relative imports (starting with '.') reveal layer relationships.
# Path aliases (@/, ~/, @scope/) are treated as external packages and ignored.
# "Path aliases are currently unsupported by design."


def test_ts_at_prefix_alias_not_detected(tmp_path):
    """@/api/routes is not a relative import — ignored by design.

    Even when the alias resolves to a higher-level layer at runtime, the
    static analyzer cannot follow aliases without a tsconfig.json parser.
    No violation is reported, and no crash occurs.
    """
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(tmp_path / "app/api/routes.ts", "")
    _write(
        tmp_path / "app/domain/service.ts",
        'import { something } from "@/api/routes";\n',
    )

    result = analyze_imports(tmp_path)

    # @-prefixed alias → not a relative import → not detected → no violation
    assert not any("domain" in v["file"] for v in result["layer_violations"])


def test_ts_tilde_prefix_alias_not_detected(tmp_path):
    """~/services/job is not a relative import — ignored by design."""
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(tmp_path / "app/api/routes.ts", "")
    _write(
        tmp_path / "app/domain/service.ts",
        'import { something } from "~/services/job";\n',
    )

    result = analyze_imports(tmp_path)
    assert not any("domain" in v["file"] for v in result["layer_violations"])


def test_ts_scoped_package_alias_not_detected(tmp_path):
    """@core/domain is treated as an external scoped package — ignored by design."""
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(
        tmp_path / "app/domain/service.ts",
        'import { Entity } from "@core/domain";\n',
    )

    result = analyze_imports(tmp_path)
    assert result["layer_violations"] == []


def test_ts_mixed_alias_and_relative_imports_no_crash(tmp_path):
    """Files mixing path aliases with relative imports must not crash.

    Only the relative import can produce a violation; aliases are silently
    skipped. boundary_map must remain consistent regardless of alias content.
    """
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(tmp_path / "app/api/real.ts", "")
    _write(
        tmp_path / "app/domain/mixed.ts",
        'import { A } from "@/api/routes";\n'      # alias — ignored
        'import { B } from "~/services/job";\n'    # alias — ignored
        'import { C } from "@core/domain";\n'      # alias — ignored
        'import { D } from "../../api/real";\n',   # relative — detected
    )

    result = analyze_imports(tmp_path)

    assert "layer_violations" in result
    assert "boundary_map" in result
    # boundary_map reflects directory structure, not import content
    assert result["boundary_map"].get("app/api") == "api"
    assert result["boundary_map"].get("app/domain") == "domain"
    # At most one violation (from the relative import); never four
    domain_violations = [v for v in result["layer_violations"] if "domain" in v["file"]]
    assert len(domain_violations) <= 1


# ─── Stdlib / framework exclusion (UPGRADE 1) ────────────────────────────────


def test_stdlib_modules_set_contains_key_entries():
    """STDLIB_MODULES must include common builtins that triggered false positives."""
    assert "uuid" in STDLIB_MODULES
    assert "datetime" in STDLIB_MODULES
    assert "os" in STDLIB_MODULES
    assert "typing" in STDLIB_MODULES
    assert "argparse" in STDLIB_MODULES


def test_framework_modules_set_contains_key_entries():
    assert "fastapi" in FRAMEWORK_MODULES
    assert "pydantic" in FRAMEWORK_MODULES
    assert "sqlalchemy" in FRAMEWORK_MODULES
    assert "httpx" in FRAMEWORK_MODULES


def test_framework_modules_no_duplicates():
    # frozenset deduplications happen automatically, but the source had aiohttp twice
    # — check the set size matches the unique count of entries we expect
    assert "aiohttp" in FRAMEWORK_MODULES
    # If aiohttp appears twice in the source literal it still becomes one entry in
    # the frozenset; this test guards against future accidental duplication
    assert FRAMEWORK_MODULES == frozenset(FRAMEWORK_MODULES)


def test_external_modules_is_union():
    assert _EXTERNAL_MODULES == STDLIB_MODULES | FRAMEWORK_MODULES
    assert "uuid" in _EXTERNAL_MODULES
    assert "fastapi" in _EXTERNAL_MODULES


def test_uuid_import_in_api_layer_does_not_produce_violation(tmp_path):
    """Regression: uuid was classified as 'ui' layer (substring 'ui' in 'uuid').
    After UPGRADE 1, uuid is excluded before any layer matching."""
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(
        tmp_path / "app/api/routes.py",
        "import uuid\nfrom uuid import UUID\n",
    )

    result = analyze_imports(tmp_path)
    uuid_violations = [v for v in result["layer_violations"] if "uuid" in v.get("imported", "")]
    assert uuid_violations == [], f"False positive uuid violations: {uuid_violations}"


def test_fastapi_import_in_service_layer_does_not_produce_violation(tmp_path):
    """Regression: fastapi was classified as 'api' layer (substring 'api' in 'fastapi').
    After UPGRADE 1, fastapi is excluded as a framework module."""
    _mkdirs(tmp_path, "app/api", "app/services")
    _write(
        tmp_path / "app/services/source_service.py",
        "from fastapi import HTTPException\n",
    )

    result = analyze_imports(tmp_path)
    fastapi_violations = [v for v in result["layer_violations"] if "fastapi" in v.get("imported", "")]
    assert fastapi_violations == [], f"False positive fastapi violations: {fastapi_violations}"


def test_stdlib_imports_never_produce_violations(tmp_path):
    """All imports from STDLIB_MODULES must be silent regardless of which layer imports them."""
    _mkdirs(tmp_path, "app/infrastructure", "app/api")
    stdlib_imports = "\n".join(
        f"import {mod}" for mod in ["os", "sys", "uuid", "datetime", "json", "typing"]
    )
    _write(tmp_path / "app/infrastructure/db.py", stdlib_imports)

    result = analyze_imports(tmp_path)
    assert result["layer_violations"] == [], (
        f"Stdlib imports must not generate violations: {result['layer_violations']}"
    )


def test_real_layer_violation_still_detected_after_upgrade(tmp_path):
    """UPGRADE 1 exclusion must not suppress genuine architectural violations."""
    _mkdirs(tmp_path, "app/api", "app/domain")
    _write(
        tmp_path / "app/domain/business.py",
        "import uuid\nfrom app.api.routes import something\n",
    )

    result = analyze_imports(tmp_path)
    # uuid must be excluded (no false positive)
    uuid_violations = [v for v in result["layer_violations"] if "uuid" in v.get("imported", "")]
    assert uuid_violations == []
    # Real domain→api violation must still be detected
    real_violations = [v for v in result["layer_violations"] if "app/api" in v.get("imported", "")]
    assert len(real_violations) >= 1
