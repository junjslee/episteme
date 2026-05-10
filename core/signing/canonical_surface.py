"""Signed Reasoning Surface — canonical payload, sign, verify.

The Signed Reasoning Surface is the v1.0 envelope that wraps the existing
`reasoning-surface@1` body with cryptographic provenance:

  envelope.{schema_version, surface_id, session_id,
            operator_pubkey_fingerprint, parent_surface_hash, issued_at}
  surface.{...payload of the operator's reasoning surface...}
  attestation.{signature_alg, signature, signed_at,
               tsa.{token shape}, transparency_log.{inclusion proof shape}}
  self_hash

Canonicalization order:

  canonical_payload   = JCS(envelope ∪ surface)
  signature_input     = canonical_payload                  (signed)
  tsa_input           = SHA-256(canonical_payload)         (timestamped)
  rekor_entry         = {sig, pubkey, payload_sha256}
  self_hash           = SHA-256(canonical_payload || signature_bytes ||
                                tsa_token_bytes || rekor_proof_bytes)

This module provides:
  - `canonical_payload(envelope, surface)` — pure function
  - `sign_surface(envelope, surface, private_key_hex)` — returns SignedSurface
  - `verify_surface(signed_surface, public_key_resolver)` — raises on failure
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from core.ptsp.canonical import jcs_canonical, sha256_hex
from core.signing.ed25519_compat import (
    SignatureVerificationError,
    sign_message,
    signature_mode,
    verify_signature,
)


SCHEMA_VERSION = "signed-surface@1.0"


# ─── Surface envelope dataclass ───────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class SignedSurface:
    envelope: Dict[str, Any]
    surface: Dict[str, Any]
    attestation: Dict[str, Any]
    self_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "envelope": dict(self.envelope),
            "surface": dict(self.surface),
            "attestation": dict(self.attestation),
            "self_hash": self.self_hash,
        }

    def to_json(self, *, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, ensure_ascii=False)


# ─── Canonical payload ────────────────────────────────────────────────────

def canonical_payload(envelope: Dict[str, Any], surface: Dict[str, Any]) -> bytes:
    """JCS-canonical bytes of {envelope, surface}.

    This is the byte sequence that gets signed AND timestamped AND included
    in the transparency log. A one-byte change here invalidates the entire
    attestation chain — that is the tamper-detection signal.
    """
    return jcs_canonical({"envelope": envelope, "surface": surface})


def _pubkey_fingerprint(public_key_hex: str) -> str:
    """SHA-256 hex of the public key bytes — the canonical fingerprint."""
    return sha256_hex(bytes.fromhex(public_key_hex))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# ─── Sign ─────────────────────────────────────────────────────────────────

def sign_surface(
    *,
    surface: Dict[str, Any],
    private_key_hex: str,
    public_key_hex: str,
    surface_id: str,
    session_id: str,
    parent_surface_hash: Optional[str] = None,
    issued_at: Optional[str] = None,
    tsa_token: Optional[Dict[str, Any]] = None,
    rekor_inclusion_proof: Optional[Dict[str, Any]] = None,
) -> SignedSurface:
    """Sign a Reasoning Surface body and return the SignedSurface wrapper.

    `tsa_token` and `rekor_inclusion_proof` are passed in pre-built; this
    module does not call external services. The mock TSA and shape-only
    Rekor helpers live in `core.signing.tsa` and `core.signing.transparency`
    so test fixtures and live integrations both go through them.
    """
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "surface_id": surface_id,
        "session_id": session_id,
        "operator_pubkey_fingerprint": _pubkey_fingerprint(public_key_hex),
        "parent_surface_hash": parent_surface_hash,
        "issued_at": issued_at or _now_iso(),
    }

    payload_bytes = canonical_payload(envelope, surface)
    payload_hash = sha256_hex(payload_bytes)

    signature = sign_message(private_key_hex, payload_bytes)
    signed_at = _now_iso()

    attestation: Dict[str, Any] = {
        "signature_alg": "Ed25519" if signature.startswith("ed25519:") else "HMAC-SHA256-TEST",
        "signature_b64_or_hex": signature,
        "signed_at": signed_at,
        "payload_sha256": payload_hash,
        "tsa": tsa_token,
        "transparency_log": rekor_inclusion_proof,
    }

    # self_hash binds payload + attestation together
    self_hash_input = jcs_canonical({
        "payload_sha256": payload_hash,
        "signature": signature,
        "tsa": tsa_token,
        "transparency_log": rekor_inclusion_proof,
    })
    self_hash = sha256_hex(self_hash_input)

    return SignedSurface(
        envelope=envelope,
        surface=surface,
        attestation=attestation,
        self_hash=self_hash,
    )


# ─── Verify ───────────────────────────────────────────────────────────────

class SurfaceVerificationError(Exception):
    """Container error for verify_surface failures. `.exit_code` matches
    the standalone CLI's deterministic exit code contract."""

    def __init__(self, exit_code: int, code: str, detail: str = ""):
        super().__init__(f"[exit={exit_code}] {code}: {detail}" if detail else f"[exit={exit_code}] {code}")
        self.exit_code = exit_code
        self.code = code
        self.detail = detail


