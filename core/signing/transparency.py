"""Sigstore Rekor transparency log — shape-only implementation for v1.

In production, every signed surface would be appended to a Sigstore Rekor
log (or self-hosted append-only Merkle log), and the inclusion proof
returned by the log would be attached to the signed surface. Live Rekor
integration is gated on operator decision (which transparency log substrate
to commit to: Sigstore public vs self-hosted vs none).

This module provides the typed shape and a deterministic mock for test
fixtures. The verifier in `episteme verify` rejects mock proofs by default
unless `--allow-test-signatures` is passed, matching the Ed25519/TSA policy.

When live Rekor integration ships in a separate Event, the production path
will call `rekor.sigstore.dev/api/v1/log/entries` with the signature, public
key, and payload hash; the returned `logIndex` and inclusion proof will be
embedded into the SignedSurface's `attestation.transparency_log` field. The
verifier will then fetch the log's current tree root and re-verify the
Merkle proof against it.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import hashlib
import hmac
from dataclasses import dataclass, asdict
from typing import Any, Dict, List


_MOCK_LOG_KEY = b"episteme-mock-rekor-key-v1-NOT-FOR-PRODUCTION"


@dataclass(frozen=True, slots=True)
class RekorInclusionProof:
    log_id: str
    log_index: int
    log_uuid: str
    tree_size: int
    tree_root_hash: str
    inclusion_path: List[str]  # sibling hashes from leaf to root
    mode: str  # "rekor" | "test"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RekorVerificationError(Exception):
    pass


def build_inclusion_proof_shape(payload_hash_hex: str, log_index: int = 0) -> Dict[str, Any]:
    """Build a deterministic test-mode inclusion proof for a payload hash.

    NOT a real Merkle proof — the `inclusion_path` is a fixed-length list
    of HMAC-derived hashes that round-trip with `verify_inclusion_proof_shape`.
    The shape matches what a real Sigstore Rekor response would carry, so
    the SignedSurface schema is stable across modes.
    """
    body = hmac.new(_MOCK_LOG_KEY, payload_hash_hex.encode("ascii"), hashlib.sha256).hexdigest()
    # Deterministic mock "inclusion path" — 3 sibling hashes, derived
    sibling_1 = hashlib.sha256((body + ":1").encode()).hexdigest()
    sibling_2 = hashlib.sha256((body + ":2").encode()).hexdigest()
    sibling_3 = hashlib.sha256((body + ":3").encode()).hexdigest()
    # Mock tree root = HMAC of the path
    mock_root = hmac.new(
        _MOCK_LOG_KEY,
        ":".join([sibling_1, sibling_2, sibling_3, body]).encode("ascii"),
        hashlib.sha256,
    ).hexdigest()

    return RekorInclusionProof(
        log_id="mock://episteme.test/rekor",
        log_index=log_index,
        log_uuid=f"test-{body[:16]}",
        tree_size=log_index + 1,
        tree_root_hash=mock_root,
        inclusion_path=[sibling_1, sibling_2, sibling_3],
        mode="test",
    ).to_dict()


def verify_inclusion_proof_shape(proof: Dict[str, Any], payload_hash_hex: str) -> None:
    """Verify an inclusion proof against a payload hash.

    In test mode: recomputes the mock root and compares.
    In production mode (rekor): would verify the real Merkle inclusion
    proof against the published tree root — gated on live Rekor integration.
    """
    for required in ("log_id", "log_index", "tree_root_hash", "inclusion_path", "mode"):
        if required not in proof:
            raise RekorVerificationError(f"missing inclusion-proof field: {required}")

    mode = proof["mode"]
    if mode == "test":
        body = hmac.new(_MOCK_LOG_KEY, payload_hash_hex.encode("ascii"), hashlib.sha256).hexdigest()
        path = proof["inclusion_path"]
        if len(path) != 3:
            raise RekorVerificationError("test-mode inclusion path expected length 3")
        sib1 = hashlib.sha256((body + ":1").encode()).hexdigest()
        sib2 = hashlib.sha256((body + ":2").encode()).hexdigest()
        sib3 = hashlib.sha256((body + ":3").encode()).hexdigest()
        if path[0] != sib1 or path[1] != sib2 or path[2] != sib3:
            raise RekorVerificationError("test-mode inclusion-path siblings mismatch")
        expected_root = hmac.new(
            _MOCK_LOG_KEY,
            ":".join([sib1, sib2, sib3, body]).encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if expected_root != proof["tree_root_hash"]:
            raise RekorVerificationError("test-mode tree-root mismatch")
        return

    if mode == "rekor":
        raise RekorVerificationError(
            "live Sigstore Rekor verification not implemented in v1; gated on "
            "operator decision (which transparency log substrate to commit to)"
        )

    raise RekorVerificationError(f"unrecognized inclusion-proof mode: {mode}")
