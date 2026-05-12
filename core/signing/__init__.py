"""Cryptographic signing primitives for the Signed Reasoning Surface.

This module is the load-bearing crypto layer of episteme's Compliance
Evidence Layer claim. It exists to make the operator-authorship requirement
structurally verifiable — without these primitives, the "operator-signed,
not LLM-generated" guarantee collapses to a policy promise.

Design constraints:

1. Zero hard dependencies. The episteme kernel ships with `dependencies = []`
   in pyproject.toml — adding a crypto library (PyNaCl or `cryptography`) as
   a hard requirement violates that posture without operator approval.
2. Production-grade when PyNaCl is available. If `pip install pynacl` has
   been run, real Ed25519 signatures are used.
3. Test-grade fallback when PyNaCl is absent. HMAC-SHA256 signatures with
   an explicit `MODE=TEST` marker, deterministic for fixture-driven tests.
4. Verifier MUST reject test-mode signatures by default. The standalone
   `episteme verify` CLI requires `--allow-test-signatures` to accept them
   — production audits will reject the entire packet on a test-mode hit.

This is NOT crypto-rolled-our-own. The HMAC-SHA256 fallback uses Python's
stdlib `hmac` module; it is well-tested. What we are explicitly NOT doing
is rolling our own Ed25519 in pure Python — that path is fragile and
should not exist in a Compliance Evidence Layer.

Public API:
- `verify_signature(pubkey_hex, message, signature_hex)` — raises on failure
- `sign_message(privkey_hex, message)` — returns hex signature
- `generate_keypair()` — returns (privkey_hex, pubkey_hex)
- `is_production_grade()` — True iff PyNaCl is importable
- `signature_mode(signature_hex)` — "production" | "test"
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from core.signing.ed25519_compat import (
    SignatureVerificationError,
    generate_keypair,
    is_production_grade,
    signature_mode,
    sign_message,
    verify_signature,
)
from core.signing.canonical_surface import (
    SignedSurface,
    SurfaceVerificationError,
    canonical_payload,
    sign_surface,
    verify_surface,
)
from core.signing.tsa import TSAToken, mock_tsa_token, verify_tsa_token
from core.signing.transparency import (
    RekorInclusionProof,
    build_inclusion_proof_shape,
    verify_inclusion_proof_shape,
)

__all__ = [
    # Ed25519 compat layer
    "SignatureVerificationError",
    "generate_keypair",
    "is_production_grade",
    "signature_mode",
    "sign_message",
    "verify_signature",
    # Canonical surface
    "SignedSurface",
    "SurfaceVerificationError",
    "canonical_payload",
    "sign_surface",
    "verify_surface",
    # TSA (RFC 3161 shape)
    "TSAToken",
    "mock_tsa_token",
    "verify_tsa_token",
    # Transparency log (Rekor shape)
    "RekorInclusionProof",
    "build_inclusion_proof_shape",
    "verify_inclusion_proof_shape",
]
