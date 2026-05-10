"""Provenance-Tagged Step Pipeline (PTSP) — counter to LLM self-conditioning.

Background. arXiv 2509.09677 ("The Illusion of Diminishing Returns: Measuring
Long-Horizon Execution in LLMs") demonstrates that frontier models degrade
monotonically with task length due to a *self-conditioning effect*: prior
errors emitted into context are silently treated as facts by the model in
later steps; per-step accuracy that looks near-ceiling on single-turn
benchmarks collapses across multi-step trajectories. Scaling alone does not
fix this; sequential test-time compute with explicit provenance does.

PTSP is the structural counter. Each step boundary holds four disjoint
ledgers — Fact, Inference, Unknown, Assumption. Items move between ledgers
only through the Promotion Gate, which requires explicit evidence
(operator cosign, deterministic test pass, or external oracle attestation)
to convert an Inference into a Fact. Context injection at step N+1 tags
items non-fungibly so the model cannot silently treat prior LLM output as
ground truth.

This module is the typed kernel of that pipeline. It is intentionally
strict: every invariant violation raises rather than returning a best-effort
result. The surrounding runtime decides how to surface failures (block,
advisory, log-and-flag).

This module is additive — it does NOT replace `reasoning-surface@1` or the
existing `reasoning_surface_guard.py` hot path. Promotion to default-path is
its own gated Event with its own Reasoning Surface and review.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
# Runtime path resolution: tests/CLI run with pytest pythonpath=["src", "."]
# from pyproject.toml; standalone runs add repo root to sys.path. Pyright
# warnings on these imports are cosmetic and matched to house style across
# the existing core/ namespace package.
from core.ptsp.types import (
    Assumption,
    Detectability,
    ExternalOracleAttestation,
    Fact,
    ImmutableLedgerError,
    Inference,
    ModelIdentity,
    OperatorCosign,
    PromotionBlocker,
    PromotionEvidence,
    PromotionRecord,
    PromotionRejected,
    ProvenanceKind,
    SourceArtifact,
    StepBoundary,
    TestPassResult,
    Unknown,
    VerificationMethod,
)
from core.ptsp.canonical import jcs_canonical, sha256_hex, sha256_of_jcs
from core.ptsp.promotion import promote_inference_to_fact
from core.ptsp.seal import seal_step_boundary
from core.ptsp.context_injection import render_step_context

__all__ = [
    # Types
    "ProvenanceKind",
    "VerificationMethod",
    "Detectability",
    "SourceArtifact",
    "ModelIdentity",
    "PromotionRecord",
    "PromotionBlocker",
    "Fact",
    "Inference",
    "Unknown",
    "Assumption",
    "StepBoundary",
    "OperatorCosign",
    "TestPassResult",
    "ExternalOracleAttestation",
    "PromotionEvidence",
    # Errors
    "PromotionRejected",
    "ImmutableLedgerError",
    # Functions
    "jcs_canonical",
    "sha256_hex",
    "sha256_of_jcs",
    "promote_inference_to_fact",
    "seal_step_boundary",
    "render_step_context",
]
