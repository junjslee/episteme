"""Typed primitives for the Provenance-Tagged Step Pipeline.

Every dataclass here is frozen — once constructed, instances cannot be
mutated. Mutation discipline is enforced by Python's frozen-dataclass
machinery; ledger-level mutation is enforced by the seal protocol in
`core.ptsp.seal`.

The discriminant `kind` field on each ledger item is what makes Invariant I1
(ledger disjointness) enforceable — a Fact carries `kind="fact"` and the
seal protocol rejects any boundary whose ledgers contain items with the
wrong kind.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional, Tuple, Union


# ─── Enums (string literals for JCS round-trip stability) ─────────────────

ProvenanceKind = Literal["fact", "inference", "unknown", "assumption"]

VerificationMethod = Literal[
    "operator_cosign",
    "test_pass",
    "external_oracle",
    "operator_read",
    "original_axiom",
]

Detectability = Literal[
    "pre_execution",
    "post_execution_soft",
    "post_execution_irreversible",
]


# ─── Helpers ──────────────────────────────────────────────────────────────

def _uuid4() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    """ISO 8601 UTC timestamp with millisecond precision."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ─── Errors ───────────────────────────────────────────────────────────────

class PromotionRejected(Exception):
    """Promotion gate refused to promote an Inference to a Fact.

    The `code` attribute is one of:
      - invalid_operator_signature
      - test_did_not_pass
      - test_target_mismatch
      - invalid_oracle_signature
      - transitive_inference_dependency
      - unrecognized_evidence_kind
    """

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class ImmutableLedgerError(Exception):
    """Step boundary cannot be sealed because an invariant is violated.

    The first message argument names the violated invariant.
    """


# ─── Value types ──────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SourceArtifact:
    """A pointer to the artifact backing a Fact's verification.

    `content_hash` is SHA-256 of the artifact's bytes at verification time.
    A later auditor can re-fetch the artifact at `locator` and check the
    hash to detect post-hoc drift in the cited source.
    """
    type: Literal["path", "url", "commit_sha", "test_id", "oracle_id", "operator_attestation"]
    locator: str
    content_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Identity of an LLM that produced an Inference."""
    provider: str
    model_name: str
    model_snapshot_hash: str
    sampling_temperature: float
    sampling_top_p: float
    sampling_seed: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d["sampling_seed"] is None:
            d.pop("sampling_seed")
        return d


@dataclass(frozen=True, slots=True)
class PromotionRecord:
    """Audit trail of an Inference→Fact promotion event."""
    inference_id: str
    evidence_hash: str
    promoted_at: str
    promoted_at_step: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PromotionBlocker:
    """Reason an Inference cannot currently be promoted to a Fact."""
    type: Literal[
        "requires_operator_cosign",
        "requires_test_pass",
        "requires_oracle",
        "transitive_dependency_unresolved",
    ]
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Ledger items ─────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Fact:
    """An operator-verified or test-verified assertion.

    Invariant I3: every id in `depends_on` MUST resolve to another Fact's id
    in the same boundary's `knowns` ledger — never an Inference. The seal
    protocol enforces this.
    """
    content: str
    source_artifact: SourceArtifact
    verified_at: str
    verification_method: VerificationMethod
    created_at_step: int
    id: str = field(default_factory=_uuid4)
    depends_on: Tuple[str, ...] = ()
    promoted_from: Optional[PromotionRecord] = None
    kind: ProvenanceKind = "fact"

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "kind": self.kind,
            "id": self.id,
            "content": self.content,
            "source_artifact": self.source_artifact.to_dict(),
            "verified_at": self.verified_at,
            "verification_method": self.verification_method,
            "depends_on": list(self.depends_on),
            "created_at_step": self.created_at_step,
        }
        if self.promoted_from is not None:
            d["promoted_from"] = self.promoted_from.to_dict()
        return d


@dataclass(frozen=True, slots=True)
class Inference:
    """An LLM-generated assertion, NOT promotable to Fact without evidence.

    `confidence_self_reported` is advisory only — it is logged for
    calibration analysis but is never load-bearing in promotion decisions.
    The Promotion Gate requires structural evidence (cosign / test / oracle),
    not a self-reported number.
    """
    content: str
    generated_by: ModelIdentity
    generated_at: str
    created_at_step: int
    confidence_self_reported: float = 0.0
    id: str = field(default_factory=_uuid4)
    promotion_blockers: Tuple[PromotionBlocker, ...] = ()
    depends_on: Tuple[str, ...] = ()
    kind: ProvenanceKind = "inference"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "content": self.content,
            "generated_by": self.generated_by.to_dict(),
            "generated_at": self.generated_at,
            "confidence_self_reported": self.confidence_self_reported,
            "promotion_blockers": [b.to_dict() for b in self.promotion_blockers],
            "depends_on": list(self.depends_on),
            "created_at_step": self.created_at_step,
        }


@dataclass(frozen=True, slots=True)
class Unknown:
    """An open question the operator has explicitly registered.

    `cost_of_ignorance` is operator-authored; the surrounding guard layer
    rejects unknowns with empty or lazy-placeholder cost strings to force
    the operator to articulate what is actually at stake.
    """
    question: str
    cost_of_ignorance: str
    created_at_step: int
    id: str = field(default_factory=_uuid4)
    resolution_path: Optional[str] = None
    kind: ProvenanceKind = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "kind": self.kind,
            "id": self.id,
            "question": self.question,
            "cost_of_ignorance": self.cost_of_ignorance,
            "created_at_step": self.created_at_step,
        }
        if self.resolution_path is not None:
            d["resolution_path"] = self.resolution_path
        return d


@dataclass(frozen=True, slots=True)
class Assumption:
    """An operator-declared if-then dependency.

    Forces the operator to articulate detectability — when would the
    assumption being wrong actually surface? Pre-execution detection is
    cheap; post-execution-irreversible is the failure mode the kernel
    most actively counters.
    """
    assumption: str
    if_wrong_then: str
    detectability: Detectability
    created_at_step: int
    id: str = field(default_factory=_uuid4)
    kind: ProvenanceKind = "assumption"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "id": self.id,
            "assumption": self.assumption,
            "if_wrong_then": self.if_wrong_then,
            "detectability": self.detectability,
            "created_at_step": self.created_at_step,
        }


# ─── Promotion evidence union ─────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class OperatorCosign:
    """Ed25519 signature by the operator over the Inference's content hash."""
    operator_pubkey_hex: str
    signature_hex: str
    cosigned_at: str
    kind: Literal["operator_cosign"] = "operator_cosign"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class TestPassResult:
    """A deterministic test that exits 0 against the inference's content."""
    # Tell pytest this is not a test class — its name starts with "Test" by
    # domain convention (it represents a *test pass*, not a *pytest test*).
    __test__ = False

    test_id: str
    test_target_inference_id: str
    test_command: str
    exit_code: int
    stdout_sha256: str
    ran_at: str
    kind: Literal["test_pass"] = "test_pass"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ExternalOracleAttestation:
    """An Ed25519-signed attestation from a trusted external oracle."""
    oracle_id: str
    oracle_pubkey_hex: str
    oracle_signature_hex: str
    attestation_payload_sha256: str
    attested_at: str
    kind: Literal["external_oracle"] = "external_oracle"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


