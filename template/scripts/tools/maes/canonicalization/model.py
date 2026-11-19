"""Canonical model builder — converts agent modules list to compiler model.json.

Invariant (I1): uses module.get("domain") only — never infers or invents domain.
               Absent domain is written as null, not filled with a default value.
               Domain inference is the agent's contractual responsibility.
"""
from __future__ import annotations


def build_model(modules_raw: list[dict]) -> dict:
    """Convert an agent modules list to the compiler's model.json format.

    Parameters
    ----------
    modules_raw:
        List of module dicts as written by the agent in modules.json (e.g.
        ``{"name": "auth", "path": "src/auth", "domain": "identity", ...}``).
        The ``domain`` field is used as-is when present. When absent, the module
        is recorded with ``"domain": null`` — this is correct, not an error.
        The ``_unclassified`` count in canonicalization-report.json signals
        agent quality, not a framework defect.

    Returns
    -------
    dict
        ``{"modules": [...], "domains": [...]}`` ready for model.json.
        Domains are derived exclusively from the ``domain`` field of each module.
        Modules with ``domain: null`` are excluded from the domains list.
    """
    modules: list[dict] = []
    domains_index: dict[str, list[str]] = {}  # domain_name → [module_names]

    for m in modules_raw:
        if not isinstance(m, dict) or not m.get("name"):
            continue

        name = m["name"]
        domain = m.get("domain")  # intentionally None when absent — I1

        raw_paths = m.get("paths")
        if not isinstance(raw_paths, list):
            raw_paths = None
        if not raw_paths and m.get("path"):
            raw_paths = [m["path"]]
        paths = [p for p in (raw_paths or []) if isinstance(p, str) and p.strip()]

        modules.append({"name": name, "domain": domain, "paths": paths})

        if domain is not None:
            domains_index.setdefault(str(domain), []).append(name)

    domains = [
        {"name": d, "modules": mods}
        for d, mods in sorted(domains_index.items())
    ]

    return {"modules": modules, "domains": domains}


def count_domain_coverage(modules: list[dict]) -> dict:
    """Return structural coverage counts for --validate / report output.

    This is an observability helper — it reports, never decides.
    """
    total = len(modules)
    with_domain = sum(1 for m in modules if m.get("domain") is not None)
    return {
        "total": total,
        "with_domain": with_domain,
        "without_domain": total - with_domain,
    }
