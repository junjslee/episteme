# Productization Plan

**Opened:** 2026-05-10 (Event 121). Rewritten 2026-05-12 (Event 122) after operator-flagged category errors. Rewritten again 2026-05-12 (Event 123) after operator's deeper correction — *"it should be fucking the way to think."*

**Primary identity (what episteme IS):** A way to think — 생각의 틀 — operationalized at the file system level. See [`docs/THE_WAY_TO_THINK.md`](THE_WAY_TO_THINK.md). The practice is the product. Everything in this document — including every claim about positioning, audience, regulatory mapping, and probes — is **downstream of the practice**, not parallel to it.

**Primary value claim (what we measure when we get to Phase 2 trial):** External architectural constraint reduces operator Confident Failure Rate on irreversible AI-assisted decisions. The mechanism is established at LLM-self-evaluation scale by MIRROR ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809)); deployment-scale replication is what the trial measures.

**Positioning (what we are testing in Phase 5):** Three audience-facing *surfaces* of the same practice; none declared validated until data lands. See § 0b.

**Regulatory tailwind:** EU AI Act Article 12 high-risk obligations apply **2026-08-02**. The practice happens to produce exactly the per-decision logging artifact Article 12 describes; that is *consequence*, not *purpose*.

---

## 0. Rationale — why and how we are building this

### 0.1 The thing itself, before anything downstream

**episteme is a way to think.** The full operationalization is at [`docs/THE_WAY_TO_THINK.md`](THE_WAY_TO_THINK.md). The one-line version:

> *A five-stage cognitive practice (Frame → Decompose → Execute → Verify → Handoff) made mechanical at the file system level, anchored on Kahneman's System-2 forcing function, Dalio's Radical Transparency, Boyd's OODA orientation, and Munger's Latticework of Mental Models. The practice is the product. The signed Reasoning Surface, the typed PTSP ledgers, the pre-tool-use gate, the standalone verifier, the Regulator Evidence Packet — these are scaffolding for the practice and residue from it.*

This Productization Plan exists because the practice has **downstream consequences** that different audiences buy for different reasons. Productization = naming those consequences honestly, testing which audience-facing surface lands, and not confusing any of them with the practice itself.

### 0.2 The operator's concern, made concrete

The thread that opened this productization cycle: an essay (in Korean) the operator surfaced during the Event 120 reframe conversation. Excerpt, translated:

> *"If I outsource my brain to an LLM wiki and get a second brain, will my brain get better, or will it atrophy?"*

The professional concern beneath the essay: when a model is *fluent and confident*, the human stops reading the diff. The audit trail records what the agent did, not what the human believed. The cognitive externalization that used to happen during deliberate effortful writing — stops happening. The model fills the cognitive space that the operator used to fill.

For most knowledge work this trade-off may be acceptable. For **irreversible decisions** — push, merge, deploy, migrate, publish, external-post — it is the failure mode the practice exists to counter.

### 0.2 The empirical anchor: only architectural constraint is effective

The MIRROR benchmark ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809)) measures whether LLMs translate self-knowledge into appropriate agentic action. Across 16 models from 8 labs and ~250,000 evaluation instances, the headline finding:

| Condition | Confident Failure Rate |
|---|---|
| Baseline (model self-evaluates) | **0.600** |
| External metacognitive control applied | **0.143** |

That is a 76% reduction at temperature 0; mean 70% across 5 frontier models at temperature 0.7. But the load-bearing claim is the paper's own sentence:

> *"Providing models with their own calibration scores produces no significant improvement (p > 0.05); only architectural constraint is effective."*

This is the causal mechanism rationale for episteme. The fix cannot be procedural ("ask the model to be careful"). The fix cannot be self-reflective ("ask the model to evaluate itself"). The fix has to be **structural** — an external constraint imposed by the agent's *environment* rather than by the model's *prompt*.

