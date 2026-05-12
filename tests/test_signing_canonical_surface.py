"""Tests for core/signing/ — sign/verify roundtrip and tamper detection.

Uses the HMAC-SHA256 test fallback when PyNaCl is unavailable. The verifier
explicitly rejects test-mode signatures by default; tests exercise both the
strict-mode rejection and the `allow_test_signatures=True` round-trip.
"""
from __future__ import annotations

import json
from typing import Any, Dict

import pytest

from core.signing import (
    SurfaceVerificationError,
    build_inclusion_proof_shape,
    canonical_payload,
    generate_keypair,
    mock_tsa_token,
    sign_surface,
    signature_mode,
    verify_inclusion_proof_shape,
    verify_surface,
    verify_tsa_token,
)

from core.ptsp.canonical import sha256_hex as _sha256_hex
from core.signing.canonical_surface import SCHEMA_VERSION


# Local alias for legacy test snippets
sha256_hex = _sha256_hex


# ─── Fixtures ─────────────────────────────────────────────────────────────


def _surface_body() -> Dict[str, Any]:
    return {
        "core_question": "Should I run the migration on prod now?",
        "risk_classification": {
            "reversibility": "irreversible",
            "blast_radius": "regulated_artifact",
            "ai_act_tier": "high",
            "article_79_1_triggers": ["material_user_impact"],
        },
        "knowns": [{"fact": "staging dry-run passed", "source_artifact": "test://x", "verified_at": "2026-05-10T19:00:00.000+00:00", "verification_method": "test_pass"}],
        "unknowns": [{"unknown": "out-of-band schema drift in last 30d", "why_not_resolvable_now": "audit log retention gap", "cost_of_ignorance": "lock duration unbounded"}],
        "assumptions": [{"assumption": "replicas fail over within 1s", "if_wrong_then": "p99 spike", "detectability": "post_execution_soft"}],
        "disconfirmation_conditions": [{"observable": "lock_wait_seconds > 0.5 in first 5s", "measurement_method": "pg_stat_activity 1Hz", "would_invalidate_plan": True}],
        "decision": {"choice": "proceed", "confidence": 0.78, "confidence_elicitation_method": "written_probability_estimate", "stop_rollback_path": "pg_cancel_backend on migration pid"},
        "audit": {"blueprint_invoked": "consequence_chain", "validation_layers_passed": ["presence", "freshness", "signature"]},
    }


def _resolver_for(pubkey_hex: str):
    """Build a resolver that maps the fingerprint to pubkey for one key."""
    fp = _sha256_hex(bytes.fromhex(pubkey_hex))
    def resolver(fingerprint: str) -> str:
        if fingerprint != fp:
            raise KeyError(f"unknown fingerprint {fingerprint}")
        return pubkey_hex
    return resolver


# ─── Roundtrip ────────────────────────────────────────────────────────────


def test_sign_verify_roundtrip_passes():
    privkey, pubkey = generate_keypair()
    body = _surface_body()
    signed = sign_surface(
        surface=body,
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="surface-001",
        session_id="session-001",
    )
    verify_surface(
        signed.to_dict(),
        public_key_resolver=_resolver_for(pubkey),
        allow_test_signatures=True,
    )


def test_sign_verify_with_tsa_and_rekor():
    privkey, pubkey = generate_keypair()
    body = _surface_body()
    payload_hash = sha256_hex(canonical_payload(
        {
            "schema_version": SCHEMA_VERSION,
            "surface_id": "surface-001",
            "session_id": "session-001",
            "operator_pubkey_fingerprint": _sha256_hex(bytes.fromhex(pubkey)),
            "parent_surface_hash": None,
            "issued_at": "2026-05-10T20:00:00.000+00:00",
        },
        body,
    ))
    tsa = mock_tsa_token(payload_hash)
    rekor = build_inclusion_proof_shape(payload_hash, log_index=42)

    signed = sign_surface(
        surface=body,
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="surface-001",
        session_id="session-001",
        issued_at="2026-05-10T20:00:00.000+00:00",
        tsa_token=tsa,
        rekor_inclusion_proof=rekor,
    )

    verify_surface(
        signed.to_dict(),
        public_key_resolver=_resolver_for(pubkey),
        allow_test_signatures=True,
        verify_tsa_fn=verify_tsa_token,
        verify_rekor_fn=verify_inclusion_proof_shape,
    )


