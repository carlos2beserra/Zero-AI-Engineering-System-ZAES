"""Fase 2 readiness — bounded context stability and retrieval scoring utilities.

Zero-LLM. Deterministic functions used by V4 (Jaccard stability) and V7 (retrieval benchmark).
"""

from __future__ import annotations


def jaccard(a: list[str] | set[str], b: list[str] | set[str]) -> float:
    """Compute Jaccard similarity between two sets.

    Returns 1.0 for two empty sets (vacuously identical).
    Returns 0.0 when exactly one set is empty and the other is not.
    """
    sa, sb = set(a), set(b)
    union = sa | sb
    if not union:
        return 1.0
    return len(sa & sb) / len(union)


def validate_context_stability(
    run1: list[dict],
    run2: list[dict],
    threshold: float = 0.70,
) -> dict:
    """Measure structural stability of bounded contexts between two analysis runs.

    Matching strategy:
      1. Exact module_fingerprint match (stable across LLM renames).
      2. Fallback: best Jaccard overlap on normalized module lists.

    avg_jaccard is computed only over matched pairs with overlap > 0 to avoid
    penalizing runs where the LLM split or merged contexts. Contexts that
    disappeared entirely are reported in removed_contexts; new contexts in
    added_contexts.

    Returns a dict with:
      - matched: list of {name_run1, name_run2, jaccard} records
      - avg_jaccard: float — average over pairs with jaccard > 0
      - passed: bool — True iff avg_jaccard >= threshold
      - threshold: the threshold used
      - added_contexts: contexts present in run2 but unmatched
      - removed_contexts: contexts present in run1 with no overlap in run2
    """
    unmatched_r2 = list(run2)
    matched: list[tuple[str, str, float]] = []

    for c1 in run1:
        fp1 = c1.get("module_fingerprint")
        fp_match = next(
            (c2 for c2 in unmatched_r2 if c2.get("module_fingerprint") == fp1 and fp1 is not None),
            None,
        )
        if fp_match is not None:
            matched.append((c1["name"], fp_match["name"], 1.0))
            unmatched_r2.remove(fp_match)
            continue

        # Fallback: best module overlap
        if not unmatched_r2:
            matched.append((c1["name"], "", 0.0))
            continue
        best = max(unmatched_r2, key=lambda c2, _c1=c1: jaccard(_c1.get("modules", []), c2.get("modules", [])))
        sim = jaccard(c1.get("modules", []), best.get("modules", []))
        matched.append((c1["name"], best["name"], sim))
        unmatched_r2.remove(best)

    avg = sum(s for _, _, s in matched) / len(matched) if matched else 1.0

    return {
        "matched": [{"name_run1": n1, "name_run2": n2, "jaccard": round(s, 4)} for n1, n2, s in matched],
        "avg_jaccard": round(avg, 4),
        "passed": avg >= threshold,
        "threshold": threshold,
        "added_contexts": [c2["name"] for c2 in unmatched_r2],
        "removed_contexts": [n1 for n1, n2, s in matched if not s],
    }


def compute_retrieval_score(
    query_keywords: list[str],
    assertion: dict,
    domain_names: list[str] | None = None,
) -> float:
    """Score an assertion's relevance to a query for warm context retrieval.

    Heuristic scoring (no LLM). Three signals:

    - keyword_overlap  (0.55): fraction of query_keywords found in assertion text fields
    - domain_match     (0.30): fraction of domain_names that appear in assertion text
    - has_id_bonus     (0.15): flat bonus for assertions with an "id" field (crosslinked)

    Weights sum to 1.0. Returns a float in [0.0, 1.0].

    This is the V7 pre-Fase-2 scoring function. Production retrieval (Fase 2) will
    replace the keyword overlap with embedding similarity; the domain_match and
    has_id_bonus signals are expected to survive into Fase 2.
    """
    text = _flatten_assertion_text(assertion)

    keyword_score = 0.0
    if query_keywords:
        hits = sum(1 for kw in query_keywords if kw.lower() in text)
        keyword_score = hits / len(query_keywords)

    domain_score = 0.0
    if domain_names:
        hits = sum(1 for d in domain_names if d.lower() in text)
        domain_score = hits / len(domain_names)

    id_bonus = 0.15 if assertion.get("id") else 0.0

    raw = keyword_score * 0.55 + domain_score * 0.30 + id_bonus
    return round(min(raw, 1.0), 4)


def _flatten_assertion_text(assertion: dict) -> str:
    """Concatenate all string leaf values of an assertion dict into a single lowercase string."""
    parts: list[str] = []

    def _collect(obj: object) -> None:
        if isinstance(obj, str):
            parts.append(obj.lower())
        elif isinstance(obj, dict):
            for v in obj.values():
                _collect(v)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)

    _collect(assertion)
    return " ".join(parts)
