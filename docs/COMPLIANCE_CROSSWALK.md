# Compliance Crosswalk — `signed-surface@1.0` → Regulatory Clauses

**What this document is.** A **downstream structural mapping**. Not the primary identity of episteme. Not the primary positioning. Not a sales artifact.

**What episteme actually is.** A way to think — 생각의 틀 — operationalized at the file system level. See [`docs/THE_WAY_TO_THINK.md`](THE_WAY_TO_THINK.md). The five-stage cognitive practice (Frame → Decompose → Execute → Verify → Handoff) is the product. The signed Reasoning Surface is what falls out when the practice is taken seriously.

**Why this crosswalk exists.** When the operator practices the cognitive moves named in `THE_WAY_TO_THINK.md`, the residue is an operator-authored, cryptographically signed, time-stamped, hash-chained, third-party-verifiable structured artifact captured *before* an irreversible AI-assisted action. EU AI Act Article 12 (record-keeping), Article 13 (deployer transparency), Article 14 (human oversight) — and the equivalent obligations in NIST AI RMF, Fed SR 11-7, EBA, MAS, OSFI, FINRA, SEC 17a-4(f) — happen to want exactly this artifact. The fit is **structural**, not the goal. The practice came first; the regulator-shape happened to match because the practice is right about the underlying mechanism (MIRROR benchmark, [arXiv 2604.19809](https://arxiv.org/abs/2604.19809) — *"only architectural constraint is effective"*).

This document maps the practice's residue to regulatory clauses cell-by-cell. Whether any specific regulator accepts the mapping is the question Phase 5 Probe 1 is designed to test; **this document does not claim regulator validation.**

**Schema version:** `signed-surface@1.0`
**Frameworks covered:** EU AI Act, NIST AI RMF + GenAI Profile (NIST AI 600-1), Financial-services framework set (Fed SR 11-7, OCC, EBA, MAS, OSFI, FINRA, SEC).
**Coverage notation:**
- **Direct** — artifact alone satisfies the obligation
- **Supporting** — artifact is necessary evidence within a broader compliance program
- **Conditional** — satisfies only when paired with named operator policy

This is a **structural mapping**. Whether the artifact materially satisfies any specific obligation in any specific jurisdiction requires legal counsel review for the deployer's specific deployment. episteme does not provide legal advice; it provides cryptographically signed structured evidence at the operator decision layer.

---

## 0. `signed-surface@1.0` field-path index

For the crosswalk below, field paths reference this canonical structure:

```
envelope.schema_version
envelope.surface_id
envelope.session_id
envelope.operator_pubkey_fingerprint
envelope.parent_surface_hash
envelope.issued_at

surface.core_question
surface.risk_classification.{reversibility, blast_radius, ai_act_tier, article_79_1_triggers[]}
surface.knowns[].{fact, source_artifact, verified_at, verification_method}
surface.unknowns[].{unknown, why_not_resolvable_now, cost_of_ignorance}
surface.assumptions[].{assumption, if_wrong_then, detectability}
surface.disconfirmation_conditions[].{observable, measurement_method, would_invalidate_plan}
surface.decision.{choice, confidence, confidence_elicitation_method, stop_rollback_path}
surface.audit.{blueprint_invoked, validation_layers_passed[]}

attestation.signature_alg
attestation.signature_b64
attestation.signed_at
attestation.tsa.{tsa_url, tsa_token_b64, tsa_certificate_chain_pem_sha256, asserted_timestamp}
attestation.transparency_log.{log_id, log_index, log_uuid, inclusion_proof, tree_root_hash}

self_hash
```

---

## 1. EU AI Act

EU AI Act high-risk system obligations apply **2026-08-02** (24 months after entry into force, 2024-08-01).

| Clause | Obligation (paraphrased) | Field path | Coverage | Technical justification |
|---|---|---|---|---|
| **Art. 12(1)** | Automatic recording of events ("logs") for high-risk systems over lifetime | All `signed_surface.json` files persisted to `EPISTEME_SURFACE_DIR` + transparency log entry | **Direct** | Per-decision artifact written before tool execution; Rekor inclusion ensures append-only off-system durability |
| **Art. 12(2)(a)** | Logging shall enable identification of situations resulting in risk per Art. 79(1) | `surface.risk_classification.article_79_1_triggers[]` | **Direct** | Operator-declared enumeration of Art. 79(1) triggers as part of pre-action commitment |
| **Art. 12(2)(b)** | Facilitate post-market monitoring per Art. 72 | Hash-chained surface index + dashboard Tier 2 register (Phase 4 deferred) | **Direct** | Indexed, queryable record by date / operator / action class / risk tier |
| **Art. 12(2)(c)** | Recording of period of each use | `envelope.issued_at` + `attestation.tsa.asserted_timestamp` | **Direct** | RFC 3161 third-party timestamp provides non-self-attested period-of-use evidence |
| **Art. 12(2)(d)** | Reference database against which input data has been checked | `surface.knowns[].source_artifact` | **Direct** | Each Known carries `source_artifact` URI and content hash |
| **Art. 12(2)(e)** | Input data leading to the output | `surface.knowns[]` + `surface.assumptions[]` | **Direct** | Operator-authored enumeration of all inputs and assumed dependencies |
| **Art. 12(2)(f)** | Identification of natural persons involved in verification | `envelope.operator_pubkey_fingerprint` + Ed25519 signature | **Direct** | Cryptographic non-repudiable bond between surface and natural person; resolves to OIDC sub or DNS-published identity |
| **Art. 12(3)** | Deployers shall keep logs ≥ 6 months (or longer per other Union law) | `episteme retention apply --framework=eu-ai-act` retention policy | **Direct** | Default retention meets minimum; transparency log entries persist indefinitely off-system |
| **Art. 13(1)** | Transparency: enable deployers to interpret system output | `surface.core_question` + `surface.{knowns,unknowns,assumptions,disconfirmation_conditions}` | **Direct** | Pre-action structured commitment serves as the deployer-facing interpretation artifact for each high-risk decision |
| **Art. 13(3)(b)(iv)** | Instructions for use shall describe human oversight measures | `surface.decision.stop_rollback_path` + `surface.disconfirmation_conditions[]` | **Direct** | Each surface declares its own oversight rule and rollback path |
| **Art. 14(4)(a)** | Operator understands capacities/limitations of the system | `surface.unknowns[].cost_of_ignorance` (operator-authored, min 30 chars) | **Supporting** | Forces explicit articulation of limitation-awareness per decision |
| **Art. 14(4)(c)** | Operator remains aware of, and counters, automation bias | Pre-tool gate (`reasoning_surface_guard.py` + `core/signing` validator): blocks irreversible action until operator authors and signs surface | **Direct** | The gate IS the counter-bias mechanism — model cannot author the surface; operator must hand-sign before action proceeds |
| **Art. 14(4)(e)** | Operator can decide not to use the output or override it | `surface.decision.choice ∈ {proceed, stop, audit}` + signed rollback path | **Direct** | Decision is operator-elected per-action, not model-defaulted |
| **Art. 19(1)** | Conformity assessment: keep automatically generated logs ≥ 6 months | Retention policy + transparency log inclusion | **Direct** | Default retention meets minimum; transparency log entries persist indefinitely off-system |
| **Art. 26(6)** | Deployers shall keep logs generated by the system for ≥ 6 months | Same retention as Art. 19(1) | **Direct** | Per-deployer retention policy enforced via `EPISTEME_RETENTION_DAYS` env var |
| **Art. 72(1)** | Post-market monitoring system | Longitudinal CFR / calibration metrics computed over surface index | **Supporting** | Surface index is the substrate; PMM plan must wrap it with deployer policy |
| **Annex IV § 6** | Detailed description of monitoring, performance, control | CCO dashboard exports + framework-aligned ZIP packet (Phase 4 deferred) | **Direct** | One-click export produces Annex IV § 6-compliant evidence bundle |

---

## 2. NIST AI RMF + GenAI Profile (NIST AI 600-1, July 2024)

| Function / Action | Sub-action description | Field path | Coverage | Technical justification |
|---|---|---|---|---|
| **GV-1.4** | Legal / regulatory / ethical requirements understood & managed | `surface.risk_classification.ai_act_tier` + framework_export outputs | **Direct** | Per-decision risk-tier declaration aligned to AI Act categories |
| **GV-6.1** | Third-party / vendor model use policies | `surface.knowns[].source_artifact` capturing model vendor + version + sampling params; `core.ptsp.ModelIdentity` for inferences | **Direct** | Each model-influenced fact carries provider identity in `ModelIdentity` |
| **MP-4.1** | Approaches for mapping AI technology and risks documented | `risk_classification.{blast_radius, article_79_1_triggers[]}` | **Direct** | Per-decision risk surface; corpus-aggregable for organizational risk map |
| **MP-5.1** | Likelihood and magnitude of each impact characterized | `surface.assumptions[].if_wrong_then` + `surface.decision.confidence` | **Direct** | Magnitude (`if_wrong_then`) + likelihood (`1 - confidence`) supplied per assumption |
| **MS-2.5** | AI system trustworthiness measured | `surface.disconfirmation_conditions[]` (pre-committed) + post-execution oracle resolution | **Direct** | Disconfirmation criteria committed before action; post-execution resolution yields per-decision trustworthiness datum |
| **MS-3.3** | Model output validation by humans with relevant domain expertise | Ed25519 signature ties surface to operator identity | **Direct** | Operator HMAC/Ed25519 key is the cryptographic proof of human-in-the-loop |
| **MG-2.1** | Resources allocated based on assessed risk | Aggregation over `risk_classification.ai_act_tier` to drive resource policy | **Supporting** | Surface index provides the empirical input; allocation policy is organizational |
| **MG-4.1** | Post-deployment monitoring plans implemented | Surface index + verifier CLI + transparency log | **Direct** | Combination satisfies "auditable, queryable, externally verifiable" |
| **GenAI MP-2.3** | Document GAI intended purposes, known limitations | `surface.unknowns[]` + `surface.assumptions[]` | **Direct** | Limitations captured per-decision rather than statically |
| **GenAI MS-3.3** | Validate outputs with relevant domain experts | Operator-signature requirement; cannot be auto-discharged | **Direct** | The gate enforces it cryptographically |
| **GenAI MG-4.1** | Track emergent risks in deployment | `core/ptsp` promotion-violation detection (Inference treated as Fact in step N+1) | **Supporting** | Surfaces self-conditioning drift as a class of emergent risk |

---

## 3. Financial-services framework set

There is no single canonical "FS-AI-RMF." This crosswalk maps to the applicable framework set covering financial-services AI as of May 2026.

| Clause | Obligation (paraphrased) | Field path | Coverage | Technical justification |
|---|---|---|---|---|
| **Fed SR 11-7 § III.B** | Effective challenge — critical analysis by objective, informed parties | `surface.disconfirmation_conditions[]` + auditor-side `episteme verify --chain` | **Direct** | Pre-committed disconfirmation conditions are the substrate of effective challenge; auditor verifies independently |
| **Fed SR 11-7 § III.A** | Model documentation — purpose, inputs, processing, outputs, limitations | Full surface schema (`core_question`, `knowns`, `assumptions`, `unknowns`) | **Direct** | Per-decision model documentation captured cryptographically |
| **Fed SR 11-7 § V** | Ongoing monitoring of model performance | Longitudinal CFR + calibration metrics from surface index | **Direct** | Empirical performance derived from same evidentiary substrate as audit |
| **Fed SR 11-7 § IV** | Validation: independent, ongoing, of all model components | `episteme verify` standalone binary | **Direct** | Reproducible, independent verifier; not dependent on episteme runtime |
| **OCC Bulletin 2011-12** | Model risk governance — board oversight, policy, retention | Dashboard role-based view for board / audit committee (Phase 4 deferred) | **Direct** | Tier 1 Posture Panel produces summary view; Tier 2/3 enable drill-down |
| **EBA Guidelines on ML for IRB Models § 4** | Human review of ML-driven IRB decisions | Operator signature requirement per credit decision | **Direct** | Each credit-impacting decision requires operator-signed surface |
| **EBA § 5** | Explainability of ML model outputs | `surface.knowns[]` + `core.ptsp.Inference` separation | **Direct** | Auditable separation of operator-verified facts from model-inferred outputs |
| **MAS FEAT** | Per-decision accountability for AI-assisted decisions | Operator pubkey → natural person → accountability | **Direct** | Non-repudiable identity-to-decision binding |
| **MAS Veritas Toolkit** | Per-decision FEAT assessments | `episteme export --framework=mas-feat` (Phase 4 deferred for full export) | **Direct** | One-click FEAT-aligned export per decision or batch |
| **OSFI Guideline E-23 § 5** | Materiality-tiered model oversight | `risk_classification.blast_radius` → materiality tier mapping | **Direct** | Tier-aware retention, review cadence, and approval policy |
| **FINRA Reg Notice 24-09** | Supervision of AI-assisted recommendations | Per-recommendation signed surface | **Direct** | Surface IS the supervisory record |
| **FINRA Rule 4511 (6-year retention)** | Books and records retention for broker-dealer activity | `episteme retention apply --framework=finra` with `--retention-days=2190` | **Direct** | Surface index + Rekor inclusion durably retained ≥ 6 yr |
| **SEC Rule 17a-4(f) (WORM)** | Write-Once-Read-Many electronic records | Append-only transparency log inclusion | **Direct** | Rekor log is cryptographically append-only; satisfies WORM intent |

---

## 4. Cross-framework export tooling (deferred, designed)

```
episteme export --framework=<eu-ai-act|nist-genai|sr-11-7|eba-ml|mas-feat|osfi-e23|finra> \
                --since <date> --until <date> \
                --output <packet.zip>
```

The framework-specific export rearranges the same underlying signed surfaces into the structure each framework's audit-evidence format expects. The cryptographic substrate is identical; only the presentation manifest changes per framework.

---

## 5. Honesty caveats

This document does **not** claim:

- That any specific regulator has reviewed and accepted `signed-surface@1.0` as satisfying any specific clause. Phase 5 Probe 1 is exactly the test of that.
- That the Coverage column is dispositive against legal challenge. Each deployer's compliance counsel must independently assess applicability for their deployment.
- That the artifact alone satisfies any framework end-to-end. Even where Coverage = Direct, the artifact is the **evidence**; the **compliance program** wrapping it is the deployer's responsibility.
- That the schema is final. `signed-surface@1.0` is the load-bearing v1 shape; v1.1+ amendments will preserve backward compatibility (the schema version field exists for exactly this).

The kernel-tone-discipline rule applies: governance surface stays precise about what is structurally defensible vs. what requires external validation.
