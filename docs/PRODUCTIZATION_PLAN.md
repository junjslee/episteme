# Productization Plan — Compliance Evidence Layer

**Opened:** 2026-05-10 (Event 121)
**Status of empirical base:** Phase 2 design pre-registered; trial dataset generation operator-gated.
**Positioning:** Compliance Evidence Layer for high-risk AI-assisted decisions. Adversarial to comfortable cognitive outsourcing.
**Regulatory tailwind:** EU AI Act Article 12 high-risk obligations apply **2026-08-02** (84 days from Event 121).

---

## 0. Position pivot — why this document exists

Events 119–120 closed the per-task A/B depth-measurement path: Sonnet 4.6 saturates at 9/10 depth on the hardest authorable tasks, kernel-free; the contamination probe confirmed Session A was genuinely kernel-free. The lift signal episteme was trying to demonstrate is structurally hard to surface at frontier model strength.

The reframe that survives this finding: **kernel value lives in operator Calibration-Lift on irreversible decisions, not model output depth.** This is anchored on published external-metacognitive-control research (MIRROR benchmark: Confident Failure Rate 0.60 → 0.14, ~70% reduction across 5 frontier models at temp 0) and the Long-Horizon Execution paper (arXiv 2509.09677: self-conditioning effect causes error compounding across multi-step trajectories; provenance-typed context injection is the structural counter).

Positioning shifts accordingly:

| Was | Is |
|---|---|
| "Cognitive scaffold for better reasoning" | "Compliance Evidence Layer for high-risk AI-assisted decisions" |
| Differentiation: "depth of analysis" | Differentiation: **pre-action operator-signed structured artifact** vs. post-hoc trace constructs |
| Audience: ML engineers | Audience: Chief Compliance Officers, Internal Audit, Notified Body assessors |
| Value claim: "X% lift on task-level scoring" | Value claim: "Cryptographically signed evidence that a real person — not the model — authorized every irreversible decision" |

---

## 1. Phase 3 — Technical Fortification (this Event)

### 1.1 Provenance-Tagged Step Pipeline (PTSP)

Counter to the self-conditioning effect (arXiv 2509.09677). Each step boundary holds four disjoint ledgers — Fact, Inference, Unknown, Assumption. Promotion of Inference → Fact requires explicit evidence (operator cosign, deterministic test pass, or external oracle attestation). Context injection at step N+1 tags items non-fungibly (`<fact>` vs `<inference>`) so the model cannot silently treat prior outputs as ground truth.

**Implementation surface:** `core/ptsp/`

**Invariants enforced:**

| ID | Invariant | Mechanism |
|---|---|---|
| I1 | No item appears in two ledgers simultaneously | Type discriminant `kind` non-nullable |
| I2 | Fact promotion is irreversible within session | `promoted_from` is set-once |
| I3 | No Fact may depend on an Inference | Topological check on `depends_on` |
| I4 | Step N+1 KNOWNS ⊇ Step N KNOWNS minus rejected facts | Set-equality at seal time |
| I5 | Hash chain unbroken | `parent_hash` = SHA-256(canonical(prev)) |

### 1.2 Signed Reasoning Surface (`signed-surface@1.0`)

Parallel-track to the live `reasoning-surface@1`. Adds cryptographic chain-of-custody to the existing structured artifact.

**Implementation surface:** `core/signing/`

**Trust model:**

| Threat | Counter |
|---|---|
| Non-repudiation of authorship | Ed25519 signature over JCS-canonical payload |
| Adversary alters past surface | Hash-chained Merkle log + Sigstore Rekor inclusion proof (shape only in v1; live integration deferred) |
| Backdated rationalization | RFC 3161 third-party TSA timestamp (mock TSA acceptable in v1; production swap is a config change) |
| Auditor cannot verify without trusting episteme | Standalone `episteme verify` binary with no runtime dependency on episteme |
| Key compromise | Ed25519 key rotation via signed key-rotation event; CRL endpoint; old surfaces remain verifiable up to revocation timestamp |

### 1.3 Standalone Auditor Verifier (`episteme verify`)

Implementation surface: `src/episteme/verify/`

**Exit code contract:**

| Code | Meaning |
|---|---|
| 0 | All surfaces verified |
| 10 | Signature invalid on ≥1 surface |
| 11 | Timestamp invalid (TSA token / asserted_timestamp drift > tolerance) |
| 12 | Transparency log inclusion failed (when live mode enabled) |
| 13 | Hash chain break |
| 14 | Self-hash mismatch |
| 20 | Surface file malformed / schema-invalid |
| 21 | Required key resolution failed (DNS/OIDC/Fulcio) |
| 30 | Mixed result in batch mode; see report for per-file status |
| 64 | Usage error |

