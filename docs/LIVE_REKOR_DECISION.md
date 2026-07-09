<!-- episteme-lifecycle: status=design-history; reviewed_as_of=E147; superseded_by=docs/DESIGN_V2_0_EPISTEMIC_ENGINE.md -->
# Live transparency-log substrate — decision research

**Status:** operator-gated decision. Phase 3 ships only the shape (typed inclusion-proof field; mock test mode that round-trips). The live append + verification is its own Event.

**Question to answer:** which transparency-log substrate should episteme commit to for production deployments?

---

## 1. Why a transparency log at all

The Signed Reasoning Surface already has:

- Ed25519 signature (non-repudiable authorship)
- RFC 3161 TSA token (independent third-party timestamp)
- SHA-256 self-hash (per-surface integrity)
- Hash chain (per-session integrity)

A transparency log adds **public, append-only inclusion** — a third-party witness that the surface existed at time T, even if the operator later loses the surface or claims it never existed. The threat model it counters:

| Threat | Counter |
|---|---|
| Operator post-hoc claims they never authored a surface | Public log entry shows the surface was published at time T |
| Operator selectively retains favorable surfaces, discards unfavorable | Audit can reconstruct: "the log shows N entries; operator produced N surfaces; counts match" |
| Operator's private storage is destroyed (disk failure, ransomware) | Log entry survives off-system; auditor can reconstruct hash chain from log alone |

Without a transparency log, every threat above falls back to "trust the operator's storage." That trust is exactly what the rest of the architecture refuses to require.

---

## 2. Substrate options

### 2.1 Sigstore Rekor (public)

