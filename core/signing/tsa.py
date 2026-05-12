"""RFC 3161 Time-Stamp Authority shape — mock implementation for v1.

In production, the TSA token field would carry a real RFC 3161 TimeStampToken
issued by a third-party TSA (FreeTSA, Apple TSS, DigiCert, etc.). Live TSA
integration is gated on operator decision (which TSA endpoint to commit to,
and whether the TSA root CA bundle is acceptable for the deployment).

This module provides:
  - The TSAToken typed shape — what every signed surface carries
  - A `mock_tsa_token` function that produces a deterministic test-mode
    token, suitable for test fixtures
  - A `verify_tsa_token` function that validates the shape + (in mock mode)
    a deterministic round-trip

The mock token's `mode` field is "test"; production tokens carry "rfc3161".
The verifier in `episteme verify` rejects mock tokens by default unless
`--allow-test-signatures` is passed, matching the Ed25519 fallback policy.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import hashlib
import hmac
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict


_MOCK_TSA_KEY = b"episteme-mock-tsa-key-v1-NOT-FOR-PRODUCTION"


@dataclass(frozen=True, slots=True)
class TSAToken:
    """Typed wrapper over the RFC 3161 token field of a SignedSurface."""
    tsa_url: str
    tsa_token_b64: str
    tsa_certificate_chain_pem_sha256: str
    asserted_timestamp: str
    mode: str  # "rfc3161" | "test"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TSAVerificationError(Exception):
    pass


def mock_tsa_token(payload_hash_hex: str) -> Dict[str, Any]:
    """Produce a deterministic test-mode TSA token over a payload hash.

    The token body is HMAC-SHA256(payload_hash, _MOCK_TSA_KEY), encoded as
    hex inside the `tsa_token_b64` slot. Real RFC 3161 tokens would be
    base64-encoded ASN.1; the test mode uses a string-typed-but-not-real
    shape to keep the field shape stable across modes.
    """
    asserted_ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    body = hmac.new(_MOCK_TSA_KEY, payload_hash_hex.encode("ascii"), hashlib.sha256).hexdigest()
    return TSAToken(
        tsa_url="mock://episteme.test/tsa",
        tsa_token_b64=f"test-tsa:{body}",
        tsa_certificate_chain_pem_sha256="0" * 64,  # placeholder; real chain is loaded from TSA root bundle
        asserted_timestamp=asserted_ts,
        mode="test",
    ).to_dict()


def verify_tsa_token(token: Dict[str, Any], payload_hash_hex: str) -> None:
    """Verify a TSA token against a payload hash.

    Raises TSAVerificationError on failure. In test mode, recomputes the
    HMAC; in production mode (rfc3161), would parse and verify the ASN.1
    token against trusted TSA roots — that path is gated on operator
    decision and lives behind a "production_tsa" flag.
    """
    for required in ("tsa_url", "tsa_token_b64", "asserted_timestamp", "mode"):
        if required not in token:
            raise TSAVerificationError(f"missing TSA token field: {required}")

    mode = token["mode"]
    if mode == "test":
        prefix = "test-tsa:"
        token_b64 = token["tsa_token_b64"]
        if not token_b64.startswith(prefix):
            raise TSAVerificationError(f"test-mode token does not start with '{prefix}' prefix")
        body = token_b64[len(prefix):]
        expected = hmac.new(_MOCK_TSA_KEY, payload_hash_hex.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, body):
            raise TSAVerificationError("test-mode TSA HMAC mismatch")
        return

    if mode == "rfc3161":
        # Production path — would invoke a real ASN.1 parser and TSA root
        # bundle verification. Not implemented in v1; gated on operator
        # decision (which TSA endpoint to commit to + cert bundle).
        raise TSAVerificationError(
            "rfc3161 TSA verification not implemented in v1; install operator-"
            "approved TSA verifier and pass via verify_tsa_fn argument"
        )

    raise TSAVerificationError(f"unrecognized TSA mode: {mode}")