The binary is built with `python -m episteme.verify` as v1; future iterations may produce a reproducible single-file static binary via PyOxidizer or Nuitka.

### 1.4 Ecosystem integration (designed, not all implemented this Event)

| Target | Integration shape | Status |
|---|---|---|
| Claude Code `.claude/settings.json` PreToolUse hook | Existing `reasoning_surface_guard.py` continues to govern; signed-surface@1.0 guard is **parallel and opt-in** until promoted in a separate Event | designed |
| Anthropic Skills Marketplace | `SKILL.md` + bundled CLI shipped via plugin manifest | designed |
| LangSmith / Langfuse | OpenTelemetry span `episteme.decision` with surface metadata; non-competing (episteme produces evidence, they consume traces) | designed |

---

## 2. Phase 4 — Compliance Mapping & Productization (mostly DESIGNED, partial LANDED)

### 2.1 Regulatory crosswalk

Cell-by-cell field-to-clause mapping landed at `docs/COMPLIANCE_CROSSWALK.md`. Covers:
- **EU AI Act** — Articles 12(1)–(3), 13(1), 13(3)(b)(iv), 14(4)(a)/(c)/(e), 19(1), 26(6), 72(1), Annex IV § 6
- **NIST AI RMF + GenAI Profile (NIST AI 600-1)** — GV-1.4, GV-6.1, MP-4.1, MP-5.1, MS-2.5, MS-3.3, MG-2.1, MG-4.1; GenAI MP-2.3, MS-3.3, MG-4.1
- **Financial-services framework set** — Fed SR 11-7, OCC Bulletin 2011-12, EBA Guidelines on ML for IRB Models, MAS FEAT + Veritas, OSFI E-23, FINRA Reg Notice 24-09 + Rule 4511, SEC Rule 17a-4(f)

### 2.2 CCO-facing dashboard

**DEFERRED — operator-gated on Probe 1 outcome.**

Functional requirements drafted:
- Tier 1 Posture Panel: decisions logged, signed-surfaces %, chain breaks, high-risk tier decisions, CFR current + delta vs prior period
- Tier 2 Decision Register: filtered, searchable, sortable, exportable
- Tier 3 Decision Detail: drill-down + hash-chain graph + signature verifier output + Rekor inclusion proof
- Tier 4 Alerts: signature failures, chain breaks, lazy-placeholder flags, paraphrase-classifier flags

**Read-only by design.** No edit, no delete. Amendment → new signed surface with `parent_surface_hash`.

**One-Click Regulator Evidence Packet** ZIP structure designed in `docs/PRODUCTIZATION_PLAN.md` § 4.2.3 (TBD if dashboard MVP is greenlit):

```
regulator-evidence-packet-<ISO>.zip
├── MANIFEST.json (+ .sig)
├── README.md
├── surfaces/<date>/*.signed.json
├── chains/session-<id>.json
├── public_keys/<fp>.pem + KEY_PROVENANCE.json
├── transparency_log/rekor_entries.jsonl + rekor_tree_root_signed.json
└── verifier/episteme-verify (standalone binary)
```

### 2.3 Differentiation matrix (designed; landing in marketing surface deferred)

| Tool | Artifact | Created when | Created by | Tamper-evident | Captures *why* operator decided |
|---|---|---|---|---|---|
| Datadog APM | Trace span | Post-execution | Auto-instrumented | No | No |
| LangSmith / Langfuse | LLM call trace | Post-execution | Auto-instrumented | No | No |
| GuardrailsAI / NeMo Guardrails | Input/output filter rule | Mid-execution | Auto-filter | No | No |
| Mem0 / Letta | Agent memory record | Post-interaction | LLM (or hybrid) | No | No |
| **episteme** | **Signed pre-action Reasoning Surface** | **Pre-action** | **Operator (cryptographically proven)** | **Yes (Ed25519 + Merkle + TSA + Rekor)** | **Yes** |

The defensive moat in one sentence: every other tool produces a *trace* of what happened; episteme produces a *commitment* the operator made before it happened, signed by a key the agent cannot access.

---

## 3. Phase 5 — Go-To-Market & Reversible Probes (DEFERRED — operator-gated)

### 3.1 Marketing copy (drafted; landing in `README.md` deferred to a separate Event)

#### 3.1.1 README headline candidate

```markdown
# episteme

**Harness Engineering for the human in the loop.**

Cryptographically signed evidence that a real person — not the model —
authorized every irreversible decision. EU AI Act Article 12 native.

Other agent memory tools (Mem0, Letta, Memento) help the agent remember.
episteme helps the regulator believe you.
```

