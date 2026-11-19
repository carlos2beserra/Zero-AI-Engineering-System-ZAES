#!/usr/bin/env python3
"""MAES data models — Module, Domain, Assertion, State."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal

AssertionType = Literal["CONSTRAINT", "PATTERN", "RATIONALE", "COMPLIANCE", "CONTRACT"]
ConfidenceLevel = Literal["explicit", "inferred-high", "inferred-medium", "assumed"]

LAYER_NAMES: dict[int, str] = {
    1: "compliance",
    2: "security",
    3: "contracts",
    4: "architecture",
    5: "domain",
    6: "engineering",
    7: "inferred-patterns",
}

CONFIDENCE_RANK: dict[str, int] = {
    "explicit": 4,
    "inferred-high": 3,
    "inferred-medium": 2,
    "assumed": 1,
}

_POLARITY_BY_TYPE: dict[str, int] = {
    "CONSTRAINT": -1,
    "COMPLIANCE": -1,
    "CONTRACT": -1,
    "PATTERN": 0,
    "RATIONALE": 1,
}

_VALID_TYPES = frozenset({"CONSTRAINT", "PATTERN", "RATIONALE", "COMPLIANCE", "CONTRACT"})
_VALID_CONFIDENCE = frozenset({"explicit", "inferred-high", "inferred-medium", "assumed"})


def polarity(assertion_type: str) -> int:
    """Derived from type — never stored. Returns +1 (allow), -1 (forbid), 0 (neutral)."""
    return _POLARITY_BY_TYPE.get(assertion_type, 0)


# ─── Source file definition (ADR 0009) ────────────────────────────────────────
#
# CANONICAL_SOURCE_EXTENSIONS is the Analyze's OFFICIAL definition of "source
# file". No stage keeps its own list or local subset to answer "is this source?"
# — every such decision derives from this set. Two divergent copies
# (pipeline._SOURCE_EXTENSIONS vs arch_analysis._SOURCE_EXTS) is precisely how
# .tsx/.jsx/.vue became invisible to Stage 1 while Stage 2 could handle them.
#
# What it is NOT: it does not represent "all code in the project" and is not a
# universal taxonomy of code. It defines the POPULATION of this system, so adding
# SQL/Terraform/YAML/GraphQL/config changes coverage, sampling, funnel and emitted
# nodes — that requires an explicit architectural decision, never an append
# because "it's also code".
#
# Capability-scoped subsets are legitimate but must derive from this set and be
# named after the capability (see IMPORT_PARSEABLE_EXTENSIONS below).

CANONICAL_SOURCE_EXTENSIONS: frozenset[str] = frozenset({
    ".ts", ".tsx", ".js", ".jsx", ".vue", ".svelte",
    ".py", ".go", ".rs", ".java", ".kt", ".rb", ".php",
})

# Capability, not definition: "can we extract imports from this language?".
# Derived — never a loose literal elsewhere.
IMPORT_PARSEABLE_EXTENSIONS: frozenset[str] = CANONICAL_SOURCE_EXTENSIONS & {
    ".py", ".ts", ".tsx", ".js", ".jsx",
}


# ─── StackContext ─────────────────────────────────────────────────────────────
#
# Normalized projection of inferred/stack.json. The raw LLM output has
# unstable shape ({languages:[]} vs {backend:{language:""}} vs ...);
# compiler._normalize_stack() collapses all known shapes into this
# fixed schema so the adapter renderer never alucinates fields.

@dataclass(frozen=True)
class StackContext:
    languages: tuple[str, ...] = ()
    frameworks: tuple[str, ...] = ()
    runtimes: tuple[str, ...] = ()
    package_managers: tuple[str, ...] = ()

    def is_empty(self) -> bool:
        return not (self.languages or self.frameworks
                    or self.runtimes or self.package_managers)

    def to_dict(self) -> dict:
        return {
            "languages": list(self.languages),
            "frameworks": list(self.frameworks),
            "runtimes": list(self.runtimes),
            "package_managers": list(self.package_managers),
        }


# ─── RuntimeContext ───────────────────────────────────────────────────────────
# Canonical commands for test/build/lint/run/migrate, parsed from
# context/human/runtime.md frontmatter. `last_verified` (ISO date) is
# required; compiler emits a staleness warning when it exceeds 30 days.

@dataclass(frozen=True)
class RuntimeContext:
    test: str = ""
    build: str = ""
    lint: str = ""
    run: str = ""
    migrate: str = ""
    test_pattern: str = ""
    run_module_test: str = ""
    last_verified: str = ""        # ISO date YYYY-MM-DD
    staleness_warning: bool = False  # set by compiler when older than threshold

    def is_empty(self) -> bool:
        return not (self.test or self.build or self.lint or self.run
                    or self.migrate or self.test_pattern
                    or self.run_module_test)

    def to_dict(self) -> dict:
        return {
            "test": self.test,
            "build": self.build,
            "lint": self.lint,
            "run": self.run,
            "migrate": self.migrate,
            "test_pattern": self.test_pattern,
            "run_module_test": self.run_module_test,
            "last_verified": self.last_verified,
            "_staleness_warning": self.staleness_warning,
        }


# ─── ArchitectureNode ─────────────────────────────────────────────────────────

# NodeType is str (not Literal) — extensible without migrations.
NodeType = str

# Known constants; callers should use these instead of raw strings.
NODE_TYPE_SERVICE        = "Service"
NODE_TYPE_WORKER         = "Worker"
NODE_TYPE_CONTROLLER     = "Controller"
NODE_TYPE_REPOSITORY     = "Repository"
NODE_TYPE_DOMAIN         = "Domain"
NODE_TYPE_LAYER          = "Layer"
NODE_TYPE_INFRASTRUCTURE = "Infrastructure"
NODE_TYPE_CLI            = "CLI"
NODE_TYPE_API            = "API"
NODE_TYPE_CONSUMER       = "Consumer"
NODE_TYPE_PRODUCER       = "Producer"
NODE_TYPE_SCHEDULER      = "Scheduler"
NODE_TYPE_ADAPTER        = "Adapter"
NODE_TYPE_GATEWAY        = "Gateway"
NODE_TYPE_FRONTEND       = "Frontend"

NodeVisibility = Literal["obvious", "hidden", "internal"]


def _path_to_id(path: str) -> str:
    """Derive a human-readable, unique id from a normalized path.

    "src/modules/auth" → "src_modules_auth"
    Deterministic and unique because path is unique in the filesystem.
    Breaks on rename — that is intentional (new path = new node).
    Callers that need rename-stability should use stable_key instead.
    """
    return re.sub(r"[^a-z0-9]+", "_", path.lower().strip("/")).strip("_") or "root"


@dataclass(frozen=True)
class ArchitectureNode:
    """A single module/layer in the project architecture map.

    id          = slug(path) — changes when path is renamed.
    stable_key  = id initially; will diverge when StableNodeIdentity RFC is implemented.
                  All consumers (Assertion.node_id, dependency edges) MUST reference
                  stable_key so future migrations only change stable_key generation.
    """

    id: str                 # _path_to_id(path)
    stable_key: str         # = id initially; migration hook for future RFC
    name: str               # last path segment, e.g. "auth"
    path: str               # "src/modules/auth"
    type: NodeType          # NODE_TYPE_* constant or custom string
    domain: str             # heuristic-inferred domain name
    domain_confidence: float  # 0.0–1.0 (0.9 = strong signal, 0.35 = ambiguous)
    visibility: NodeVisibility  # "obvious" | "hidden" | "internal"
    entry_points: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # stable_keys of dependencies
    file_count: int = 0     # files in this node — POPULATION
    # ADR 0009: completeness is expressed as a population/evidence PAIR, never as a
    # per-feature boolean. files_sampled == 0 means EVERY semantic field of this node
    # (entry_points today, anything added later) lacks evidence — not that it is empty.
    # files_sampled < file_count means partial evidence. The consumer compares the two
    # numbers; the Analyze does not emit the interpretation.
    files_sampled: int = 0  # of those, how many had content read — EVIDENCE

    @staticmethod
    def make(path: str, node_type: NodeType, domain: str,
             domain_confidence: float = 0.5) -> "ArchitectureNode":
        node_id = _path_to_id(path)
        name = path.rstrip("/").rsplit("/", 1)[-1] if "/" in path else path
        return ArchitectureNode(
            id=node_id,
            stable_key=node_id,
            name=name,
            path=path,
            type=node_type,
            domain=domain,
            domain_confidence=round(max(0.0, min(1.0, domain_confidence)), 2),
            visibility="obvious",
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "stable_key": self.stable_key,
            "name": self.name,
            "path": self.path,
            "type": self.type,
            "domain": self.domain,
            "domain_confidence": self.domain_confidence,
            "visibility": self.visibility,
            "entry_points": self.entry_points,
            "dependencies": self.dependencies,
            "file_count": self.file_count,
            "files_sampled": self.files_sampled,
        }


# ─── ArchitectureCandidate (intermediate — never serialized in normal output) ──

@dataclass
class ArchitectureCandidate:
    """Intermediate representation during Architecture Builder candidate-collapse phase.

    Never written to disk in normal mode. With --verbose the builder may include
    a _candidates_debug key in architecture_map.json for inspection.
    """

    path: str
    files: list[str]
    file_count: int
    parent: str | None
    children: list[str]
    collapsed_from: list[str]   # paths of candidates absorbed into this one
    collapse_reason: str | None  # "layer_group" | "too_small" | "split_down" | None
    semantic_weight: int = 0     # computed before collapse; weight > 0 blocks collapse


# ─── Module (legacy) ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Module:
    id: str         # SHA256[:16](name.lower())
    name: str
    domain: str     # domain name reference (not ID)
    paths: list[str]

    @staticmethod
    def make_id(name: str) -> str:
        return hashlib.sha256(name.lower().encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "domain": self.domain,
            "paths": self.paths,
        }


@dataclass(frozen=True)
class Domain:
    name: str

    @property
    def id(self) -> str:
        """Derived from name — not stored. Stable identifier for reference."""
        return hashlib.sha256(self.name.lower().encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "id": self.id,
        }


@dataclass
class Assertion:
    id: str           # SHA256[:16](claim.lower().strip())
    claim: str
    type: AssertionType
    layer: int        # 1–7
    subject: str | None  # module.id or domain.name; None = global (layers 1–2 only)
    paths: list[str]
    confidence: ConfidenceLevel
    source: str       # file path: "human/compliance.md" | "inferred/assertions.json"
    ttl: str
    last_verified: str
    owner: str
    merge_history: list[str] = field(default_factory=list)
    code_examples: list[dict] = field(default_factory=list)
    # Localization fields (populated by analyze_cmd when architecture_map is available)
    evidence: str | None = None      # "src/modules/auth/auth.service.ts:42"
    scope_type: Literal["global", "bounded_context", "module", "file"] = "global"
    node_id: str | None = None       # ArchitectureNode.stable_key

    @staticmethod
    def make_id(claim: str) -> str:
        normalized = " ".join(claim.lower().split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "claim": self.claim,
            "type": self.type,
            "layer": self.layer,
            "layer_name": LAYER_NAMES.get(self.layer, "unknown"),
            "subject": self.subject,
            "paths": self.paths,
            "confidence": self.confidence,
            "source": self.source,
            "ttl": self.ttl,
            "last_verified": self.last_verified,
            "owner": self.owner,
            "merge_history": self.merge_history,
            "code_examples": self.code_examples,
            "evidence": self.evidence,
            "scope_type": self.scope_type,
            "node_id": self.node_id,
        }


@dataclass
class State:
    modules: list[Module]
    domains: list[Domain]
    assertions: list[Assertion]
    architecture_map: list[ArchitectureNode] = field(default_factory=list)
    stack: StackContext = field(default_factory=StackContext)
    runtime: RuntimeContext = field(default_factory=RuntimeContext)


@dataclass
class ConflictRecord:
    id: str
    assertion_a: str
    assertion_b: str
    status: Literal["RESOLVED", "UNRESOLVED"]
    reason: str
    winner: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "assertion_a": self.assertion_a,
            "assertion_b": self.assertion_b,
            "status": self.status,
            "reason": self.reason,
            "winner": self.winner,
        }
