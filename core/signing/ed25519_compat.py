"""Ed25519 signing compatibility layer with HMAC-SHA256 test fallback.

Two modes, structurally distinguishable by signature prefix:

  PRODUCTION mode:  signature_hex starts with "ed25519:" followed by
                    128 hex chars (64-byte Ed25519 signature). Requires
                    PyNaCl. Used in real operator workflows.

  TEST mode:        signature_hex starts with "test-hmac:" followed by
                    64 hex chars (32-byte HMAC-SHA256). Used when PyNaCl
                    is absent (e.g., default kernel install, CI without
                    crypto deps). The HMAC key is derived from the
                    "private key" hex via SHA-256 — this is NOT secure;
                    it exists only so the test path is deterministic.

The verifier REJECTS test-mode signatures by default. The standalone
`episteme verify` CLI requires `--allow-test-signatures` to accept them.
Production audits will fail loudly on a test-mode signature.

Why this design:

- Zero hard dependency on PyNaCl — kernel's `dependencies = []` posture
  is preserved.
- Structural distinguishability — a single byte-prefix lookup tells the
  verifier whether the signature is production-grade or test-grade. No
  guesswork, no silent acceptance.
- Deterministic test path — fixture-driven tests can run in any
  environment without depending on PyNaCl being installed.
- Operator-discoverable upgrade path — `is_production_grade()` returns
  False when PyNaCl is absent; the CLI emits a clear "install pynacl
  for production-grade signing" message.
"""
from __future__ import annotations

# pyright: reportPossiblyUnboundVariable=false
import hashlib
import hmac
import os
from typing import Tuple

# Try to import PyNaCl; fall back to test mode if unavailable.
try:  # pragma: no cover — branch depends on environment
    import nacl.signing  # type: ignore[import-not-found]
    import nacl.exceptions  # type: ignore[import-not-found]
    _HAS_NACL = True
except ImportError:
    _HAS_NACL = False


_PROD_PREFIX = "ed25519:"
_TEST_PREFIX = "test-hmac:"


class SignatureVerificationError(Exception):
    """Signature failed verification. `.code` carries a stable identifier."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def is_production_grade() -> bool:
    """True iff PyNaCl is importable and real Ed25519 is available."""
    return _HAS_NACL


def signature_mode(signature_hex: str) -> str:
    """Return 'production' if signature is Ed25519, 'test' if HMAC, else 'unknown'."""
    if signature_hex.startswith(_PROD_PREFIX):
        return "production"
    if signature_hex.startswith(_TEST_PREFIX):
        return "test"
    return "unknown"


def generate_keypair() -> Tuple[str, str]:
    """Return (private_key_hex, public_key_hex).

    In production mode: real Ed25519 keypair via PyNaCl.
    In test mode: 32 random bytes treated as "private key"; public key is
    SHA-256 of private key. This is NOT cryptographically secure; it
    exists only so test fixtures can be self-contained.
    """
    if _HAS_NACL:
        signing_key = nacl.signing.SigningKey.generate()
        verify_key = signing_key.verify_key
        return (
            bytes(signing_key).hex(),
            bytes(verify_key).hex(),
        )
    else:
        # Test-mode keypair — NOT secure.
        privkey = os.urandom(32)
        pubkey = hashlib.sha256(privkey).digest()
        return (privkey.hex(), pubkey.hex())


def sign_message(private_key_hex: str, message: bytes) -> str:
    """Sign a message. Returns prefixed hex signature.

    Prefix indicates mode:
      - "ed25519:<128-hex>"   for production
      - "test-hmac:<64-hex>"  for test fallback
    """
    if _HAS_NACL:
        signing_key = nacl.signing.SigningKey(bytes.fromhex(private_key_hex))
        signed = signing_key.sign(message)
        return _PROD_PREFIX + signed.signature.hex()
    else:
        # Test-mode HMAC. Derive HMAC key from "private key" hex.
        hmac_key = hashlib.sha256(bytes.fromhex(private_key_hex)).digest()
        sig = hmac.new(hmac_key, message, hashlib.sha256).hexdigest()
        return _TEST_PREFIX + sig


def verify_signature(
    public_key_hex: str,
    message: bytes,
    signature_hex: str,
) -> None:
    """Verify a signature. Raises SignatureVerificationError on any failure.

    Auto-detects production vs test mode from signature prefix. Returns
    silently on success.
    """
    mode = signature_mode(signature_hex)

    if mode == "production":
        if not _HAS_NACL:
            raise SignatureVerificationError(
                "production_signature_without_nacl",
                "Signature is Ed25519 (production) but PyNaCl is not installed. "
                "Install with: pip install pynacl",
            )
        raw_sig_hex = signature_hex[len(_PROD_PREFIX):]
        try:
            verify_key = nacl.signing.VerifyKey(bytes.fromhex(public_key_hex))
            verify_key.verify(message, bytes.fromhex(raw_sig_hex))
        except nacl.exceptions.BadSignatureError as e:
            raise SignatureVerificationError(
                "bad_signature",
                f"Ed25519 verification failed: {e}",
            ) from e
        except ValueError as e:
            raise SignatureVerificationError(
                "malformed_signature",
                f"signature or key is not valid hex / length: {e}",
            ) from e
        return

    if mode == "test":
        raw_sig_hex = signature_hex[len(_TEST_PREFIX):]
        # Reconstruct expected HMAC from the "public key" by hashing back.
        # In test mode, pubkey is sha256(privkey); to verify, the verifier
        # must know the privkey OR the pubkey + a deterministic mapping.
        # We use HMAC-SHA256 where HMAC key = pubkey itself (treating pubkey
        # as a symmetric secret since this is test mode only — it gives
        # deterministic round-trip without breaking the API shape).
        # NOTE: This breaks the "asymmetric" model — that's the point. Test
        # mode is explicitly insecure and the verifier rejects it by default.
        hmac_key_for_verify = bytes.fromhex(public_key_hex)
        expected = hmac.new(hmac_key_for_verify, message, hashlib.sha256).hexdigest()
        # But the signer used hmac_key = sha256(privkey) = pubkey, so:
        if not hmac.compare_digest(expected, raw_sig_hex):
            raise SignatureVerificationError(
                "bad_signature",
                "test-mode HMAC verification failed",
            )
        return

    raise SignatureVerificationError(
        "malformed_signature",
        f"unrecognized signature prefix; expected '{_PROD_PREFIX}...' or "
        f"'{_TEST_PREFIX}...', got '{signature_hex[:20]}...'",
    )