#### 3.1.2 Manifesto (≤ 250 words)

```markdown
## What episteme is, and what it refuses to be

Every other agent tool in 2026 makes the model more capable, the agent
more autonomous, or the trace more searchable. episteme does none of
those things. It does one thing: it stops the operator from authorizing
an irreversible action until the operator has written down — in their
own hand, signed with their own key — what they know, what they don't
know, and what would prove them wrong.

We built episteme because frontier models are now good enough that
operators stop reading the diff. The same fluency that makes models
useful makes them dangerous: confident outputs replace deliberate
judgment, and the audit trail records only what the agent did, not
what the human believed.

episteme is adversarial to comfortable cognitive outsourcing. The
Reasoning Surface cannot be auto-filled. The signing key is not in the
agent's reach. The hash chain is public.

You will type more. You will move slower on irreversible operations.
Your auditor will sleep through the night.
```

#### 3.1.3 "Skeptical view on second-brain tools" copy block

```markdown
## Why we are skeptical of "second-brain" tools

Karpathy's LLM Wiki, Mem0, Memento, and the broader "AI-maintained
knowledge base" pattern share an assumption: it is good for the model
to remember on your behalf. For most knowledge work, that may be true.

For irreversible decisions, it is the failure mode.

When the model holds your context, your reasoning chain, and your prior
inferences, you do not audit them — you accept them. The MIRROR
benchmark showed that frontier models, left to self-evaluate, commit
confident failures at 0.60 rate. External metacognitive control drops
it to 0.14. The "external" in that sentence is doing all the work.

episteme insists the external is a human, signing with a key the model
cannot reach. We do not make outsourcing your reasoning easier. We
make it costlier — on purpose, only on the operations that cannot be
taken back.
```

#### 3.1.4 Hedging discipline on the 70.3% number

Until the Phase 2 productive-run dataset is published on OSF, marketing copy citing the CFR-reduction figure MUST include:

> "MIRROR-aligned design target (cf. external-metacognitive-control literature). Pre-registration OSF/REGISTRY-ID/<TBD>. Trial dataset publication pending."

No bare-number citation. No "we measured." Honesty discipline is brand discipline; the kernel's whole thesis falls apart if its marketing surface is buzzword-compliant rather than measurably correct.

### 3.2 Probe 1 — EU regulator outreach script

**Audience (10 high-leverage contacts, loss-averse posture):**

| Title pattern | Why |
|---|---|
| Head of AI Governance, EU-domiciled bank ≥ EUR 100B AUM | High-risk AI deployer under Art. 6; Art. 12 obligations live 2026-08-02 |
| AI Compliance Officer, EU insurer | Insurance is Annex III high-risk category |
| Data Protection Officer with AI mandate, EU healthcare provider | Annex III medical devices + AI Act overlap |
| Notified Body assessor — TÜV, DEKRA, BSI AI conformity practice | Direct line into Art. 19 conformity assessment criteria |
| EU AI Office liaison personnel | Authoritative interpretive guidance |

**Outreach template** (irreversible action — operator-gated, must not be sent automatically):

```
Subject: Article 12 evidence model — would 5 minutes of your read be useful?

Hi [Name],

I'm Jun Lee, building episteme — a small open-source tool that produces
cryptographically signed, operator-authored Reasoning Surfaces before
high-risk AI-assisted decisions. Ed25519 signatures, RFC 3161
timestamps, Sigstore-style transparency log.

The artifact is designed to satisfy:
  • Article 12(2)(a)–(f): event recording, period-of-use, identification
    of verifying persons, input data references
  • Article 13(1): deployer-facing interpretability of system output
  • Article 14(4)(a) and (c): operator awareness of limitations and
    counter to over-reliance on automated output

We have a Phase 2 trial pre-registered on OSF [link]; the design target
is a ≥50% relative reduction in confident-failure rate on irreversible-
class operations, aligned with published external-metacognitive-control
literature (MIRROR benchmark).

One definitive question: assuming the cryptographic chain-of-custody
holds, does a per-decision signed Reasoning Surface satisfy Article 13
deployer-transparency obligations as you currently interpret them — or
is there a gap I haven't surfaced?

I'm not selling — I'm trying to find the gap before I publish. Happy
to share the spec, the trial pre-registration, and the verifier CLI.
15 minutes if you're open; written reply equally fine.

— Jun
[github.com/junjslee/episteme] [signed contact pubkey fingerprint]
```

### 3.3 Day-90 OSS pull-velocity exit gate

