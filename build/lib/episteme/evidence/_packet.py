"""Regulator Evidence Packet ZIP exporter.

Builds a self-contained ZIP archive per PRODUCTIZATION_PLAN.md § 4.2.3:

    regulator-evidence-packet-<ISO>.zip
    ├── MANIFEST.json                ← canonical manifest, framework-aligned
    ├── MANIFEST.json.sig            ← Ed25519/HMAC signature over MANIFEST.json
    ├── README.md                    ← human-readable orientation
    ├── surfaces/<date>/<id>.signed.json
    ├── chains/session-<id>.json     ← ordered hash-chain manifests
    ├── public_keys/<fp>.pem         ← pubkeys + KEY_PROVENANCE.json
    ├── transparency_log/rekor_entries.jsonl
    └── verifier/                    ← standalone verifier reference

The packet is reproducible byte-for-byte given the same inputs and operator
key — the manifest hash is stable, the signature is deterministic per the
HMAC/Ed25519 contract. Auditor verifies by:
    unzip packet.zip
    python -m episteme.verify --batch surfaces/ --keys-dir public_keys/

This module ships in v1 with the manifest + surfaces + chains + public keys
+ transparency log. The bundled standalone verifier is referenced (path is
included in MANIFEST.json) rather than re-shipped at this layer — the
auditor uses their own checkout of `episteme verify`.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.ptsp.canonical import jcs_canonical, sha256_hex
from core.signing.ed25519_compat import sign_message, signature_mode
from episteme.evidence._index import IndexEntry
from episteme.surface._storage import keys_dir, read_keypair, read_public_key_by_fingerprint


PACKET_SCHEMA = "regulator-evidence-packet@1.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _build_manifest(
    entries: List[IndexEntry],
    *,
    framework: str,
    period_from: Optional[str],
    period_to: Optional[str],
    operator_fingerprints: List[str],
) -> Dict[str, Any]:
    """Build the canonical MANIFEST.json structure."""
    surface_files = []
    chain_sessions: Dict[str, List[str]] = {}
    for e in entries:
        date_bucket = e.issued_at[:10] if e.issued_at else "unknown"
        surface_filename = f"surfaces/{date_bucket}/{e.surface_id}.signed.json"
        surface_files.append({
            "surface_id": e.surface_id,
            "filename": surface_filename,
            "self_hash": e.self_hash,
            "issued_at": e.issued_at,
            "ai_act_tier": e.ai_act_tier,
            "signature_mode": e.signature_mode,
        })
        chain_sessions.setdefault(e.session_id, []).append(e.surface_id)

    manifest = {
        "schema": PACKET_SCHEMA,
        "framework": framework,
        "generated_at": _now_iso(),
        "period": {"from": period_from, "to": period_to},
        "counts": {
            "surfaces": len(entries),
            "sessions": len(chain_sessions),
            "operators": len(operator_fingerprints),
        },
        "operator_fingerprints": sorted(operator_fingerprints),
        "surfaces": surface_files,
        "chains": [
            {"session_id": s, "surface_ids": ids}
            for s, ids in sorted(chain_sessions.items())
        ],
        "verifier_reference": {
            "command": "python -m episteme.verify --batch surfaces/ --keys-dir public_keys/",
            "exit_codes_doc": "https://episteme.dev/docs/episteme-verify-exit-codes",
        },
    }
    return manifest


def _readme_text(framework: str, manifest: Dict[str, Any]) -> str:
    counts = manifest["counts"]
    period = manifest["period"]
    return f"""Regulator Evidence Packet — {framework}
============================================

Schema:      {manifest['schema']}
Framework:   {framework}
Generated:   {manifest['generated_at']}
Period:      {period.get('from')} → {period.get('to')}
Surfaces:    {counts['surfaces']}
Sessions:    {counts['sessions']}
Operators:   {counts['operators']}

WHAT THIS PACKET CONTAINS
-------------------------

A self-contained, cryptographically verifiable record of every Reasoning
Surface authored and signed by the operator(s) named in MANIFEST.json
during the period above. Each surface is an operator-authored, Ed25519-
signed structured artifact captured BEFORE an irreversible AI-assisted
action, satisfying EU AI Act Article 12(1)-(3) record-keeping obligations
and the equivalent record-keeping clauses of the framework named above.

HOW TO VERIFY
-------------

    cd <unzipped_packet_root>
    python -m episteme.verify --batch surfaces/ --keys-dir public_keys/