def verify_surface(
    signed_surface: Dict[str, Any],
    *,
    public_key_resolver: Optional[Callable[[str], str]] = None,
    allow_test_signatures: bool = False,
    verify_tsa_fn: Optional[Callable[[Dict[str, Any], str], None]] = None,
    verify_rekor_fn: Optional[Callable[[Dict[str, Any], str], None]] = None,
) -> None:
    """Verify a SignedSurface dict end-to-end.

    Raises SurfaceVerificationError on any failure. Returns silently on
    success. The exit_code attribute on the error matches the standalone
    CLI's deterministic exit code contract:

      10 — signature invalid
      11 — timestamp invalid
      12 — transparency log inclusion failed
      13 — hash chain break (caller's responsibility; not checked here)
      14 — self_hash mismatch
      20 — surface file malformed / schema-invalid
      21 — required key resolution failed
    """
    # ── Schema shape check ──
    for required in ("envelope", "surface", "attestation", "self_hash"):
        if required not in signed_surface:
            raise SurfaceVerificationError(20, "malformed_surface", f"missing top-level field '{required}'")

    envelope = signed_surface["envelope"]
    surface = signed_surface["surface"]
    attestation = signed_surface["attestation"]
    self_hash = signed_surface["self_hash"]

    for required in ("schema_version", "surface_id", "session_id", "operator_pubkey_fingerprint", "issued_at"):
        if required not in envelope:
            raise SurfaceVerificationError(20, "malformed_surface", f"missing envelope.{required}")

    for required in ("signature_b64_or_hex", "signed_at", "payload_sha256"):
        if required not in attestation:
            raise SurfaceVerificationError(20, "malformed_surface", f"missing attestation.{required}")

    # ── Test-signature gating ──
    sig_mode = signature_mode(attestation["signature_b64_or_hex"])
    if sig_mode == "test" and not allow_test_signatures:
        raise SurfaceVerificationError(
            10,
            "test_signature_rejected",
            "signature is test-mode HMAC; verifier rejects by default. "
            "Pass --allow-test-signatures to accept (NOT for production audit).",
        )

    # ── Recompute payload bytes and check hash ──
    payload_bytes = canonical_payload(envelope, surface)
    recomputed_payload_hash = sha256_hex(payload_bytes)
    if recomputed_payload_hash != attestation["payload_sha256"]:
        raise SurfaceVerificationError(
            14,
            "self_hash_mismatch",
            "payload SHA-256 in attestation does not match recomputed canonical payload hash",
        )

    # ── Resolve public key ──
    fingerprint = envelope["operator_pubkey_fingerprint"]
    if public_key_resolver is None:
        raise SurfaceVerificationError(
            21,
            "key_resolution_failed",
            "no public_key_resolver provided; cannot resolve fingerprint to pubkey",
        )
    try:
        pubkey_hex = public_key_resolver(fingerprint)
    except Exception as e:
        raise SurfaceVerificationError(21, "key_resolution_failed", str(e)) from e

    # Defensive: confirm fingerprint matches resolved pubkey
    if _pubkey_fingerprint(pubkey_hex) != fingerprint:
        raise SurfaceVerificationError(
            21,
            "key_resolution_failed",
            "resolved pubkey does not match envelope fingerprint",
        )

    # ── Verify signature ──
    try:
        verify_signature(pubkey_hex, payload_bytes, attestation["signature_b64_or_hex"])
    except SignatureVerificationError as e:
        raise SurfaceVerificationError(10, "signature_invalid", str(e)) from e

    # ── Verify TSA (if present and verifier provided) ──
    tsa_token = attestation.get("tsa")
    if tsa_token is not None and verify_tsa_fn is not None:
        try:
            verify_tsa_fn(tsa_token, recomputed_payload_hash)
        except Exception as e:
            raise SurfaceVerificationError(11, "timestamp_invalid", str(e)) from e

    # ── Verify Rekor inclusion (if present and verifier provided) ──
    rekor_proof = attestation.get("transparency_log")
    if rekor_proof is not None and verify_rekor_fn is not None:
        try:
            verify_rekor_fn(rekor_proof, recomputed_payload_hash)
        except Exception as e:
            raise SurfaceVerificationError(12, "log_inclusion_invalid", str(e)) from e

    # ── Verify self_hash ──
    expected_self_hash_input = jcs_canonical({
        "payload_sha256": recomputed_payload_hash,
        "signature": attestation["signature_b64_or_hex"],
        "tsa": tsa_token,
        "transparency_log": rekor_proof,
    })
    expected_self_hash = sha256_hex(expected_self_hash_input)
    if expected_self_hash != self_hash:
        raise SurfaceVerificationError(
            14,
            "self_hash_mismatch",
            "self_hash does not match recomputed attestation hash",
        )