**Pre-registered metrics — asymmetric thresholds per loss-averse posture.**

| Metric | 30-day | 90-day | Weight |
|---|---|---|---|
| GitHub stars | 800+ / 200–800 / <200 | 2,500+ / 500–2,500 / <500 | Low (vanity) |
| Substantive issues (non-bot, ≥100 chars, technical) | 30+ / 10–30 / <10 | 80+ / 25–80 / <25 | Medium |
| External PRs merged | 8+ / 2–8 / <2 | 25+ / 5–25 / <5 | Medium |
| Cited usage (blog / podcast / talk by non-author) | 5+ / 1–5 / 0 | 15+ / 3–15 / <3 | High |
| **CCO / Head of AI Governance inbound** | **5+ / 1–5 / 0** | **15+ / 3–15 / <3** | **Highest** |
| Paid pilot inquiries (LOI or signed engagement) | 1+ / 0 / 0 | 3+ / 1–3 / 0 | High |
| Notified body / regulator citation | 0–1 acceptable | 1+ triggers Probe 1 escalation | Inflection |

**Day-90 decision matrix (pre-registered, signed at Probe-launch time):**

| Outcome region | Definition | Decision |
|---|---|---|
| Commercial spin-off | CCO inbound ≥3 **AND** paid pilot inquiries ≥1 **AND** ≥1 notified-body engagement | Form entity, take pilot revenue, hire 1 compliance lead, keep kernel MIT, license enterprise dashboard + framework exports |
| OSS sustain | CCO inbound 1–2 **OR** stars 500–2,500 **AND** no paid pilot inquiries | Continue OSS; pursue grant funding (EU Horizon, NLnet, OpenSSF); no commercial entity yet |
| Personal-tool sunset | All metrics in "Null" column **AND** Probe 1 produced no engaged notified-body conversation | Public post-mortem. Keep using episteme personally. Reframe README as "personal compliance harness, not productized." No commercial pivot. No marketing spin. |
| Adverse | Critique invalidates a load-bearing claim (cryptographic or regulatory) | Immediate written response. If critique holds, rewrite the load-bearing claim. If not, publish rebuttal. Do not paper over with marketing. |

---

## 4. Reversibility ledger

| Action | Reversibility | Rollback path |
|---|---|---|
| This Event's file additions (Phase 3 modules + 2 docs) | Reversible (local git, no push) | `git reset --hard HEAD~1` before push |
| Local commit | Reversible until pushed | Amend or reset |
| Push to remote `master` | Irreversible (public claim) | Operator-gated; not in this Event |
| README/manifesto landing | Irreversible (positioning claim) | Operator-gated; deferred Event |
| OSF pre-registration | Irreversible (timestamped public) | Amendments only via OSF amendment protocol; design feature |
| HN / Lobsters / LinkedIn / X posts | Effectively irreversible (caches) | Honest follow-up post if claims need correction |
| Probe 1 sent emails | Reversible per-conversation; cumulative reputational effect not | Operator-gated; maintain Probe 1 signed-surface log so every contact is auditable |
| Commercial entity formation | Irreversible without significant cost | Gate behind Day-90 matrix outcome; do not trigger on Phase 5 Probe 1 enthusiasm alone |

---

## 5. Anti-self-deception protocol during Probes 1 + 2

Failure modes to actively screen for (per noise-watch: status-pressure, false-urgency):

| Failure mode | Counter |
|---|---|
| Counting stars as proof of fit | Weight CCO inbound 10× higher than stars in the matrix |
| Mistaking engineer enthusiasm for compliance-buyer fit | Only Probe 1 contacts count toward the commercial-spin-off threshold |
| Allowing day-30 numbers to drive a permanent pivot | Pre-registered day-90 decision; no commercial action before then |
| Re-interpreting Null outcome as "needs more marketing" | The matrix is signed and timestamped; post-hoc reinterpretation is a logged amendment |
| Confusing "regulator interested in the artifact" with "regulator will require the artifact" | Single notified-body conversation is a signal, not a market |

---

## 6. What this document does NOT claim

- The 70.3% CFR reduction is **not** an episteme-measured number until a real 12-operator × 50-task crossover trial runs. It is a MIRROR-aligned design target derived from published literature on external metacognitive control.
- The Compliance Evidence Layer positioning is **not** validated by external regulator confirmation. Probe 1 is exactly the test of whether that positioning lands.
- The dashboard MVP, the marketing surface, the commercial entity — none exist as of this Event. All operator-gated, all reversible until executed.

This document is the **plan**, not the **proof**. The kernel-tone-discipline rule applies: governance surface stays precise about what the data does and doesn't show.