PromotionEvidence = Union[OperatorCosign, TestPassResult, ExternalOracleAttestation]


# ─── Step boundary ────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class StepBoundary:
    """One sealed step in a PTSP trajectory.

    `parent_hash` is the SHA-256 hex of the JCS-canonical bytes of the
    previous boundary's `to_canonical_dict()` (which excludes self_hash and
    operator_signature). `self_hash` is computed the same way over THIS
    boundary's canonical dict — see `core.ptsp.seal.seal_step_boundary`.
    """
    session_id: str
    step_index: int
    parent_hash: Optional[str]
    knowns: Tuple[Fact, ...]
    inferences: Tuple[Inference, ...]
    unknowns: Tuple[Unknown, ...]
    assumptions: Tuple[Assumption, ...]
    model_calls: Tuple[Dict[str, Any], ...]
    sealed_at: str
    self_hash: str
    operator_signature: Optional[Dict[str, Any]] = None
    schema_version: Literal["1.0"] = "1.0"

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Dict suitable for JCS canonicalization, EXCLUDING self_hash and
        operator_signature (those are computed AFTER canonicalization and
        appended)."""
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "step_index": self.step_index,
            "parent_hash": self.parent_hash,
            "knowns": [f.to_dict() for f in self.knowns],
            "inferences": [i.to_dict() for i in self.inferences],
            "unknowns": [u.to_dict() for u in self.unknowns],
            "assumptions": [a.to_dict() for a in self.assumptions],
            "model_calls": list(self.model_calls),
            "sealed_at": self.sealed_at,
        }

    def to_full_dict(self) -> Dict[str, Any]:
        d = self.to_canonical_dict()
        d["self_hash"] = self.self_hash
        if self.operator_signature is not None:
            d["operator_signature"] = self.operator_signature
        return d
