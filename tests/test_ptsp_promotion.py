"""Tests for core/ptsp/ — Promotion Gate, Step Seal, Context Injection.

These tests use the HMAC-SHA256 test fallback for signatures since PyNaCl
is not a kernel dependency. Production-grade Ed25519 testing is gated on
operator decision to install PyNaCl (covered in
tests/test_ptsp_promotion_ed25519.py, which is skipped if PyNaCl is absent).
"""
from __future__ import annotations

import pytest

from core.ptsp import (
    Assumption,
    ExternalOracleAttestation,
    Fact,
    ImmutableLedgerError,
    Inference,
    ModelIdentity,
    OperatorCosign,
    PromotionRejected,
    SourceArtifact,
    TestPassResult,
    Unknown,
    jcs_canonical,
    promote_inference_to_fact,
    seal_step_boundary,
    sha256_hex,
)
from core.signing.ed25519_compat import (
    generate_keypair,
    sign_message,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────


def _make_inference(content: str = "the prod schema is identical to staging",
                    depends_on: tuple = ()) -> Inference:
    return Inference(
        content=content,
        generated_by=ModelIdentity(
            provider="anthropic",
            model_name="claude-opus-4-7",
            model_snapshot_hash="a" * 64,
            sampling_temperature=0.0,
            sampling_top_p=1.0,
        ),
        generated_at="2026-05-10T20:00:00.000+00:00",
        created_at_step=1,
        confidence_self_reported=0.84,
        depends_on=depends_on,
    )


def _make_operator_cosign(inference: Inference, privkey: str, pubkey: str) -> OperatorCosign:
    """Build a valid OperatorCosign for the given inference."""
    payload = jcs_canonical({
        "inference_id": inference.id,
        "content_sha256": sha256_hex(inference.content.encode("utf-8")),
        "cosigned_at": "2026-05-10T20:01:00.000+00:00",
    })
    sig = sign_message(privkey, payload)
    return OperatorCosign(
        operator_pubkey_hex=pubkey,
        signature_hex=sig,
        cosigned_at="2026-05-10T20:01:00.000+00:00",
    )


# ─── Promotion: happy paths ────────────────────────────────────────────────


def test_promotion_via_operator_cosign_succeeds():
    privkey, pubkey = generate_keypair()
    inference = _make_inference()
    cosign = _make_operator_cosign(inference, privkey, pubkey)
    fact = promote_inference_to_fact(inference, cosign, {}, current_step_index=2)
    assert fact.kind == "fact"
    assert fact.content == inference.content
    assert fact.verification_method == "operator_cosign"
    assert fact.promoted_from is not None
    assert fact.promoted_from.inference_id == inference.id
    assert fact.promoted_from.promoted_at_step == 2


def test_promotion_via_test_pass_succeeds():
    inference = _make_inference("the regex matches all valid email addresses")
    test_result = TestPassResult(
        test_id="test://email-regex-coverage",
        test_target_inference_id=inference.id,
        test_command="pytest tests/test_email_regex.py",
        exit_code=0,
        stdout_sha256="b" * 64,
        ran_at="2026-05-10T20:02:00.000+00:00",
    )
    fact = promote_inference_to_fact(inference, test_result, {}, current_step_index=3)
    assert fact.kind == "fact"
    assert fact.verification_method == "test_pass"
    assert fact.source_artifact.type == "test_id"
    assert fact.source_artifact.locator == "test://email-regex-coverage"


def test_promotion_via_external_oracle_succeeds():
    privkey, pubkey = generate_keypair()
    inference = _make_inference("the operator's tier is registered with FINRA")
    payload = jcs_canonical({
        "inference_id": inference.id,
        "content_sha256": sha256_hex(inference.content.encode("utf-8")),
        "attested_at": "2026-05-10T20:03:00.000+00:00",
    })
    sig = sign_message(privkey, payload)
    oracle = ExternalOracleAttestation(
        oracle_id="oracle://finra-test-registry",
        oracle_pubkey_hex=pubkey,
        oracle_signature_hex=sig,
        attestation_payload_sha256=sha256_hex(payload),
        attested_at="2026-05-10T20:03:00.000+00:00",
    )
    fact = promote_inference_to_fact(inference, oracle, {}, current_step_index=4)
    assert fact.verification_method == "external_oracle"
    assert fact.source_artifact.type == "oracle_id"


# ─── Promotion: rejection paths (each invariant violation has a code) ─────


def test_promotion_rejects_invalid_operator_signature():
    _, pubkey = generate_keypair()
    privkey_other, _ = generate_keypair()  # different key — wrong signer
    inference = _make_inference()
    # Sign with the WRONG private key for this pubkey
    bad_cosign = _make_operator_cosign(inference, privkey_other, pubkey)
    with pytest.raises(PromotionRejected) as exc_info:
        promote_inference_to_fact(inference, bad_cosign, {}, current_step_index=2)
    assert exc_info.value.code == "invalid_operator_signature"


def test_promotion_rejects_test_target_mismatch():
    inference = _make_inference()
    test_result = TestPassResult(
        test_id="test://some-test",
        test_target_inference_id="WRONG-INFERENCE-ID",
        test_command="pytest",
        exit_code=0,
        stdout_sha256="c" * 64,
        ran_at="2026-05-10T20:02:00.000+00:00",
    )
    with pytest.raises(PromotionRejected) as exc_info:
        promote_inference_to_fact(inference, test_result, {}, current_step_index=2)
    assert exc_info.value.code == "test_target_mismatch"


def test_promotion_rejects_test_did_not_pass():
    inference = _make_inference()
    test_result = TestPassResult(
        test_id="test://flaky-test",
        test_target_inference_id=inference.id,
        test_command="pytest",
        exit_code=1,  # FAILURE
        stdout_sha256="d" * 64,
        ran_at="2026-05-10T20:02:00.000+00:00",
    )
    with pytest.raises(PromotionRejected) as exc_info:
        promote_inference_to_fact(inference, test_result, {}, current_step_index=2)
    assert exc_info.value.code == "test_did_not_pass"


def test_promotion_rejects_invalid_oracle_signature():
    _, pubkey = generate_keypair()
    privkey_other, _ = generate_keypair()
    inference = _make_inference()
    payload = jcs_canonical({
        "inference_id": inference.id,
        "content_sha256": sha256_hex(inference.content.encode("utf-8")),
        "attested_at": "2026-05-10T20:03:00.000+00:00",
    })
    bad_sig = sign_message(privkey_other, payload)
    oracle = ExternalOracleAttestation(
        oracle_id="oracle://some-registry",
        oracle_pubkey_hex=pubkey,  # mismatched pubkey
        oracle_signature_hex=bad_sig,
        attestation_payload_sha256=sha256_hex(payload),
        attested_at="2026-05-10T20:03:00.000+00:00",
    )
    with pytest.raises(PromotionRejected) as exc_info:
        promote_inference_to_fact(inference, oracle, {}, current_step_index=2)
    assert exc_info.value.code == "invalid_oracle_signature"


def test_promotion_rejects_transitive_inference_dependency():
    # An inference that depends on an id NOT in the Facts ledger
    inference = _make_inference(depends_on=("upstream-inference-id-not-yet-promoted",))
    privkey, pubkey = generate_keypair()
    cosign = _make_operator_cosign(inference, privkey, pubkey)
    with pytest.raises(PromotionRejected) as exc_info:
        promote_inference_to_fact(inference, cosign, ledger_facts_by_id={}, current_step_index=2)
    assert exc_info.value.code == "transitive_inference_dependency"


def test_promotion_accepts_when_dependency_already_a_fact():
    upstream_fact = Fact(
        content="schema X exists in production",
        source_artifact=SourceArtifact(
            type="test_id",
            locator="test://schema-check",
            content_hash="e" * 64,
        ),
        verified_at="2026-05-10T19:00:00.000+00:00",
        verification_method="test_pass",
        created_at_step=1,
    )
    inference = _make_inference(depends_on=(upstream_fact.id,))
    privkey, pubkey = generate_keypair()
    cosign = _make_operator_cosign(inference, privkey, pubkey)
    fact = promote_inference_to_fact(
        inference,
        cosign,
        ledger_facts_by_id={upstream_fact.id: upstream_fact},
        current_step_index=2,
    )
    assert fact.kind == "fact"
    assert upstream_fact.id in fact.depends_on


# ─── Step boundary seal: invariant enforcement ────────────────────────────


def _make_unknown(text: str = "schema drift since last audit unknown") -> Unknown:
    return Unknown(
        question=text,
        cost_of_ignorance="migration may acquire long lock if schema drifted",
        created_at_step=1,
    )


def _make_assumption() -> Assumption:
    return Assumption(
        assumption="read replicas will fail over within 1s",
        if_wrong_then="user-facing latency spike during migration window",
        detectability="post_execution_soft",
        created_at_step=1,
    )


def _make_fact(content: str = "test passed on staging mirror") -> Fact:
    return Fact(
        content=content,
        source_artifact=SourceArtifact(
            type="test_id",
            locator="test://staging-dry-run",
            content_hash="f" * 64,
        ),
        verified_at="2026-05-10T19:00:00.000+00:00",
        verification_method="test_pass",
        created_at_step=1,
    )


def test_seal_first_step_succeeds():
    fact = _make_fact()
    boundary = seal_step_boundary(
        session_id="session-001",
        step_index=1,
        parent_boundary=None,
        knowns=[fact],
        inferences=[],
        unknowns=[_make_unknown()],
        assumptions=[_make_assumption()],
    )
    assert boundary.step_index == 1
    assert boundary.parent_hash is None
    assert len(boundary.self_hash) == 64  # SHA-256 hex


def test_seal_rejects_ledger_overlap_I1():
    fact = _make_fact()
    inf = _make_inference()
    # Forge an inference with same id as a fact — should raise I1
    inf_with_collision = Inference(
        content=inf.content,
        generated_by=inf.generated_by,
        generated_at=inf.generated_at,
        created_at_step=inf.created_at_step,
        confidence_self_reported=inf.confidence_self_reported,
        id=fact.id,  # COLLISION
    )
    with pytest.raises(ImmutableLedgerError, match="I1 violation"):
        seal_step_boundary(
            session_id="session-001",
            step_index=1,
            parent_boundary=None,
            knowns=[fact],
            inferences=[inf_with_collision],
            unknowns=[],
            assumptions=[],
        )


def test_seal_rejects_fact_depending_on_non_fact_I3():
    bad_fact = Fact(
        content="some derived fact",
        source_artifact=SourceArtifact(
            type="test_id", locator="test://x", content_hash="g" * 64,
        ),
        verified_at="2026-05-10T19:00:00.000+00:00",
        verification_method="test_pass",
        created_at_step=1,
        depends_on=("some-id-that-isnt-in-knowns",),
    )
    with pytest.raises(ImmutableLedgerError, match="I3 violation"):
        seal_step_boundary(
            session_id="session-001",
            step_index=1,
            parent_boundary=None,
            knowns=[bad_fact],
            inferences=[],
            unknowns=[],
            assumptions=[],
        )


def test_seal_rejects_parent_knowns_dropped_I4():
    parent_fact = _make_fact("parent fact retained across steps")
    parent = seal_step_boundary(
        session_id="session-001",
        step_index=1,
        parent_boundary=None,
        knowns=[parent_fact],
        inferences=[],
        unknowns=[],
        assumptions=[],
    )
    # Step 2 drops parent_fact — should violate I4
    with pytest.raises(ImmutableLedgerError, match="I4 violation"):
        seal_step_boundary(
            session_id="session-001",
            step_index=2,
            parent_boundary=parent,
            knowns=[],  # parent_fact dropped
            inferences=[],
            unknowns=[],
            assumptions=[],
        )


def test_seal_chains_self_hash_to_parent_I5():
    parent = seal_step_boundary(
        session_id="session-001",
        step_index=1,
        parent_boundary=None,
        knowns=[_make_fact()],
        inferences=[],
        unknowns=[],
        assumptions=[],
    )
    child = seal_step_boundary(
        session_id="session-001",
        step_index=2,
        parent_boundary=parent,
        knowns=list(parent.knowns),
        inferences=[],
        unknowns=[],
        assumptions=[],
    )
    assert child.parent_hash == parent.self_hash


# ─── Context injection: typed tags ────────────────────────────────────────


def test_render_step_context_tags_facts_and_inferences_distinctly():
    from core.ptsp.context_injection import render_step_context

    fact = _make_fact("verified fact content")
    inf = _make_inference("speculative model output")
    boundary = seal_step_boundary(
        session_id="session-001",
        step_index=1,
        parent_boundary=None,
        knowns=[fact],
        inferences=[inf],
        unknowns=[_make_unknown()],
        assumptions=[_make_assumption()],
    )
    rendered = render_step_context(boundary)
    # Facts and inferences MUST appear under different tags
    assert "<fact " in rendered
    assert "<inference " in rendered
    assert "verified fact content" in rendered
    assert "speculative model output" in rendered
    # Their tags must NOT be swappable: an inference tag should never appear
    # inside the <facts> block.
    facts_start = rendered.find("<facts>")
    facts_end = rendered.find("</facts>")
    facts_block = rendered[facts_start:facts_end]
    assert "<inference" not in facts_block