# ─── Test-mode rejection by default ───────────────────────────────────────


def test_verify_rejects_test_signatures_by_default():
    privkey, pubkey = generate_keypair()
    signed = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="surface-001",
        session_id="session-001",
    )
    # signature_mode is "test" since PyNaCl is unavailable in default env
    assert signature_mode(signed.attestation["signature_b64_or_hex"]) == "test"
    with pytest.raises(SurfaceVerificationError) as exc_info:
        verify_surface(
            signed.to_dict(),
            public_key_resolver=_resolver_for(pubkey),
            allow_test_signatures=False,
        )
    assert exc_info.value.exit_code == 10
    assert exc_info.value.code == "test_signature_rejected"


# ─── Tamper detection ─────────────────────────────────────────────────────


def test_tamper_in_surface_body_detected():
    privkey, pubkey = generate_keypair()
    signed = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="surface-001",
        session_id="session-001",
    )
    tampered = signed.to_dict()
    # Mutate the decision after sign — payload hash will no longer match.
    tampered["surface"]["decision"]["choice"] = "stop"

    with pytest.raises(SurfaceVerificationError) as exc_info:
        verify_surface(
            tampered,
            public_key_resolver=_resolver_for(pubkey),
            allow_test_signatures=True,
        )
    # Either signature_invalid (10) or self_hash_mismatch (14) depending on
    # which layer trips first. Both indicate detected tamper.
    assert exc_info.value.exit_code in (10, 14)


def test_tamper_in_envelope_detected():
    privkey, pubkey = generate_keypair()
    signed = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="surface-001",
        session_id="session-001",
    )
    tampered = signed.to_dict()
    tampered["envelope"]["session_id"] = "DIFFERENT-SESSION"

    with pytest.raises(SurfaceVerificationError) as exc_info:
        verify_surface(
            tampered,
            public_key_resolver=_resolver_for(pubkey),
            allow_test_signatures=True,
        )
    assert exc_info.value.exit_code in (10, 14)


def test_signature_swap_to_other_key_detected():
    privkey_a, pubkey_a = generate_keypair()
    _, pubkey_b = generate_keypair()
    signed = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey_a,
        public_key_hex=pubkey_a,
        surface_id="surface-001",
        session_id="session-001",
    )
    # Swap fingerprint to a different key
    tampered = signed.to_dict()
    tampered["envelope"]["operator_pubkey_fingerprint"] = _sha256_hex(bytes.fromhex(pubkey_b))

    resolver_b = _resolver_for(pubkey_b)
    with pytest.raises(SurfaceVerificationError) as exc_info:
        verify_surface(
            tampered,
            public_key_resolver=resolver_b,
            allow_test_signatures=True,
        )
    # Signature verification will fail under the wrong pubkey
    assert exc_info.value.exit_code in (10, 14)


def test_missing_fields_yield_malformed_exit_20():
    bad = {"envelope": {}, "surface": {}, "attestation": {}, "self_hash": ""}
    with pytest.raises(SurfaceVerificationError) as exc_info:
        verify_surface(bad, public_key_resolver=lambda fp: "00" * 32, allow_test_signatures=True)
    assert exc_info.value.exit_code == 20


def test_unresolvable_key_yields_exit_21():
    privkey, pubkey = generate_keypair()
    signed = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="surface-001",
        session_id="session-001",
    )

    def failing_resolver(fp: str) -> str:
        raise FileNotFoundError(f"no key for {fp}")

    with pytest.raises(SurfaceVerificationError) as exc_info:
        verify_surface(
            signed.to_dict(),
            public_key_resolver=failing_resolver,
            allow_test_signatures=True,
        )
    assert exc_info.value.exit_code == 21


# ─── JSON serialization round-trip ────────────────────────────────────────


def test_signed_surface_to_json_and_back_verifies():
    privkey, pubkey = generate_keypair()
    signed = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="surface-001",
        session_id="session-001",
    )
    serialized = signed.to_json()
    deserialized = json.loads(serialized)
    verify_surface(
        deserialized,
        public_key_resolver=_resolver_for(pubkey),
        allow_test_signatures=True,
    )
