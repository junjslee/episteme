<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->
# The Way to Think — 생각의 틀

> *"The product is a way to think when the model can finish your sentences."*

This is the **primary identity doc** for episteme. Everything else in this repository — the typed Reasoning Surface schema, the Ed25519 signing, the standalone verifier, the pre-tool-use gate, the Hermes substrate bridge, the Regulator Evidence Packet exporter — is *enforcement geometry* for the practice this document names. The practice is the product. The artifacts are residue.

If you came to episteme expecting agent memory, observability, guardrails, or compliance tooling, you're at the wrong layer. Those are downstream consequences (see § 7); they are not what the project is for.

---

## 0. Why a way to think

Frontier models in 2026 are fluent enough that the diff *looks fine* and the analysis *sounds right* and the operator stops actually thinking at the moment of decision. For everyday knowledge work this trade-off is acceptable — even desirable. For decisions that compound, drift, mislead, or cannot be taken back, it is exactly the failure mode the cognitive-governance literature has been warning about.

The MIRROR benchmark ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809)) settled the empirical question for LLM self-evaluation: across 16 models from 8 labs and ~250,000 evaluation instances, *"providing models with their own calibration scores produces no significant improvement; only architectural constraint is effective."* External architectural constraint reduces Confident Failure Rate from 0.60 to 0.14. The constraint cannot come from within the model. It cannot come from a better prompt. It has to come from outside — most defensibly, from a human practicing a specific way to think at the moment of irreversible action.

This document names that way of thinking. It is not original to episteme. It is operationalized — turned into something an LLM has to respect, something an operator practices daily, something a third party can verify happened.

---

## 1. The practice, in five stages

The five-stage workflow is authored in [`core/memory/global/workflow_policy.md`](/Users/junlee/episteme/core/memory/global/workflow_policy.md). episteme's job is to enforce it at moments that matter.

### 1.1 Frame
Define the objective. State the success metric. Declare exactly **one Core Question** for this cycle.