Two reinforcing findings from [arXiv 2509.09677](https://arxiv.org/abs/2509.09677) ("The Illusion of Diminishing Returns: Measuring Long-Horizon Execution in LLMs"):

1. Models exhibit a **self-conditioning effect**: prior LLM output in context is silently treated as fact in later steps, causing error compounding across multi-step trajectories.
2. **Scaling alone does not fix this.** Sequential test-time compute with explicit provenance does.

### 0.3 What the mechanism requires

Tracing the requirement chain from finding to artifact:

| Requirement (derived) | Why this and not the obvious alternative |
|---|---|
| The constraint comes from **outside the model** | MIRROR: model-internal calibration produces no improvement |
| The most defensible "outside" is the **operator** | Operator is the natural source of judgment for irreversible decisions on their own systems |
| The constraint must be **unforgeable by the model** | If the model can author the constraint, the human-in-the-loop claim collapses to a policy promise |
| The constraint must be **structurally typed** | If Knowns and Inferences are fungible strings, the model paraphrases prior inferences into "facts" and the self-conditioning fix dissolves |
| The constraint must apply **before** the irreversible action | Post-hoc trace constructs (Datadog, LangSmith, Langfuse) record what happened; they cannot prevent confident failure at the moment of authorization |
| The constraint must be **third-party verifiable** | The operator cannot be both party and auditor; auditor must verify without trusting episteme's runtime |
| The constraint must **follow the operator across substrates** | If the gate only exists on one platform, operators reroute to platforms without the gate — the constraint dissolves |

### 0.4 How each artifact realizes the requirement

What we have built (Event 121–122) and what each piece is required for:

| Artifact | Path | Realizes which requirement |
|---|---|---|
| **PTSP** typed Fact / Inference / Unknown / Assumption ledgers + Promotion Gate | `core/ptsp/` | Structurally typed constraint; counters self-conditioning |
| **Signed Reasoning Surface** envelope (Ed25519 + JCS canonicalization + RFC 3161 TSA shape + Sigstore Rekor inclusion shape) | `core/signing/` | Unforgeable cryptographic provenance |
| **Standalone verifier CLI** with deterministic exit codes | `src/episteme/verify/` | Third-party verifiable without trusting episteme runtime |
| **Operator authoring CLI** (`episteme surface author / sign / show / list / status / verify`) | `src/episteme/surface/` | Practical UX so the constraint actually gets authored |
| **Evidence viewer + Regulator Evidence Packet exporter** (`episteme evidence posture / register / show / alerts / packet build`) | `src/episteme/evidence/` | Operator self-audit; on-demand export for regulator request |
| **Pre-tool-use validator hook** (opt-in via `EPISTEME_SIGNED_SURFACE_REQUIRED=1`) | `src/episteme/hooks/signed_surface_validator.py` | The gate at the moment of irreversible action |
| **Substrate adapters** — Claude Code (existing reasoning-surface@1 hot path); Hermes (signed-surface bridge in build) | `core/hooks/`, `src/episteme/adapters/`, `.claude/` | Constraint follows the operator wherever they work |

### 0.5 What episteme deliberately is *not*

| Not | Because |
|---|---|
| Agent memory (Mem0, Letta, Memento, Karpathy LLM Wiki) | Those make agents remember on behalf of humans; episteme makes the human *think* at the gate |
| LLM observability (Datadog APM, LangSmith, Langfuse) | Those record what happened; episteme records what the operator *believed* before it happened |
| Guardrails (GuardrailsAI, NeMo Guardrails) | Those filter model I/O at execution; episteme constrains operator authorization upstream of execution |
| Compliance vendor (single-jurisdiction) | Compliance is a *downstream consequence* of the practice; not the practice's purpose |
| A prompt template / system-prompt addendum | Prompts can be skipped. A file-system hook that exits non-zero cannot. The practice has mechanical teeth. |
| An AI safety system (in the alignment-research sense) | episteme constrains *the human's* relationship to the AI, not the AI itself. Operator-side governance, not model alignment. |

This list is not adversarial — these tools are complements at *different layers*. § 2.7 has the layer diagram.

---

## 0a. Primary value claim (what we measure)

**Claim:** Adding an external architectural constraint (the signed Reasoning Surface) at the moment of an operator's irreversible decision reduces operator Confident Failure Rate substantially relative to a no-constraint baseline.

**Empirical status:**
- **Established (published literature):** MIRROR shows external architectural constraint reduces LLM-self-evaluation CFR by ~70% across 5 frontier models. The mechanism is established.
- **Open (deployment-scale):** Whether the same magnitude transfers to a human+kernel deployment (where the constraint is friction-bearing) is empirically open. Friction may suppress participation; structure may amplify benefit. The deployment-scale effect is what episteme's Phase 2 trial is designed to measure.

**Honesty discipline.** No marketing copy may cite "70.3%" or "~70% CFR reduction" as an episteme-measured number until our own dataset exists. Permitted forms:
- ✅ *"The MIRROR benchmark ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809)) shows external architectural constraint reduces LLM Confident Failure Rate from 0.60 to 0.14. episteme is designed to replicate this effect at human-in-the-loop deployment scale."*
- ❌ *"episteme reduces Confident Failure Rate by 70%."* (assumes measurement we haven't done)
- ❌ *"70.3% reduction (MIRROR-aligned target; OSF pre-registration TBD)."* (cites a pre-registration that doesn't exist)

---

## 0b. Positioning hypotheses (what we are testing — not yet validated)

Three positioning candidates. Each addresses a different buyer. None is declared the primary positioning until Phase 5 probe data lands.

| ID | Positioning | Primary audience | Probe |
|---|---|---|---|
| A | **Compliance Evidence Layer** — pre-action operator-signed structured artifact, AI Act Article 12 native | Chief Compliance Officer, Internal Audit, Notified Body assessor | Probe 1 (regulator outreach) |
| B | **Operator Decision Audit Trail** — your own externalized reasoning, signed by you, searchable later | Developer-operator who cares about their own judgment quality | Probe 2 (developer surfaces: HN, Lobsters, dev.to) |
| C | **Pre-Action Reasoning Commitment** — engineering-discipline forcing function for teams managing AI-assisted infra | Tech lead / staff engineer at growing teams adopting AI-assisted ops | Probe 3 (engineering-leadership channels) |

The original Event 121 framing prematurely declared A the primary positioning. The corrected framing tests A, B, and C in parallel with weighted probes and lets data choose.

---

## 0c. Audience clarity (primary vs derivative)

| Audience | Priority | Signal we measure |
|---|---|---|
| **Operator-as-user** (the person typing `episteme surface author`) | **Primary** | Surfaces authored / day; kernel hot-path firings; framework synthesis events; daily-user retention |
| Developer-operator considering adoption | Secondary | GitHub stars, substantive issues, external PRs, podcast/blog citations |
| CCO / Internal Audit / Notified Body | Tertiary | Direct outbound responses, paid pilot inquiries, regulator citation |

The Day-90 decision matrix (§ 3.5) weights operator-as-user signals **highest** — operators tell you the tool *works*; CCOs tell you it *sells*. Those are different questions and conflating them is the original Event 121 framing error.

---

## 1. Phase 3 — Technical Fortification (shipped Event 121–122)

### 1.1 Provenance-Tagged Step Pipeline (PTSP) — `core/ptsp/`

Counters the self-conditioning effect (arXiv 2509.09677). Each step boundary holds four disjoint ledgers — Fact / Inference / Unknown / Assumption. Inference → Fact promotion requires explicit evidence (operator cosign / deterministic test pass / external oracle attestation). Step N+1 context tags items non-fungibly so the model cannot silently treat a prior `<inference>` as a `<fact>`.

Invariants I1 (ledger disjointness) / I2 (irreversible promotion within session) / I3 (no Fact may depend on an unresolved Inference) / I4 (parent KNOWNS monotonic) / I5 (hash chain unbroken).

### 1.2 Signed Reasoning Surface `signed-surface@1.0` — `core/signing/`

Parallel-track to the live `reasoning-surface@1` schema. Adds cryptographic chain-of-custody.

| Threat | Counter |
|---|---|
| Non-repudiation of authorship | Ed25519 signature over RFC 8785 JCS canonical payload |
| Adversary alters past surface | Hash chain + Sigstore Rekor inclusion proof (shape in v1; live integration deferred) |
| Backdated rationalization | RFC 3161 third-party TSA timestamp (mock TSA in v1) |
| Auditor cannot verify without trusting episteme | Standalone verifier CLI; no episteme runtime dependency |
| Key compromise | Ed25519 key rotation via signed key-rotation event; CRL; historical surfaces remain verifiable up to revocation |

Zero-hard-dep posture: PyNaCl is optional (`pip install episteme[signing]`); when absent, the signing layer falls back to a structurally-distinguishable HMAC-SHA256 test mode (`test-hmac:` prefix). The verifier rejects test-mode signatures by default; `--allow-test-signatures` is required.

### 1.3 Standalone Auditor Verifier — `src/episteme/verify/`

Deterministic exit codes: 0 / 10 (signature) / 11 (timestamp) / 12 (transparency log) / 13 (chain break) / 14 (self-hash mismatch) / 20 (malformed) / 21 (key resolution) / 30 (batch mixed) / 64 (usage).

Invoked as `python -m episteme.verify` in v1. Single-file static binary via PyOxidizer / Nuitka explicitly deferred — the Python module form is already the load-bearing artifact; a static binary is feature creep for v1.

### 1.4 Substrate hooks

| Substrate | Adapter status | Signed-surface integration |
|---|---|---|
| **Claude Code** | Full (existing `core/hooks/reasoning_surface_guard.py` hot path; `.claude/settings.json` integration; plugin manifest) | Opt-in via `EPISTEME_SIGNED_SURFACE_REQUIRED=1`; new validator at `src/episteme/hooks/signed_surface_validator.py` runs ADDITIVELY in parallel with the existing guard |
| **Hermes** | Partial (existing `OPERATOR.md` sync via `src/episteme/adapters/hermes.py`) | In build — extends adapter to sync signed-surface schema + verifier reference + governance-block update to `~/.hermes/` |
| **Codex** | Name only (listed in pyproject keywords; no adapter code yet) | Future work; honest gap |
| **Cursor** | Name only (listed in pyproject keywords; no adapter code yet) | Future work; honest gap |
| **opencode** | Name only (mentioned in overview.md; no adapter code yet) | Future work; honest gap |

---

## 2. Phase 4 — Operator UX + Substrate Parity (shipped + in build)

### 2.1 Operator authoring CLI — `src/episteme/surface/` (shipped Event 122)

`episteme surface author` with interactive prompts + non-interactive `--core-question / --decision-choice / ...` args. Other subcommands: sign, show, list, status, verify (round-trip self-test against active surface). Persists to `.episteme/surfaces/<date>/<id>.json`; key under `.episteme/keys/operator_signing.{key,pub}` (mode 0600 on Unix).

### 2.2 Evidence viewer + packet exporter — `src/episteme/evidence/` (shipped Event 122)

Read-only terminal-first viewer. Subcommands:
- `posture` — Tier 1 KPI panel (decisions logged, signed%, chain breaks, test-mode sig count, high-tier count, by-tier / by-blast / by-operator breakdowns)
- `register` — Tier 2 filterable list (by since/until, operator fingerprint prefix, tier, reversibility, choice)
- `show <surface_id>` — Tier 3 detail drill-down (full schema fields, TSA + Rekor refs, file path)
- `alerts` — Tier 4 anomalies (test-mode signatures present, chain breaks, low-confidence high-risk proceeds, missing Article 79(1) triggers)
- `packet build --framework=<...> --output <.zip>` — Regulator Evidence Packet ZIP with MANIFEST.json + signature + surfaces + chains + public keys + transparency log + README

The full web dashboard (SvelteKit / Next.js) is deliberately **deferred** — terminal-first viewer covers operator self-audit; web dashboard is post-Probe-1 work if compliance positioning lands.

### 2.3 Pre-tool-use validator hook (shipped Event 122)

`src/episteme/hooks/signed_surface_validator.py` runs additively alongside the existing `core/hooks/reasoning_surface_guard.py` hot path. Opt-in via `EPISTEME_SIGNED_SURFACE_REQUIRED=1`. Matches irreversible-class Bash patterns (git push / git reset --hard / rm -rf / kubectl apply / terraform apply / *publish / aws s3 rm / drop|truncate table). Verifies the active signed surface; blocks via exit 2 with structured JSON remediation on stderr if invalid.

### 2.4 Hermes substrate parity (in build, Event 122 task #15)

Extends `src/episteme/adapters/hermes.py` to bridge signed-surface@1.0 into the Hermes substrate. What lands:
- `~/.hermes/SIGNED_SURFACE_PROTOCOL.md` — operator-facing workflow doc for Hermes sessions
- `~/.hermes/schemas/signed-surface-v1.0.json` — schema reference
- Governance-block addition to `~/.hermes/OPERATOR.md` mentioning the signed-surface workflow expectations
- Verifier reference path documented in OPERATOR.md so Hermes-running models know how to point operators at it

### 2.5 Codex / Cursor / opencode (honest gap)

Listed in pyproject keywords; no adapter code. These are *substrate-parity work* in the same lane as Hermes, not "ecosystem integrations" (which is a different category). Honest framing: episteme's substrate coverage today is "Claude Code (full) + Hermes (partial)" not "Claude Code, Codex, Cursor, Hermes."

### 2.6 Regulatory crosswalk as downstream artifact — `docs/COMPLIANCE_CROSSWALK.md`

Cell-by-cell mapping of `signed-surface@1.0` fields to EU AI Act Article 12/13/14/19/72, NIST AI RMF + GenAI Profile (NIST AI 600-1), and a financial-services framework set (Fed SR 11-7, OCC, EBA, MAS, OSFI, FINRA, SEC 17a-4(f)). This document is a **structural mapping** — evidence that the architecture happens to satisfy multiple regulatory obligation classes as a byproduct of being right. It is not the primary positioning, and we explicitly do not claim regulator validation until Probe 1 returns signal.

### 2.7 Layer diagram (not a competition matrix)

The Event 121 doc framed a "differentiation matrix" placing episteme on the same axis as Datadog, LangSmith, Langfuse, GuardrailsAI, Mem0, Letta. That framing is wrong — these tools operate at different layers and are complementary, not alternatives. Corrected diagram:

```
┌────────────────────────────────────────────────────────────────────┐
│ Layer 6 — OPERATOR DECISION COMMITMENT                             │
│    episteme (pre-action operator-signed Reasoning Surface)         │
├────────────────────────────────────────────────────────────────────┤
│ Layer 5 — GUARDRAILS (mid-execution I/O filters)                   │
│    GuardrailsAI, NeMo Guardrails                                   │
├────────────────────────────────────────────────────────────────────┤
│ Layer 4 — AGENT MEMORY (cross-session continuity)                  │
│    Mem0, Letta, Memento, Karpathy LLM Wiki                         │
├────────────────────────────────────────────────────────────────────┤
│ Layer 3 — LLM OBSERVABILITY (post-execution traces of LLM calls)   │
│    LangSmith, Langfuse                                             │
├────────────────────────────────────────────────────────────────────┤
│ Layer 2 — APPLICATION OBSERVABILITY (post-execution traces of app) │
│    Datadog APM, New Relic, Honeycomb                               │
├────────────────────────────────────────────────────────────────────┤
│ Layer 1 — INFRASTRUCTURE OBSERVABILITY                             │
│    Prometheus, OpenTelemetry collector                             │
└────────────────────────────────────────────────────────────────────┘
```

episteme is at Layer 6, alone. Tools at Layers 1–5 *consume* episteme attestations (via OTel metadata) or operate independently. A CCO does not pick episteme *instead of* Datadog — they pick episteme *as well as* Datadog. The defensive moat is the layer itself, not feature-by-feature competition.

---

## 3. Phase 5 — Reversible Probes (deferred — operator-gated)

### 3.1 Marketing copy (drafted; landing in README deferred)

Three candidate manifestos to test the three positioning hypotheses (§ 0b). All draft, all in `docs/MARKETING_COPY_DRAFT.md` (deferred to its own Event); none landed in `README.md` until probe signal arrives.

#### 3.1.1 Positioning A — Compliance Evidence Layer

```markdown
# episteme

**Cryptographically signed evidence that a real person — not the model — authorized every irreversible decision.**

The MIRROR benchmark ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809))
showed that LLMs left to self-evaluate commit confident failures at a 0.60
rate; external architectural constraint drops that to 0.14. The "external"
in that sentence is what episteme provides — and we provide it as
auditable, signed evidence that satisfies EU AI Act Article 12 logging
obligations as a byproduct of being right about the mechanism.
```

#### 3.1.2 Positioning B — Operator Decision Audit Trail

```markdown
# episteme

**Your own externalized reasoning, signed by you, searchable later.**

For most knowledge work, letting the model remember on your behalf is
fine. For irreversible decisions — push, merge, deploy, migrate — it is
the failure mode. episteme is a forcing function: before you authorize
the irreversible action, you write down what you know, what you don't
know, and what would prove you wrong. Then you sign it with a key the
model cannot reach. Six months later, when you wonder why you decided
what you decided, the surface is there, signed, dated, and unalterable.
```

#### 3.1.3 Positioning C — Pre-Action Reasoning Commitment

```markdown
# episteme

**The engineering-discipline forcing function for AI-assisted irreversible operations.**

Frontier models are good enough that engineers stop reading the diff.
The team's audit trail records what the agent did, not what the human
believed. episteme is the structural counter — every irreversible
action (push, deploy, migrate, publish) blocks at the gate until an
engineer authors a typed, signed Reasoning Surface. Knowns and
Inferences are non-fungible field types. The model cannot author the
surface; the agent's signing key access is structurally absent. The
team's audit trail records what was *believed*, not just what was *done*.
```

#### 3.1.4 "Skeptical view on second-brain tools" block (positioning-agnostic)

Same as previous draft, lightly edited. Lives in `docs/MARKETING_COPY_DRAFT.md`.

### 3.2 Probe 1 — Compliance positioning test (8 contacts)

| Contact | Why | Pathway |
|---|---|---|
| Head of AI Governance, EU-domiciled bank ≥ EUR 100B AUM (×3) | High-risk AI deployer under Art. 6; Art. 12 obligations live 2026-08-02 | LinkedIn outbound |
| AI Compliance Officer, EU insurer (×2) | Insurance is Annex III high-risk category | LinkedIn outbound |
| Notified Body AI conformity practice (TÜV, DEKRA, BSI) — assessor or partner (×2) | Direct line into Art. 19 conformity assessment | LinkedIn + cold email |
| DPO with AI mandate, EU healthcare provider (×1) | Annex III medical device overlap | LinkedIn outbound |

**Dropped from original list:** EU AI Office liaison personnel — no realistic outbound pathway from a solo-OSS project; listing implied backchannel access I don't have.

Outreach template content unchanged from current draft. Sending remains operator-gated — irreversible reputational action.

**Base-rate honesty:** cold outbound from a solo OSS project to compliance practitioners has a low response rate. Realistic expectation: 1–2 substantive responses out of 8. The Day-90 matrix in § 3.5 accounts for this base rate.

### 3.3 Probe 2 — Developer-operator positioning test

Lighter-touch than Probe 1. Surfaces episteme to the developer-operator audience via:

- Show-HN-equivalent post (Hacker News) with positioning B copy as the framing
- Lobsters submission
- dev.to / Substack technical writeup ("We pivoted episteme to test Calibration-Lift; here's why")
- Twitter/X thread tagging known commentators (Karpathy on LLM Wiki, Hashimoto on harness engineering)

Probe 2 is structurally cheaper than Probe 1 — single post, broad audience, low per-contact cost. The relevant signal: stars + substantive issues + external PRs + cited usage.

### 3.4 Probe 3 — Operator-as-user retention test

The lowest-overhead, highest-information probe. The operator + 2–3 willing colleagues use episteme on actual irreversible operations for 30 days, instrumented:

| Metric | Source |
|---|---|
| Surfaces authored | `.episteme/surfaces/` count |
| Validator hook firings (blocks vs allows) | hook telemetry log |
| Re-authoring rate after rejection | hook telemetry diff |
| Daily-active operators | session telemetry |
| Subjective: "did this surface a decision you would have otherwise made wrongly?" | weekly self-report (1 line) |

This is the cheapest test of the load-bearing claim. If the operator + colleagues themselves abandon episteme during the 30 days, no Probe 1 or Probe 2 signal can save the project.

### 3.5 Day-90 decision matrix (four outcomes, not three)

Operator-as-user signal is weighted highest. CCO inbound and developer-adoption signal are secondary.

| Outcome | Definition (all three sub-conditions required) | Decision |
|---|---|---|
| **Commercial spin-off** | Probe 3 retention ≥ 80% AND Probe 1 CCO inbound ≥ 2 AND paid pilot inquiry ≥ 1 | Form entity; take pilot revenue; hire 1 compliance lead; keep kernel MIT; license enterprise dashboard + framework exports |
| **OSS scale** | Probe 3 retention ≥ 80% AND Probe 2 (stars 500+ AND non-author contributors ≥ 5 AND cited usage ≥ 3) AND no commercial signal | Continue OSS at scale; pursue grant funding (EU Horizon, NLnet, OpenSSF); position publicly as developer-tool not commercial product |
| **Operator-first OSS sustain** (NEW vs Event 121) | Probe 3 retention ≥ 80% AND Probes 1+2 produce no broader-adoption signal | Keep kernel MIT; document honestly as "personal-and-small-circle compliance harness"; no commercial pivot, no marketing spin. The operator's continued use IS the validation. |
| **Sunset** | Probe 3 retention < 50% (operator + colleagues abandon during 30-day instrumentation) | Public post-mortem. The load-bearing claim failed at deployment scale even for the operator who designed it. Honest write-up of why. |
| **Adverse** (any time) | Critique invalidates a load-bearing claim (cryptographic, regulatory, or empirical) | Immediate written response; if critique holds, rewrite the claim |

**Why this matrix is asymmetric and operator-first:**

- The "operator-first OSS sustain" outcome (third row) is the corrected gap from Event 121. The operator's own continued use IS empirical validation of the load-bearing claim. Commercial absence is not failure.
- Probe 3 retention (operator + colleagues) is the gate condition on every positive outcome. If episteme fails the people who designed it, no external signal can prove it works.
- Probe 1 (CCO) and Probe 2 (developer) are *positioning tests*, not value-claim tests. Their function is to tell us *who buys* if there is a buyer — not whether the kernel does anything.

---

## 4. Reversibility ledger

| Action | Reversibility | Rollback path |
|---|---|---|
| Event 121–122 file additions (Phase 3 modules + 2 docs) | Reversible (local git, no push) | `git reset --hard` before push |
| Local commit | Reversible until pushed | `git reset` or amend |
| Push to remote `master` | Irreversible (public claim) | Operator-gated; not in current Event |
| README positioning swap | Irreversible (positioning claim) | Operator-gated; deferred to its own Event after probe signal |
| OSF pre-registration | Irreversible (timestamped public) | Amendment only via OSF amendment protocol — design feature |
| HN / Lobsters / LinkedIn / X posts | Effectively irreversible (caches) | Honest follow-up post if claims need correction |
| Probe 1 sent emails | Per-conversation reversible; cumulative reputational effect not | Operator-gated; maintain Probe 1 signed-surface log |
| Commercial entity formation | Irreversible at significant cost | Gate behind Day-90 commercial-spin-off matrix outcome ONLY |

---

## 5. Anti-self-deception protocol (noise-watch: status-pressure, false-urgency)

| Failure mode | Counter |
|---|---|
| Counting stars as proof of fit | Probe 3 retention is the gate condition; Probe 2 signal alone never crosses the matrix threshold |
| Mistaking engineer enthusiasm for compliance-buyer fit | Probe 1 contacts are the only CCO-inbound source counted toward commercial-spin-off |
| Allowing day-30 numbers to drive a permanent pivot | Pre-registered day-90 decision; no commercial action before then |
| Re-interpreting Null outcome as "needs more marketing" | The matrix is signed and timestamped; post-hoc reinterpretation requires a logged amendment |
| Confusing "regulator interested" with "regulator will require" | Single notified-body conversation is a signal, not a market |
| Treating the Compliance Evidence Layer positioning as already validated | The positioning is a *hypothesis under test* (Probe 1); no copy may claim "regulator-approved" or "AI Act compliant" until Probe 1 returns substantive engagement |

---

## 6. What this document does NOT claim

- The 70.3% / ~70% Confident Failure Rate reduction is **not** an episteme-measured number until a real human-in-the-loop trial runs. It is the MIRROR benchmark's published finding for the LLM-self-evaluation case; whether deployment-scale episteme replicates the magnitude is empirically open.
- "Compliance Evidence Layer" is **not** the declared positioning — it is one of three positioning hypotheses under structured testing in Phase 5. The primary value claim is operator Calibration-Lift; the positioning that fits buyers best is the question Probe 1 + Probe 2 + Probe 3 jointly answer.
- The substrate coverage is **not** "Claude Code, Codex, Cursor, Hermes." Honest current state is Claude Code (full) + Hermes (partial, in-build). Codex / Cursor / opencode are listed in pyproject keywords but have no adapter code.
- No regulator has reviewed or accepted `signed-surface@1.0` as satisfying any specific clause. Probe 1 is exactly the test of that.
- The CCO dashboard MVP, marketing copy in README, and commercial entity are not yet built and remain operator-gated.

This document is the **plan**, not the **proof**. The kernel-tone-discipline rule applies — governance surface stays precise about what the data does and doesn't show.