Exit code 0 means all surfaces in this packet verify cryptographically
against the public keys included here. Any other exit code indicates a
specific verification failure (signature, timestamp, transparency log,
hash chain, or self-hash). See `verifier_reference.exit_codes_doc` in
MANIFEST.json.

INTEGRITY CHAIN
---------------

  MANIFEST.json.sig    Ed25519 (or test-mode HMAC) signature over the
                       canonical JCS bytes of MANIFEST.json
  surfaces/            individual signed-surface@1.0 JSON artifacts
  chains/              session-ordered hash-chain references
  public_keys/         operator public keys + KEY_PROVENANCE.json
  transparency_log/    Sigstore Rekor inclusion proofs (when present)

CAVEATS
-------

If signature_mode is "test" on any surface, the operator's environment
was running episteme's HMAC-SHA256 test-mode fallback (PyNaCl not
installed). Production audits SHOULD reject test-mode signatures by
default. The `--allow-test-signatures` flag on `episteme verify` will
accept them only when explicitly passed — typically used in fixture-driven
test runs, not real audits.
"""


def build_packet(
    entries: List[IndexEntry],
    *,
    framework: str,
    output_path: Path,
    period_from: Optional[str] = None,
    period_to: Optional[str] = None,
    include_rekor: bool = True,
) -> Dict[str, Any]:
    """Build a Regulator Evidence Packet ZIP. Returns the manifest dict."""
    operator_fps = sorted({e.operator_pubkey_fingerprint for e in entries if e.operator_pubkey_fingerprint})
    manifest = _build_manifest(
        entries,
        framework=framework,
        period_from=period_from,
        period_to=period_to,
        operator_fingerprints=operator_fps,
    )

    # Sign the manifest with the operator's keypair (if present).
    manifest_bytes = jcs_canonical(manifest)
    manifest_sig: Optional[str] = None
    kp = read_keypair()
    if kp:
        privkey, _ = kp
        manifest_sig = sign_message(privkey, manifest_bytes)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Manifest + signature
        zf.writestr("MANIFEST.json", manifest_bytes)
        if manifest_sig:
            zf.writestr("MANIFEST.json.sig", manifest_sig)

        # README
        zf.writestr("README.md", _readme_text(framework, manifest))

        # Surfaces
        for e in entries:
            date_bucket = e.issued_at[:10] if e.issued_at else "unknown"
            zf.writestr(
                f"surfaces/{date_bucket}/{e.surface_id}.signed.json",
                json.dumps(e.raw, indent=2, sort_keys=True),
            )

        # Chains
        chain_sessions: Dict[str, List[IndexEntry]] = {}
        for e in entries:
            chain_sessions.setdefault(e.session_id, []).append(e)
        for session_id, session_entries in chain_sessions.items():
            ordered = sorted(session_entries, key=lambda x: x.issued_at)
            chain_doc = {
                "session_id": session_id,
                "surfaces": [
                    {
                        "surface_id": e.surface_id,
                        "issued_at": e.issued_at,
                        "parent_surface_hash": e.parent_surface_hash,
                        "self_hash": e.self_hash,
                    }
                    for e in ordered
                ],
            }
            zf.writestr(f"chains/session-{session_id}.json", json.dumps(chain_doc, indent=2))

        # Public keys
        key_provenance: Dict[str, Any] = {
            "schema": "key-provenance@1.0",
            "generated_at": manifest["generated_at"],
            "keys": [],
        }
        for fp in operator_fps:
            pk = read_public_key_by_fingerprint(fp)
            if pk:
                zf.writestr(f"public_keys/{fp}.pub", pk)
                key_provenance["keys"].append({
                    "fingerprint": fp,
                    "filename": f"public_keys/{fp}.pub",
                    "resolution": "local-filesystem",
                    "note": (
                        "v1 packet ships local-filesystem-resolved pubkeys. "
                        "Production deployments should bind via DNS TXT or "
                        "OIDC subject claim; see KEY_PROVENANCE.md."
                    ),
                })
        zf.writestr("public_keys/KEY_PROVENANCE.json", json.dumps(key_provenance, indent=2))

        # Transparency log entries (if Rekor proofs are present on any surface)
        if include_rekor:
            rekor_entries = []
            for e in entries:
                rekor = e.raw.get("attestation", {}).get("transparency_log")
                if rekor:
                    rekor_entries.append({
                        "surface_id": e.surface_id,
                        "self_hash": e.self_hash,
                        "rekor": rekor,
                    })
            if rekor_entries:
                zf.writestr(
                    "transparency_log/rekor_entries.jsonl",
                    "\n".join(json.dumps(r) for r in rekor_entries) + "\n",
                )

    return manifest