| Cognitive move | What it forces | Artifact field |
|---|---|---|
| Name the Core Question | Counters question substitution (Kahneman System 1's substitution failure) | `surface.core_question` (min 20 chars) |
| Build the distinction map | Forces explicit separation of **Knowns** / **Unknowns** / **Assumptions** | `surface.{knowns,unknowns,assumptions}[]` |
| Declare constraint regime | Surfaces what is allowed, forbidden, costly | `risk_classification` |
| Classify reversibility | Names whether this decision can be unmade | `risk_classification.reversibility` |
| Identify the uncomfortable friction driving the work | Counters solution-first behavior | (operator-authored; cited in `core_question`) |

A Frame that skips the Core Question is not a Frame; it is solution-first reasoning wearing planning vocabulary. The validator rejects surfaces whose `core_question` is shorter than 20 characters or matches the lazy-placeholder list (`tbd`, `n/a`, `see above`, `해당 없음`, …) — not because length is the point, but because length under that threshold structurally cannot encode a Core Question.

### 1.2 Decompose
Convert the Frame into operational tasks.

| Cognitive move | What it forces | Artifact field |
|---|---|---|
| Why → How translation | Converts philosophical diagnosis into measurable mapping | (operator-authored prose; cited in `decision` rationale) |
| Options + tradeoffs (≥ 2 for high-impact) | Counters anchoring to the first framing | (operator-authored; visible in surface drafts) |
| Because-chain (signal → cause → decision) | Forces causal articulation, not pattern-match | (operator-authored prose) |
| Working hypothesis (thinking as a bet) | Names what you are betting on | `decision.choice` + `decision.confidence` |

### 1.3 Execute
Run one bounded task per owner. Prefer reversible moves first. Record assumptions when data is incomplete.

| Cognitive move | What it forces | Artifact field |
|---|---|---|
| Reversibility-first execution order | Counters planning fallacy (Kahneman) | `risk_classification.reversibility` gate |
| Record assumptions | Marks load-bearing beliefs so they can be falsified | `assumptions[]` with `if_wrong_then` + `detectability` |

### 1.4 Verify
Validate against the success metric, not effort spent. Distinguish proven facts from inferred conclusions. Explicitly mark residual unknowns at handoff time. Evaluate hypothesis result.

| Cognitive move | What it forces | Artifact field |
|---|---|---|
| Disconfirmation conditions (pre-committed) | Robust Falsifiability — Popper, enforced by the file system | `disconfirmation_conditions[].observable` + `measurement_method` |
| Distinguish proven from inferred | Counters narrative fallacy (Taleb/Kahneman) | PTSP Fact vs Inference typed ledgers (§ 5.2) |
| Mark residual unknowns | Counters WYSIATI (Kahneman) | `unknowns[].cost_of_ignorance` (min 30 chars) |
| Hypothesis evaluation: validated / refined / invalidated | Keeps thinking as a bet, not as a story | (post-action; operator-authored update to the surface chain) |

### 1.5 Handoff
Update authoritative docs (`docs/PLAN.md`, `docs/PROGRESS.md`, `docs/NEXT_STEPS.md`). Capture unresolved risks and the exact next action.

| Cognitive move | What it forces | Artifact field |
|---|---|---|
| Persist reasoning to disk, not chat | Counters reliance on transcript memory | Signed surface persisted to `.episteme/surfaces/<date>/<surface_id>.json` |
| Hash chain across the session | Counters tampering and post-hoc rationalization | `envelope.parent_surface_hash` + `self_hash` |
| Signed by the operator's key | Counters forgery by the agent or anyone else | Ed25519 signature over JCS-canonical payload |

---

## 2. The Decision Engine — operational thinking rules

Authored in [`core/memory/global/cognitive_profile.md`](/Users/junlee/episteme/core/memory/global/cognitive_profile.md) § Decision Engine. Each rule is a counter to a named failure mode:

| Rule | Counters | How episteme enforces |
|---|---|---|
| Convert *why* → *how* quickly | Vague philosophical diagnosis with no measurable next action | Core Question must be answerable; validator rejects lazy placeholders |
| Govern with one Core Question | Multiple loose questions blur signal | Schema permits exactly one `core_question` field |
| Start from uncomfortable friction | Curiosity-driven exploration that never lands | Surface must declare the *uncomfortable friction* in the operator's own words |
| Form explicit hypothesis early (*A likely works because B*) | Floating reasoning that never commits | `decision.choice` + `decision.confidence` with elicitation method |
| Strict utility filter: *so what is the cost of staying ignorant?* | Information collection without operational utility | `unknowns[].cost_of_ignorance` (min 30 chars; operator-authored) |
| Rebuild ideas in your own language | Quoting authority without understanding | Surface text must pass LLM-paraphrase classifier check (the model couldn't have authored it) |
| Invite audit of reasoning paths, not just conclusions | Conclusion-only handoffs lose the chain | The signed surface IS the reasoning path; reasoning is the persisted artifact |

---

## 3. Signal vs Noise — the pre-action checklist

Before any major action, answer briefly (from [`workflow_policy.md`](/Users/junlee/episteme/core/memory/global/workflow_policy.md) § Signal-over-Noise Rules):

1. **What is the signal?** (objective evidence)
2. **What is the noise?** (fear, regret, status pressure, speculation)
3. **What action is justified by signal only?**
4. **What evidence would disconfirm the current plan?**
5. **So what is the concrete cost of remaining ignorant here?**

If these cannot be answered, do not escalate execution scope. The reasoning_surface_guard hot path treats unanswerable surfaces as `exit 2` blocks at the pre-tool-use gate.

---

## 4. Cognitive Red Flags — when to slow down

From [`cognitive_profile.md`](/Users/junlee/episteme/core/memory/global/cognitive_profile.md) § Cognitive Red Flags. If any of these appears, slow down and reframe before execution:

- false urgency without explicit impact analysis
- emotional over-weighting of one recent event
- solution-first behavior without clear problem statement
- hidden assumption not stated as assumption
- collecting more information without a core question or hypothesis
- inability to state the practical cost of ignorance (*so what?*)

The surface schema makes each of these violations a structural failure — hidden assumptions surface as missing `assumptions[]` entries; missing problem statements surface as short `core_question` text; solution-first behavior surfaces as missing `disconfirmation_conditions[]`.

---

## 5. Why the practice has to be mechanical (not procedural)

Asking the model to be careful does not work — proven by MIRROR. Asking the model to evaluate itself does not work — proven by MIRROR, and worse: intrinsic self-correction without an external signal measurably *degrades* accuracy ([arXiv 2310.01798](https://arxiv.org/abs/2310.01798)). Asking the operator to be careful does not work either, at frontier model strength — willpower-as-vigilance fails when the model is fluent and the deadline is close. The constraint must be a wall, not advice.

But a wall has a precise limit the v1 kernel under-weighted: **a wall can guarantee that the epistemic work happened; it cannot tell thinking from theater.** Form-checks — field presence, minimum lengths, lazy-token lists — are satisfiable by reasoning-shaped tokens ([arXiv 2410.07137](https://arxiv.org/abs/2410.07137)), and rigid schemas measurably degrade the reasoning they are meant to capture ([arXiv 2408.02442](https://arxiv.org/abs/2408.02442)). The v2.0 division of labor (see [`DESIGN_V2_0_EPISTEMIC_ENGINE.md`](DESIGN_V2_0_EPISTEMIC_ENGINE.md)):

- **The wall** (deterministic): routes decision shapes, validates artifact contracts (exists, fresh, non-vacuous, verdict-consistent), hard-blocks only destructive operations, and chains every record. MIRROR's lesson stands — this layer is why the practice survives deadline pressure.
- **The judge** (model, factored): substance is checked by a fresh context that never sees the draft — decomposed claims verified against external evidence (file reads, execution, search), an assigned opposition rather than a neutral review. Independence of the checking signal is the load-bearing property ([arXiv 2309.11495](https://arxiv.org/abs/2309.11495)); a verifier that reads the reasoning it checks inherits its errors.
- **Neither does the other's job.** A wall that tries to judge substance becomes a Goodhart target; a judge with no wall gets skipped at deadline.

This is why the artifacts under `core/` and `src/episteme/` exist. They are not the product; they are the wall — and, as of v2.0, the dispatcher for the judge.

### 5.1 The mental models that justify the mechanical posture

From [`cognitive_profile.md`](/Users/junlee/episteme/core/memory/global/cognitive_profile.md) § Foundational Mental Models — these are not citations to perform sophistication; they are the operating system beneath the protocol:

| Model | What it says | What episteme builds against it |
|---|---|---|
| **Dual-Process Theory** (Kahneman) | System 1 is fast, automatic, pattern-matching. System 2 is slow, deliberate, effortful. LLMs are maximally prone to System 1 failure. | Reasoning Surface is a System 2 forcing function. Every required field counters a specific System 1 failure mode (WYSIATI → Unknowns field; question substitution → Core Question; anchoring → Disconfirmation; narrative fallacy → Knowns/Inferences separation; planning fallacy → inversion via Disconfirmation; overconfidence → calibrated confidence elicitation). |
| **Radical Transparency** (Dalio) | Remove ego from truth-finding. Surface uncertainty even when it makes you appear less capable. Believability-weighting over authority-weighting. | Surface text must include real Unknowns with operator-authored `cost_of_ignorance`. Lazy "I don't know" placeholders are structurally rejected. |
| **OODA Loop** (Boyd) | The side that completes Observe-Orient-Decide-Act loops faster wins. But Orientation is what matters most — you decide from your model of reality, not from reality. | episteme IS the Orientation infrastructure. Small reversible actions close loops quickly; large irreversible bets collapse multiple loops into one and eliminate the correction feedback would have provided. |
| **Latticework of Mental Models** (Munger) | Every model has structural blind spots. Models from different domains have non-overlapping blind spots. Convergence across lenses increases confidence; conflict is information. | Before any high-impact decision, the surface should be reasoned through ≥ 2 lenses (Inversion, Second-order, Base rates, Margin of safety). Convergence → proceed. Conflict → mandatory investigation, not tiebreaker. |

### 5.2 The self-conditioning correction

[arXiv 2509.09677](https://arxiv.org/abs/2509.09677) ("The Illusion of Diminishing Returns") added a finding directly load-bearing for episteme's PTSP layer: models exhibit a **self-conditioning effect** where prior LLM output in context is silently treated as fact in later steps. Errors compound across multi-step trajectories. *Scaling alone does not fix this.* Sequential test-time compute with **explicit provenance** does.

This is why episteme has typed `Fact` and `Inference` ledgers (`core/ptsp/`) as non-fungible types. Model output enters as `Inference`; it cannot be promoted to `Fact` without operator co-sign, deterministic test pass, or external oracle attestation. The model cannot paraphrase its own conjecture into your fact.

---

## 6. How episteme operationalizes the practice

The practice maps to artifacts that fall into three lanes:

### 6.1 Operator-side scaffolding (the practice lived in)

| Artifact | What it does | Source |
|---|---|---|
| Reasoning Surface schema (`signed-surface@1.0`) | Typed structure of the cognitive moves; non-fungible field types | `core/signing/canonical_surface.py` |
| `episteme surface author` | Authoring UX with interactive prompts + non-interactive flags | `src/episteme/surface/` |
| Operator-controlled signing key | Proof the human did the practice (not the model) | `.episteme/keys/operator_signing.{key,pub}` |
| Hash chain across surfaces | The practice survives across decisions; the trail cannot be silently rewritten | `envelope.parent_surface_hash` |
| `episteme evidence` viewer | Operator self-audits their own practice — posture / register / drill-down / alerts | `src/episteme/evidence/` |

### 6.2 Agent-side enforcement (the practice the model is forced to respect)

| Artifact | What it does | Source |
|---|---|---|
| Pre-tool-use validator hook | Blocks irreversible-class action until a valid signed surface exists | `core/hooks/reasoning_surface_guard.py` (default) + `src/episteme/hooks/signed_surface_validator.py` (opt-in signed-surface variant) |
| PTSP typed ledgers | Forces context injection to distinguish `<fact>` from `<inference>` in next-step prompts | `core/ptsp/` |
| Promotion Gate (Invariants I1–I5) | An `Inference` cannot become a `Fact` without explicit external evidence | `core/ptsp/promotion.py` |
| Substrate adapters (Claude Code, Hermes) | Practice follows the operator across substrates; same gate exists wherever the operator works | `core/hooks/`, `src/episteme/adapters/hermes.py`, `adapters/claude/` |

### 6.3 Third-party verification (the practice provable to anyone)

| Artifact | What it does | Source |
|---|---|---|
| Standalone `episteme verify` CLI | Independent verification of any signed surface; runs without trusting the episteme runtime | `src/episteme/verify/` |
| `episteme evidence packet build` | On-demand ZIP packet for auditor / regulator / future-self / new-teammate review | `src/episteme/evidence/_packet.py` |
| Sigstore Rekor inclusion-proof shape | Append-only off-system witness (live integration deferred per `docs/LIVE_REKOR_DECISION.md`) | `core/signing/transparency.py` |
| RFC 3161 TSA timestamps | Independent third-party time-binding | `core/signing/tsa.py` |

---

## 7. What falls out — downstream consequences

When the practice is taken seriously and mechanically enforced, useful side effects fall out. None of these is the product:

- **Decision archaeology.** Six months later when someone asks why you decided what you decided, your signed surface is there — readable, dated, unalterable.
- **Compliance evidence.** The EU AI Act Article 12 (record-keeping), Article 13 (deployer transparency), Article 14 (human oversight) obligations happen to want exactly what the practice produces. NIST AI RMF + GenAI Profile, Fed SR 11-7, EBA Guidelines on ML, MAS FEAT, OSFI E-23, FINRA Reg Notice 24-09, SEC 17a-4(f) — same pattern. See [`docs/COMPLIANCE_CROSSWALK.md`](COMPLIANCE_CROSSWALK.md). Compliance is a *downstream* property of being right about the mechanism, not the headline.
- **Cross-team coherence.** When everyone on a team authors against the same schema, post-hoc disagreements have the same vocabulary to argue in.
- **Onboarding artifact.** A new teammate reading your last 50 signed surfaces sees how you actually thought, not just what you actually shipped.
- **Anti-cognitive-atrophy.** The Korean essay's question — *"내 뇌가 퇴화하게 될까"* — gets a structural answer: the practice keeps your judgment present at the moments that matter most. The brain that practices stays a brain.

---

## 8. The negative space — what episteme is not

| Not | Because |
|---|---|
| **Agent memory** (Mem0, Letta, Memento, Karpathy LLM Wiki) | Those make agents remember on behalf of humans. episteme makes humans think at the gate. Different layer in the operator-decision-vs-agent-runtime stack. |
| **LLM observability** (Datadog APM, LangSmith, Langfuse) | Those record what the agent did. episteme records what the operator *believed* before the agent acted. Different artifact. |
| **Guardrails** (GuardrailsAI, NeMo Guardrails) | Those filter model I/O at execution. episteme constrains operator authorization *upstream* of execution. Different point in the loop. |
| **Compliance vendor** (single-jurisdiction tool) | Compliance is a downstream consequence, not the product. The practice came first; the regulator-shape happened to fit. |
| **A prompt template** | Prompts can be skipped. A file-system hook that exits non-zero cannot. The practice has mechanical teeth. |
| **An AI safety system** (in the alignment-research sense) | episteme constrains *the human's* relationship to the AI, not the AI itself. It is operator-side governance. The AI's behavior is downstream of what the operator authorizes. |

---

## 9. Who this is for

Anyone whose work involves irreversible decisions that compound under cognitive load, working alongside frontier AI fluent enough that *"I should have read the diff"* is a real risk.

Concretely: engineers managing production state. Researchers running experiments that mutate data pipelines. Compliance leads who need defensible audit trails. Tech leads adopting AI-assisted ops who want their team's reasoning to survive post-mortems. Operators of any AI-assisted process where the cost of confidently-wrong action is not bounded by *"oh well, I'll redo it."*

Explicitly **not** for: chatbot-style ask-and-answer interactions where nothing irreversible follows from the conversation. The practice would be friction for friction's sake. The cost of staying ignorant must exceed the cost of the practice — otherwise the practice should not run.

---

## 10. Pointers — where the practice is authoritatively defined

The practice this document operationalizes is **already authored** in operator-controlled docs that predate this Event. THE_WAY_TO_THINK.md is the index, not the source.

| Source | What lives there |
|---|---|
| [`core/memory/global/cognitive_profile.md`](/Users/junlee/episteme/core/memory/global/cognitive_profile.md) | Core Philosophy, Decision Engine rules, Decision Protocol, Collaboration Stance, Cognitive Red Flags, Foundational Mental Models (Kahneman / Dalio / Boyd / Munger) |
| [`core/memory/global/workflow_policy.md`](/Users/junlee/episteme/core/memory/global/workflow_policy.md) | The 5-stage workflow (Frame → Decompose → Execute → Verify → Handoff), Signal-over-Noise rules, Risk and Autonomy Policy, Project Memory Contract |
| [`core/memory/global/operator_profile.md`](/Users/junlee/episteme/core/memory/global/operator_profile.md) | Per-axis profile values (failure-first lens, loss-averse posture, fence_discipline, etc.) the practice tunes against |
| [`core/memory/global/agent_feedback.md`](/Users/junlee/episteme/core/memory/global/agent_feedback.md) | Universal + universal-principled rules the practice respects (positive vs negative system framing, kernel-tone-discipline, no AI co-author trailers) |
| [`docs/COMPLIANCE_CROSSWALK.md`](COMPLIANCE_CROSSWALK.md) | The downstream regulatory-mapping artifact — *what falls out* of the practice for AI Act / NIST / financial-services frameworks |
| Private operator notes (`~/episteme-private/docs/PRODUCTIZATION_PLAN.md`) | How the practice gets carried to additional audiences via positioning probes — GTM strategy held in operator's private notes, not in the public repo |

---

## 11. The one-line, and the longer line

**One line:** *episteme is a way to think — 생각의 틀 — an epistemic engine that makes AI-assisted decisions earn their confidence: structure guarantees the thinking happens; factored verification checks it was real.*

**Longer line:** Frontier models are now fluent enough that the diff *looks fine* and the conclusions *sound right* and the operator stops actually thinking at the moment of decision. For everyday work this is fine. For decisions that cannot be taken back, it is the failure mode the cognitive-governance literature has been warning about. episteme is the structural counter — a five-stage cognitive practice (Frame → Decompose → Execute → Verify → Handoff) made mechanical at the file system level. The practice is the product. The signed Reasoning Surface, the typed PTSP ledgers, the pre-tool-use gate, the standalone verifier, the regulator evidence packet — these are scaffolding for the practice and residue from it. Without the practice they are theater. With the practice they are how the practice survives at frontier model strength, when willpower-as-vigilance does not.

You will type more. You will move slower at the irreversible gate. Your judgment will stay present where it used to silently go absent. Six months from now when something asks you why you decided what you decided — an auditor, a teammate, your future self — your own reasoning will be there: readable, verifiable, dated, unalterable.

That is not compliance. That is what it means to keep thinking while the model finishes your sentences.