**What:** [`https://rekor.sigstore.dev`](https://rekor.sigstore.dev) — operated by the Linux Foundation Sigstore project, public append-only Merkle log already trusted by sigstore, cosign, in-toto, npm provenance, Python PyPI attestations, and the broader supply-chain security ecosystem.

**Pros:**
- Already operates at scale (billions of entries)
- No infrastructure burden for us
- Independent third party (LF, not us)
- Existing tooling (rekor CLI, OpenSSF-aligned)
- Inclusion proofs are standard Merkle proofs against signed log checkpoints
- Free (no per-entry cost)

**Cons:**
- Every surface published becomes **publicly indexed** with its hash and (truncated) metadata
- Operator data-residency concerns — Rekor is US-based, EU operators in scope for AI Act may have GDPR / NIS2 concerns about logging *any* metadata to a US public log even if surface bodies stay private
- Dependence on Sigstore project's continued operation (mitigated: their public log has multi-organization governance)

**Rate limits:** practical, not hard. Sigstore public log has fair-use limits; bursts of hundreds of entries per minute have been handled in supply-chain releases.

### 2.2 Self-hosted append-only Merkle log (Trillian / sigstore-self-hosted)

**What:** Run our own Rekor-equivalent log on operator-controlled infrastructure using [Google Trillian](https://github.com/google/trillian) as the underlying append-only Merkle tree, with sigstore Rekor as the HTTP API layer (Rekor itself is built on Trillian).

**Pros:**
- Operator controls the substrate; can be air-gapped or on-premises
- No cross-jurisdiction data flow concerns
- No third-party indexing of metadata
- Same proof shape as Sigstore — same verifier code

**Cons:**
- Operator runs the log (or hires someone to run it) — durability, backup, key rotation become operator's problem
- Trust model degrades: a single-operator-controlled log is less independently-verifiable than a multi-organization-governed public log. A determined operator could equivocate by publishing different log roots to different verifiers.
- Setup + maintenance cost (Trillian + PostgreSQL + Rekor frontend + signing keys + monitoring)
- "Self-hosted transparency log" is a slight contradiction — the *point* of a transparency log is third-party witness

### 2.3 Public log + private mirror (hybrid)

**What:** Publish to Sigstore Rekor public AND mirror to a self-hosted append-only log. Auditor can verify against either, and inconsistency between the two is itself an alarm.

**Pros:**
- Defense in depth — survives Sigstore unavailability OR self-hosted compromise
- EU operators can point auditor at the self-hosted mirror; the public log entry exists but is not the verification target
- Audit equivocation detection (mismatched roots = anomaly)

**Cons:**
- Two systems to maintain
- More moving parts; more failure modes
- Operationally heavier for a v1

### 2.4 No transparency log (just signature + TSA)

**What:** Skip the log layer. Rely on Ed25519 + RFC 3161 TSA for non-repudiation and time-binding.

**Pros:**
- Simplest; lowest operational burden
- Some EU operators will require this for data-residency reasons regardless

**Cons:**
- Reverts threat-model coverage to "trust operator storage" for the survivor-of-disk-loss and selective-retention threats
- Auditor cannot reconstruct missing surfaces

---

## 3. Decision criteria

| Criterion | Sigstore | Self-hosted | Hybrid | None |
|---|---|---|---|---|
| **Threat coverage** | High | Medium (operator-controlled) | Highest | Low |
| **Operational burden** | Low (no infra) | High (run Trillian) | Highest (run + monitor) | Lowest |
| **EU data-residency-friendly** | Low (US log) | High | High (self-hosted is the verification target) | High |
| **Third-party independence** | High (LF governance) | Low (operator-controlled) | High (via public log mirror) | None |
| **v1 fit (90 days from this Event)** | Yes | No (infra time) | No | Yes |
| **v2+ fit** | Maybe | Maybe | Yes | Probably no |

---

## 4. Recommendation (default)

**Default for v1: Sigstore Rekor public + a deferred decision on self-hosting.** The shape ships unchanged from Phase 3; the live append calls `rekor.sigstore.dev/api/v1/log/entries` and the verifier fetches the corresponding tree root for inclusion verification.

**Override path:** any operator deploying for EU high-risk AI Act compliance can set `EPISTEME_REKOR_URL=https://rekor.<my-domain>.example` to point at a self-hosted Rekor instance. The schema does not change; only the URL the verifier dials does. Phase 4 ships this env override as a documented config knob, gated on operator decision to actually stand up a self-hosted log.

**Hybrid is the v2 target** once we have at least one deployer who has stood up a self-hosted instance — at that point, we'll have learned what double-publishing actually costs in practice.

---

## 5. What ships in v1 vs v2

| Component | v1 (this Event) | v2 (deferred) |
|---|---|---|
| Inclusion-proof schema field | Shipped (`core/signing/transparency.py`) | — |
| Mock test-mode inclusion proof | Shipped | — |
| Live `POST /api/v1/log/entries` to Rekor | Deferred | Ships |
| Live tree-root fetch + Merkle proof verification | Deferred | Ships |
| `EPISTEME_REKOR_URL` env override | Deferred | Ships |
| Self-hosted Rekor deployment doc | Deferred | Future |
| Hybrid mode (dual-publish) | Deferred | Future v3 |

**Operator decision required to unblock v2 work:**
1. Acceptable to publish surface hashes (not bodies) to Sigstore public log? (Y/N — affects whether v2 is Sigstore-default or self-hosted-default)
2. Standing up self-hosted Rekor — willing to invest infra time, or wait until a deployer asks? (now / wait)
3. Treat live transparency log as required for Phase 5 launch, or as a nice-to-have? (required / optional)

---

## 6. References

- Sigstore Rekor: <https://docs.sigstore.dev/logging/overview/>
- Google Trillian: <https://github.com/google/trillian>
- RFC 9162 (Certificate Transparency v2.0 — Merkle proof structure underlying Rekor): <https://www.rfc-editor.org/rfc/rfc9162>
- RFC 8785 (JSON Canonicalization Scheme, used for the payload that gets logged): <https://www.rfc-editor.org/rfc/rfc8785>
- EU AI Act Article 12 (record-keeping requirements that motivated this design): <https://artificialintelligenceact.eu/article/12/>
