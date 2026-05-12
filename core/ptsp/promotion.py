"""Promotion Gate — Inference → Fact conversion under structural evidence.

This is the load-bearing function that distinguishes PTSP from naive chain-of-
thought. An LLM-emitted Inference does NOT become a Fact just because the
model is confident, fluent, or repeats it in later steps. It becomes a Fact
only if one of three structural evidence types is presented:

  1. OperatorCosign — Ed25519 signature by the operator over the inference's
     content hash. The operator has explicitly read and endorsed.
  2. TestPassResult — a deterministic test that exits 0 against the
     inference's content. Machine-verifiable.
  3. ExternalOracleAttestation — an Ed25519-signed attestation from a
     pre-trusted external oracle (e.g., a regulatory database query).

Invariant I3 is also enforced here at promotion time: a Fact cannot
transitively depend on an unresolved Inference. If the inference being
promoted references another inference id, the gate refuses until that
upstream inference has itself been promoted.

The gate is intentionally pure — it does not mutate any boundary, it
returns a new Fact dataclass and relies on the seal protocol to verify
the resulting boundary is well-formed before sealing.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from typing import Mapping

from core.ptsp.canonical import jcs_canonical, sha256_hex
from core.signing.ed25519_compat import verify_signature, SignatureVerificationError
from core.ptsp.types import (
    ExternalOracleAttestation,
    Fact,
    Inference,
    OperatorCosign,
    PromotionEvidence,
    PromotionRecord,
    PromotionRejected,
    SourceArtifact,
    TestPassResult,
    _now_iso,
    _uuid4,
)


def _verify_signature_or_reject(
    pubkey_hex: str,
    message: bytes,
    signature_hex: str,
    *,
    rejection_code: str = "invalid_operator_signature",
) -> None:
    """Raise PromotionRejected if signature is invalid.

    Delegates to `core.signing.ed25519_compat.verify_signature`, which
    transparently handles both production Ed25519 (PyNaCl) and test-mode
    HMAC-SHA256 fallback. Test-mode signatures are explicitly tagged and
    the verifier CLI refuses them unless `--allow-test-signatures` is set.
    """
    try:
        verify_signature(pubkey_hex, message, signature_hex)
    except SignatureVerificationError as e:
        raise PromotionRejected(rejection_code, str(e)) from e


def _evidence_hash(evidence: PromotionEvidence) -> str:
    """JCS-canonical hash of the evidence object for the PromotionRecord."""
    return sha256_hex(jcs_canonical(evidence.to_dict()))


def promote_inference_to_fact(
    inference: Inference,
    evidence: PromotionEvidence,
    ledger_facts_by_id: Mapping[str, Fact],
    current_step_index: int,
) -> Fact:
    """Promote an Inference to a Fact. Returns a new Fact instance.

    Raises PromotionRejected with a specific `.code` for any structural
    invariant violation. The caller is expected to inspect `.code` and
    surface an appropriate operator-facing remediation.
    """

    # ── Invariant I3: transitive dependency check ──────────────────────────
    # Every id in the inference's depends_on MUST already be in the Facts
    # ledger; an inference depending on another unresolved inference cannot
    # be promoted (the dependency chain must be flattened first).
    for dep_id in inference.depends_on:
        if dep_id not in ledger_facts_by_id:
            raise PromotionRejected(
                "transitive_inference_dependency",
                f"inference {inference.id} depends on unresolved id {dep_id}; "
                f"promote dependency to Fact first",
            )

    # ── Evidence-class branch ──────────────────────────────────────────────
    if isinstance(evidence, OperatorCosign):
        payload = jcs_canonical(
            {
                "inference_id": inference.id,
                "content_sha256": sha256_hex(inference.content.encode("utf-8")),
                "cosigned_at": evidence.cosigned_at,
            }
        )
        _verify_signature_or_reject(
            evidence.operator_pubkey_hex,
            payload,
            evidence.signature_hex,
            rejection_code="invalid_operator_signature",
        )
        verification_method = "operator_cosign"
        source_artifact = SourceArtifact(
            type="operator_attestation",
            locator=evidence.operator_pubkey_hex[:16],
            content_hash=sha256_hex(payload),
        )

    elif isinstance(evidence, TestPassResult):
        if evidence.test_target_inference_id != inference.id:
            raise PromotionRejected(
                "test_target_mismatch",
                f"test targeted {evidence.test_target_inference_id}, "
                f"but inference is {inference.id}",
            )
        if evidence.exit_code != 0:
            raise PromotionRejected(
                "test_did_not_pass",
                f"test {evidence.test_id} exited with code {evidence.exit_code}",
            )
        verification_method = "test_pass"
        source_artifact = SourceArtifact(
            type="test_id",
            locator=evidence.test_id,
            content_hash=evidence.stdout_sha256,
        )

    elif isinstance(evidence, ExternalOracleAttestation):
        oracle_payload = jcs_canonical(
            {
                "inference_id": inference.id,
                "content_sha256": sha256_hex(inference.content.encode("utf-8")),
                "attested_at": evidence.attested_at,
            }
        )
        _verify_signature_or_reject(
            evidence.oracle_pubkey_hex,
            oracle_payload,
            evidence.oracle_signature_hex,
            rejection_code="invalid_oracle_signature",
        )
        verification_method = "external_oracle"
        source_artifact = SourceArtifact(
            type="oracle_id",
            locator=evidence.oracle_id,
            content_hash=evidence.attestation_payload_sha256,
        )

    else:
        raise PromotionRejected(
            "unrecognized_evidence_kind",
            f"evidence type {type(evidence).__name__} is not a recognized "
            f"PromotionEvidence",
        )

    # ── Build the new Fact ─────────────────────────────────────────────────
    return Fact(
        id=_uuid4(),
        content=inference.content,
        source_artifact=source_artifact,
        verified_at=_now_iso(),
        verification_method=verification_method,
        depends_on=tuple(inference.depends_on),
        promoted_from=PromotionRecord(
            inference_id=inference.id,
            evidence_hash=_evidence_hash(evidence),
            promoted_at=_now_iso(),
            promoted_at_step=current_step_index,
        ),
        created_at_step=current_step_index,
    )
