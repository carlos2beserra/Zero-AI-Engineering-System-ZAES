#!/usr/bin/env python3
"""Evidence-sufficiency policy for the Analyze (ADR 0009).

This module holds POLICY — the answer to "do I have enough evidence to assert?".
It is deliberately NOT a bucket of constants: consumers that ask this question must
consult this policy instead of inlining their own floor. Different floors per
consumer are legitimate — that is what the `floor` parameter is for — but *scattered*
floors are not.

Two distinct questions live here, because two distinct kinds of claim exist and the
evidence for each is different. Conflating them is the category error ADR 0009 exists
to prevent:

  - CONTENT-derived claims (entry_points, dep_edges, anything read from a file):
    evidence is `sampling_ratio` → has_sufficient_sample()
  - STRUCTURE-derived claims (where does a Service live?): evidence is whether the
    artifact was built over the population at all → has_population_semantics()

The mechanism of expressing a refusal (a status value in an emitted artifact) belongs
to the caller, not here.
"""

from __future__ import annotations

# PARAMETER OF POLICY, not an invariant nor a public contract. Revisable on field
# evidence; not part of any schema and not configurable in this version. Changing
# the value is not a breaking change; removing the policy is.
#
# NOT a statistical confidence threshold. It is an operational barrier against
# conclusions we already know are fragile. It does not claim that 25% is enough to
# trust — it states that below it we know it is not. It may be too high for a huge
# monorepo and too low for a small critical project; it does not pretend to solve that.
MIN_SAMPLING_FOR_CONTENT_CLAIMS = 0.25

# First schema whose coverage metrics are measured against the project POPULATION
# instead of the content sample. Below it, a structural claim cannot be trusted —
# not because too little was read, but because the topology itself was built on a
# budget-capped sample.
MIN_SCHEMA_FOR_POPULATION_SEMANTICS = (2, 1)


def has_sufficient_sample(
    sampling_ratio: float | None,
    floor: float = MIN_SAMPLING_FOR_CONTENT_CLAIMS,
) -> bool:
    """Is there enough evidence for a claim derived from FILE CONTENT?

    FAIL-CLOSED: an unknown sampling ratio is insufficiency, not permission.
    """
    return sampling_ratio is not None and sampling_ratio >= floor


def has_population_semantics(schema_version: str | None) -> bool:
    """Is there enough evidence for a claim derived from PROJECT STRUCTURE?

    The precondition is not "how much content was read" — a placement conclusion is
    built from node paths, types and file counts, all of which come from the
    population. The precondition is whether this artifact's topology was built over
    the population at all.

    FAIL-CLOSED: an absent or unparseable version is insufficiency, not permission —
    which is what keeps the `sync` inside `maes upgrade` from re-emitting a conclusion
    derived from a budget-capped sample.
    """
    if not isinstance(schema_version, str):
        return False
    try:
        parts = tuple(int(p) for p in schema_version.split(".")[:2])
    except ValueError:
        return False
    if len(parts) < 2:
        return False
    return parts >= MIN_SCHEMA_FOR_POPULATION_SEMANTICS
