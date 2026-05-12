# How to verify a Regulator Evidence Packet

**Audience:** external auditor / Internal Audit / Notified Body assessor receiving a `regulator-evidence-packet-<ISO>.zip` from an episteme operator.
**Goal:** independently verify the packet's cryptographic chain-of-custody without trusting the operator's episteme runtime.

---

## 1. What you are looking at

The packet is a self-contained ZIP archive with the following structure:

```
regulator-evidence-packet-<ISO>.zip
├── MANIFEST.json                 ← canonical manifest (JCS-canonical bytes)
├── MANIFEST.json.sig             ← Ed25519 (or test-mode HMAC) signature over MANIFEST.json
├── README.md                     ← human-readable orientation
├── surfaces/<date>/<id>.signed.json
├── chains/session-<id>.json      ← session-ordered hash-chain references
├── public_keys/<fp>.pub          ← operator public keys + KEY_PROVENANCE.json
└── transparency_log/rekor_entries.jsonl  ← when Rekor proofs were attached
```

Every signed surface is an operator-authored structured artifact (the `signed-surface@1.0` schema) captured **before** an irreversible AI-assisted action. The operator's private key signed each surface; the public key is in the packet. The audit-evidence chain is:

```
operator's private key   →   signs surface payload (JCS-canonical bytes)
operator's public key    →   bundled in packet, verifies signature
RFC 3161 TSA token       →   independent third-party timestamp on payload hash
Sigstore Rekor proof     →   public append-only transparency log inclusion
operator pubkey fingerprint = SHA-256(public key)   → in envelope, must match
hash chain across session → each surface references parent's self_hash
```

If any link in this chain is broken, the verifier exits with a specific code (§3).

---

## 2. Run the verifier

You need Python 3.10+ and the `episteme` package (any version ≥ Phase 3). Install:

```bash
pip install episteme              # zero hard deps
pip install 'episteme[signing]'   # adds PyNaCl for Ed25519 verification
```

Unzip the packet and run:

```bash
unzip regulator-evidence-packet-<ISO>.zip -d packet/
cd packet
python -m episteme.verify \
    --batch surfaces/ \
    --keys-dir public_keys/ \
    --verify-tsa \
    --verify-rekor \
    --format json
```

**Exit code 0** means every surface in the packet verified cryptographically against the public keys included. Any other exit code is a specific failure (§3). The verifier walks every `*.json` file under `surfaces/` recursively when given the `surfaces/` root.

---

## 3. Exit code contract

| Code | Meaning | Likely cause |
|---|---|---|
| 0 | All surfaces verified | — |
| 10 | Signature invalid on at least one surface | Surface payload was modified after signing, OR public key in packet doesn't match the signing private key |
| 11 | Timestamp invalid (TSA token / asserted_timestamp drift) | RFC 3161 token does not validate against the embedded TSA cert chain, OR `asserted_timestamp` predates / postdates `envelope.issued_at` |
| 12 | Transparency log inclusion failed | Rekor inclusion proof does not verify against the published tree root |
| 13 | Hash chain break | `parent_surface_hash` of surface N does not match `self_hash` of surface N-1 in the same session |
| 14 | Self-hash mismatch | `self_hash` does not match the recomputed canonical hash — surface was tampered after signing |
| 20 | Surface file malformed / schema-invalid | JSON parse failure or missing required envelope/surface/attestation fields |
| 21 | Required key resolution failed | Public key file missing under `public_keys/<fingerprint>.pub` |
| 30 | Mixed result in batch mode | Some surfaces passed, some failed — read per-file report in the output |
| 64 | Usage error | Invalid CLI argument combination |

---

## 4. Verify the chain ordering (per session)

The flat `--batch` mode verifies each surface independently. To verify session-level continuity (parent→child hash chain):

```bash
python -m episteme.verify \
    --chain chains/session-<id>.json \
    --keys-dir public_keys/ \
    --verify-tsa --verify-rekor
```

A chain break (exit 13) means a surface within the session references a parent hash that does not match the prior surface's `self_hash`. This indicates either (a) a missing intermediate surface, (b) tampering, or (c) a different operator session that was incorrectly bundled.

---

## 5. Test-mode signatures

If you see exit code 10 with `test_signature_rejected`, the packet contains surfaces signed in the operator's HMAC-SHA256 test mode (PyNaCl was not installed in the signing environment). The verifier rejects these by default. For production audit, this should fail the audit — the operator must re-sign with production Ed25519 (after installing PyNaCl) and rebuild the packet.

For internal testing only, you can pass `--allow-test-signatures` to override. **Never do this in a production audit.**

---

## 6. Verify the MANIFEST itself

The packet's `MANIFEST.json` is signed by the same operator key as the surfaces. To verify the manifest:

```bash
python -m episteme.verify \
    MANIFEST.json \
    --keys-dir public_keys/
```

A valid manifest signature confirms the operator's claim about WHICH surfaces are in the packet (counts, fingerprints, period). A modified manifest with the same surfaces would still pass per-surface verification but would fail manifest-level signature.

---

## 7. What the verifier does NOT verify

| Out of scope | Why |
|---|---|
| Whether the operator's reasoning in the surface is *correct* | The verifier is cryptographic, not epistemic; reasoning quality is a human review question |
| Whether the operator's identity binding is real-world correct | The verifier confirms `pubkey_fingerprint = SHA-256(pubkey)`; binding the fingerprint to a natural person requires DNS / OIDC / Fulcio attestation that lives outside the packet |
| Whether the action that followed the surface actually happened as described | The verifier confirms the operator authored a commitment; tying the commitment to a downstream action requires the operator's runtime logs (Datadog / LangSmith / Langfuse traces — episteme operates at the operator-decision layer, upstream of those) |
| Whether the operator's deployment satisfies any specific regulatory clause | That is the auditor's job; the verifier provides the evidence; legal/compliance counsel applies it |

---

## 8. Reporting failures back to the operator

If verification fails with exit code 10/11/12/13/14, the surface(s) named in the report cannot be trusted as audit evidence. The operator should:

1. Inspect their own `episteme evidence alerts` output
2. Re-author the failing surfaces if possible (operator-side)
3. Rebuild the packet with `episteme evidence packet build`
4. Re-send

If exit code 20 or 21 fires, the packet is structurally damaged — request a fresh build from the operator.
