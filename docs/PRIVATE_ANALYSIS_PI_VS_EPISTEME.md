# Private Analysis — pi.dev vs episteme: where the layers actually sit, and where episteme is structurally weak

**Status:** private. Not committed. Operator decides whether to promote, gitignore, or shred.
**Triggered by:** operator request 2026-05-07 with pi.dev landing page + Pi explainer-video transcript ("I deleted Claude Code last week"). Operator framing: "is this what episteme solves? this information is GOLDEN — evaluate if episteme was built the right way, find faults/flaws, make it better."
**Method:** swing-review skill (steel-man → 3-vector adversarial attack → severity classification → counter-proposals → verdict).
**Author:** the agent in this session, under the operator's direct-critique posture (operator profile: failure-first / causal-chain / first-principles / direct-critique / loss-averse / fence-discipline 4).

---

## TL;DR (for the impatient operator)

1. **Pi.dev is not a competitor to episteme.** Pi sits in the **harness/execution slot** (same as Claude Code, Cursor, opencode). Episteme's stated thesis sits **above** the harness slot in the cognitive-governance slot. The video's argument that "Pi makes Claude Code obsolete" is a within-layer argument; it does not touch episteme's layer at all.

2. **But the comparison forces a real test.** Pi explicitly disclaims everything episteme adds (governance, structured reasoning, operator profile, pre-tool enforcement). That makes Pi the **clearest substrate gap pi leaves** — and it tells you exactly where episteme is at risk of being unnecessary: any harness that *closes* the gap pi leaves would compete with episteme directly, not with Pi.

3. **The disconfirmation declared in the surface fired in the *opposite* direction.** I asked: does kernel/ + active hooks reduce to a bounded Pi extension without semantic loss? Answer: **no for the enforcement layer** (Pi has no PreToolUse-equivalent), **yes for the markdown corpus** (the kernel is markdown by design and is already substrate-portable). This means the markdown-vs-enforcement claims in the architecture docs are *fused* in the marketing surface but are *structurally separable* — and the docs do not currently make that separation explicit. That is a real flaw.

4. **Verdict: FAIL by the swing-review rubric (1 Critical with viable mitigation + 5 Major findings).** Not "scrap it." Not "Pi is going to win." But: episteme has 6 named gaps to close before its layer-distinction claim is fully defended against the comparative challenge Pi raises.

5. **The single most important counter-proposal:** publish a one-page **layer map** that puts Pi/CC/Cursor/opencode on the harness layer, episteme on the cognition layer, and shows the **enforcement-primitive matrix** (which substrates expose pre-tool hooks, which only expose message injection, which expose neither). That diagram is the marketing surface that today is missing — and it is the artifact that turns "Pi is GOLDEN, are we built right?" from a panic question into a settled architectural fact.

---

## Phase 1 — Steel-Man

### What is Pi.dev?

Quoting the landing page directly:

- Tagline: *"There are many agent harnesses, but this one is yours."*
- Positioning: *"Pi is a minimal terminal coding harness. Adapt Pi to your workflows, not the other way around."*
- Extension API capabilities (verbatim from the page text):
  - "Extensions can inject messages before each turn"
  - "filter the message history"
  - extensions get "access to tools, commands, keyboard shortcuts, events, and the full TUI"
  - "implement topic-based compaction, code-aware summaries"
- Governance posture (verbatim): *"No permission popups. Run in a container, or build your own."*
- No structured reasoning artifacts. No operator-profile / cognitive-style configuration. Context engineering surfaces named: AGENTS.md, SYSTEM.md, Skills, prompt templates, dynamic context.

### Steel-man for Pi (the strongest version of the case Pi is making)

Pi optimizes for **harness-layer plurality**: every developer should be able to mutate the harness itself, not just configure it. The pitch is right that Claude Code and Cursor today are *rented harnesses* — the user doesn't own the abstraction; Anthropic / Cursor team does, and every release can change the system prompt, the tools, the lifecycle. A TypeScript-extension-with-hot-reload model is genuinely a stronger ergonomic substrate than a hook config in JSON. Pi is correct that **same model + better harness > better model + worse harness** for many real workflows. The video's claim that this redistributes power from harness vendors to harness users is true at the harness layer.

### Steel-man for episteme (the strongest version of why episteme exists)

Episteme is explicitly NOT in the harness slot. From `docs/LAYER_MODEL.md`:

> "episteme is the governance and identity layer that sits above agent platforms. The platforms are delivery vessels; episteme is the authority. … No single agent platform is authoritative. episteme is. A context reset in Claude Code, a new Codex session, or a Cursor workspace change does not reset your identity — only episteme holds that."

From `kernel/CONSTITUTION.md` (the philosophical root):

> "The danger is not incompetence. It is confident wrongness. … episteme is orientation infrastructure. It is the layer that shapes the agent's worldview before any observation in a new context."

Episteme's claim is that the harness layer is necessary but insufficient. A better harness lets the model run faster; it does not address the fact that **fluent text production is uncorrelated with epistemic correctness** — the failure mode that the constitution names as the project's reason to exist. The Reasoning Surface (`kernel/REASONING_SURFACE.md`) is a feedforward gate: knowns / unknowns / assumptions / disconfirmation must be declared *before* an action with blast radius. That gate fired in this session — the kernel refused to let me run a high-impact bash op until the stale surface was refreshed. That is empirically distinct from anything Pi offers.

The architectural separation is real and load-bearing:

| Layer                        | Concern                                                | Pi.dev | Claude Code | Cursor | opencode | episteme |
| ---                          | ---                                                    | ---    | ---         | ---    | ---      | ---      |
| Cognition / governance       | What does "good reasoning" mean here? What's unknown?  | —      | —           | —      | —        | ✅       |
| Harness / execution          | Tools, sessions, compaction, model switching           | ✅     | ✅          | ✅     | ✅       | —        |
| Substrate / model            | The CPU                                                | (any)  | Anthropic   | (any)  | (any)    | —        |

Pi competes in row 2. Episteme competes in row 1. If the layer model holds, **Pi's success is good news for episteme** — more substrates to ride on, fewer ergonomics objections to inheriting episteme's cognitive contract, and Pi's explicit AGENTS.md support means episteme's vendor-neutral policy artifact already drops in cleanly.

That is the steel-man. Now the attack.

---

## Phase 2 — Adversarial Attack

### Vector A — Logical Soundness

#### 🔴 Critical / Finding 1: The "kernel is markdown, ports anywhere" claim fuses two distinct claims

**Vector:** Logical Soundness.

**What:** `docs/LAYER_MODEL.md` says: *"Not model-specific. The kernel is markdown. It injects into any runtime that accepts system-level context. The platform is the delivery vessel. The kernel is what travels in it."* This phrasing fuses two claims that are structurally separable:

- **Claim α (cognition portability):** the *markdown corpus* (`kernel/*.md`, `AGENTS.md`, `core/memory/global/*.md`) ports to any runtime that accepts system-level context. This is true — any LLM that reads a system prompt or AGENTS.md inherits the orientation.
- **Claim β (enforcement portability):** the *Reasoning Surface enforcement* (the actual feedforward gate that fired on me twice in this session, refusing to let bash run on a stale surface) ports to any runtime. This is **not** true. The gate runs in Claude Code's `PreToolUse` hook surface. Pi exposes "message injection before each turn" (system-prompt augmentation, not tool-call interception) and "message filtering" (post-hoc cleanup). Codex skills and opencode subagents likewise have no pre-tool primitive equivalent.

The flaw: the marketing surface and `LAYER_MODEL.md` present α and β as one claim. The hook layer is at the heart of episteme's distinct value (it's the feedforward control mechanism named in the constitution), but β is what makes that mechanism real, and β is currently CC-only.

**Impact:** A reader who tries episteme on Pi or Codex today gets the markdown corpus working (orientation injects fine) but does not get the gate firing. They would conclude "episteme is just structured prompts" — and they would be partly right *under that runtime*. The constitution's central claim (feedforward, not feedback) silently degrades to feedback when β is unavailable. This is the gap Pi makes most visible because Pi's whole pitch is "you own the harness layer, not the cognition layer" — Pi users will arrive at episteme expecting cross-tool enforcement and find they got cross-tool advisory.

**Fix:** In `docs/LAYER_MODEL.md`, `docs/HARNESSES.md`, and the README, **separate the two claims into a 2x4 enforcement-primitive matrix**:

```
                                    | CC     | Pi     | Codex  | opencode |
Cognition layer (markdown)          | ✅     | ✅     | ✅     | ✅       |
Enforcement layer (pre-tool gate)   | ✅     | ⚠️ msg | ❌     | ⚠️ subag |
                                    |        | inject |        | invoke   |
```

Then write the substrate-bridge note explicitly: "Episteme runs in *advisory mode* on runtimes that lack a pre-tool hook primitive. Advisory mode preserves orientation but degrades from feedforward to feedback control. Today only Claude Code provides full feedforward enforcement; Pi and opencode provide partial enforcement via message-injection / subagent-invoke patterns; Codex provides cognition only."

Then publish a roadmap line for *each* substrate showing the path from advisory → full feedforward (or the architectural impossibility, named).

**Trade-off:** This admits, in writing, that the cross-tool claim is partially aspirational today. That is operator-aligned (loss-averse + direct-critique posture demands it), but the README rewrite that landed in Event 113 currently leans into the cross-tool framing without the asterisk. Adding the asterisk reduces marketing punch by ~one notch in exchange for a much stronger truthfulness signal in front of an audience (Pi users, ex-CC users) who will examine the claim closely.

#### 🟠 Major / Finding 2: Layer-distinction is asserted but never empirically tested in the artifacts

**Vector:** Logical Soundness.

**What:** Episteme's whole architecture rests on the claim that there is a *cognition layer* genuinely above the *harness layer* and that the cognition layer adds non-trivial value the harness layer cannot. This is asserted across `kernel/CONSTITUTION.md`, `docs/LAYER_MODEL.md`, `docs/POSTURE.md`. It is not measured anywhere in the repository.

The constitution itself, by Principle I, demands measurement: *"Hidden assumptions are objectives in disguise."* The hidden assumption here is that "cognitive governance" produces a measurable outcome difference vs same-model + same-task without the kernel. If that assumption is wrong, every line of `kernel/*.md` is well-written orientation theater.

**Impact:** When Pi or any next-gen harness offers stronger ergonomics, the operator (and any potential adopter) has no falsifiable artifact to point at and say "here is the lift." The base-rate lens (operator's own lens stack) is unforgiving on this class — most "cognitive frameworks" fail because they add ceremony without measurable lift, and the ones that succeed are the ones that produced their lift evidence early.

**Fix:** Add `benchmarks/cognitive-lift-baseline/` with at least one paired comparison: same task, same model, identical seed; one run with `EPISTEME_KERNEL_DISABLED=1`, one run with the kernel hooks live. Measure: (a) rate of confident-wrong outputs on a held-out task set; (b) time-to-disconfirmation when the operator plants a falsifiable error; (c) rollback frequency under cascade:architectural workloads. Even a single result that shows non-trivial lift is more defensible than the entire `REFERENCES.md` corpus, because it makes the central claim falsifiable.

**Trade-off:** This is hard. Designing a good cognitive-lift benchmark is its own research project, and a poorly-designed one would damage the project worse than no benchmark. Suggest: start with an *internal* private benchmark not published; use it to recalibrate kernel design; only publish once a stable lift signal exists. The cost of doing nothing is unbounded — the cost of doing it badly is bounded by "don't publish until the methodology survives swing-review."

### Vector B — Edge Case Assault

#### 🟠 Major / Finding 3: Episteme has no escape hatch for cognition-about-cognition (meta-reasoning under load)

**Vector:** Edge Case.

**What:** This very session demonstrates the edge case empirically. The hook fired three separate times during my analysis of whether the hook regime is correctly designed. That is *functionally* correct (the hook can't introspect topic) but *structurally* it means: **the kernel is the friction during any redesign of the kernel**. There is no operator-flagged mode for "I am specifically working on improving the kernel itself; please hold the gate enforcement at advisory only."

For most operators on most projects this is a non-issue. For this project — where the kernel *is* the product — it produces a real per-turn tax. Each meta-cognition turn pays the same staleness check that protects the kernel from drift in unrelated work.

**Impact:** Two second-order effects: (a) the operator may unconsciously route around the kernel's friction by editing files outside its enforcement zone (e.g., `docs/private/*` or `archive/`), bleeding kernel-architecture work into ungated paths; (b) any external contributor trying to improve the kernel hits the same friction with no context, which raises the contribution barrier in exactly the way Pi's "you own the harness, write 10-line extensions" pitch lowers it.

**Fix:** Add a `kernel-edit-mode` flag to `.episteme/advisory-surface` (or a separate `.episteme/meta-mode` marker file) that, when present, downgrades the staleness check from cascade:architectural to advisory + audit-log-only for changes in `kernel/`, `hooks/`, `core/blueprints/`, `docs/DESIGN_*`. The flag itself is gate-protected — setting it requires acknowledging that meta-mode is on, naming the editing-window scope, and naming the auto-clear condition.

Pi-style precedent: Pi's hot-reload of extensions during their own development is the same principle — the harness must be re-editable without needing the harness's full enforcement to be up. Episteme should adopt the same pattern at the kernel layer.

**Trade-off:** Any escape hatch is exploitable; this one most so because it disables the central control. Mitigation: make the meta-mode marker file expire on its own short TTL (e.g., 60 minutes), require explicit re-acknowledgement to extend, and force an audit-log entry into the hash-chained framework on activation/deactivation so the operator can see in retrospect when the kernel was running with reduced enforcement.

#### 🟠 Major / Finding 4: Extension authoring threshold is dramatically higher than Pi's, in a market that increasingly judges harnesses on extensibility ergonomics

**Vector:** Edge Case (test against the contributor / community in 6 months).

**What:** Pi's pitch lands because adding a new check in Pi is *empirically* a 10-line TypeScript file in an extensions folder, hot-reloaded. Adding a new gate or check in episteme requires:

1. Knowing the Reasoning Surface JSON schema.
2. Knowing the Cognitive Blueprint v1.0 RC schema if your check is blueprint-shaped.
3. Knowing CC's `settings.json` hook config syntax + the `hooks.json` shape episteme uses.
4. Writing bash and/or Python that emits the right JSON to stdout for the hook protocol.
5. Knowing the hash-chain envelope format for any synthesis arm.
6. Reading `kernel/HOOKS_MAP.md`, `kernel/REASONING_SURFACE.md`, `docs/HOOKS.md`, and at least the relevant Blueprint section in `DESIGN_V1_0_SEMANTIC_GOVERNANCE.md`.

That barrier is *intentional* in some places — the kernel is a precision instrument, not a plugin marketplace. But the operator's stated audience (`kernel/CONSTITUTION.md` "Who this is for") is *people who do consequential knowledge work* — not "kernel hackers." In the audience the docs name, very few will cross that barrier.

**Impact:** Six-month risk: episteme has an active operator and ~zero external contributors writing new checks. Pi-style projects accumulate ecosystem mass. Episteme accumulates artifacts only the original author writes. Layer-distinction notwithstanding, the cognition-layer thesis cannot ride if no one is willing to author into it.

**Fix:** Build a **`episteme check new <name>`** scaffolder that generates a minimal check from a template (input JSON shape, output JSON shape, three example checks committed alongside as references). Target: a new check should be ~30 lines + 1 markdown stub describing what it checks, no kernel-corpus reading required. The kernel corpus should still be the **invariant** — the scaffolder enforces the contract; it doesn't ask the contributor to read it.

**Trade-off:** Lowering the contribution threshold raises the rate of bad-check submissions. Counter: combine with a `episteme check verify` command that runs each new check against the falsifiability conditions in `kernel/FALSIFIABILITY_CONDITIONS.md` before activation. Bad checks fail verify and never load. (This is the same architecture as the substrate-bridge `verify` command — proven pattern, port the shape.)

#### 🟠 Major / Finding 5: No empirical evidence of cognitive lift in the artifacts (already named in Finding 2 — separated here as edge-case framing)

**Vector:** Edge Case (test against time, base rate, and the ex-believer scenario).

**What:** Same gap as Finding 2 viewed through the edge-case lens: in 12 months, the operator who has lived inside episteme will have built deep tacit conviction that it produced lift. An ex-believer or new evaluator will have no shared experience and will demand the paired comparison. By that time the project will have evolved past the design choices that the early benchmark would have validated, and the benchmark becomes harder to reconstruct, not easier.

**Impact:** Same as Finding 2 plus a time-asymmetry: every month of postponed measurement compounds the cost.

**Fix:** Same as Finding 2. Reason for separating: Finding 2 is "the logical claim is unfalsifiable today"; Finding 5 is "the claim becomes architecturally harder to falsify the longer you wait." Both fixes are the same artifact; the urgency framing is different.

**Trade-off:** Same as Finding 2. Note that the operator's `uncertainty_tolerance: 4` makes living with this gap genuinely possible — it is not a CC-style weekly outage. But the *cost of staying ignorant* (the operator's own utility filter from `cognitive_profile.md`) on a benchmark is: every architectural argument from this point forward is decided by aesthetics rather than data.

### Vector C — Structural Integrity

#### 🟠 Major / Finding 6: README/marketing surface lacks a tagline that survives 5-second comparison with Pi's

**Vector:** Structural Integrity (the marketing surface IS structure for an open-source / shareable project).

**What:** Pi's tagline is concrete, ownership-framed, instantly graspable: *"There are many agent harnesses, but this one is yours."* It tells you the layer, the field, and the differentiation in twelve words.

Episteme's hero-tagline-equivalent (post-Event 113) is *"A thinking framework for the agents you already ship."* That's better than the older versions — it tells you it's not a harness, it's a thinking layer — but it does not tell you the layer-distinction (vs Pi/CC), and it does not tell you the differentiation primitive (the Reasoning Surface gate). A reader landing from the Pi video transcript with the question "is this what episteme solves?" should be able to answer in 5 seconds and currently cannot.

The Universal-Principled rule on kernel tone (`agent_feedback.md`) correctly says marketing surface ≠ governance surface. So this finding is **only** about the marketing surface — the kernel/ corpus is fine to keep technical and load-bearing.

**Impact:** The Pi vs episteme comparison is the highest-bandwidth distribution moment available right now (the operator brought this up because the Pi video is going viral in the harness community). A marketing surface that doesn't survive the 5-second compare loses the layer-distinction argument before it starts.

**Fix:** Drop a layer-explicit tagline above the current one. Candidates:

- *"Pi makes the harness yours. episteme makes how it thinks yours."* (direct comparative, names the layer above harness)
- *"The cognition layer above your harness. CC, Pi, Codex, opencode — episteme runs above all of them."*
- *"Your harness runs the model. episteme runs your reasoning."*

Pair with the enforcement-primitive matrix from Finding 1 immediately below the tagline. Together those two artifacts answer the operator's "is this what episteme solves?" question on the first scroll.

**Trade-off:** Direct comparative taglines age fast (Pi might rebrand; CC might add a cognition layer in version 2.0). Counter: pair the comparative line with the layer-explicit one ("the cognition layer above your harness") so the durable framing carries the weight and the comparative line is rotation-safe.

#### 🟡 Minor / Finding 7: Kernel corpus is large relative to what is empirically load-bearing for runtime behavior

**Vector:** Structural Integrity.

**What:** `kernel/*.md` totals 4,831 lines across 18 files. The constitution + reasoning surface + failure modes are 925 lines and are clearly load-bearing (they shape the gate and the blueprint set). `REFERENCES.md` is 846 lines and is clearly attribution. The remaining ~3,000 lines (`MEMORY_ARCHITECTURE`, `CONTINUITY_PLAN`, `CHAIN_RECOVERY_PROTOCOL`, `PHASE_12_LEXICON`, `MODEL_PROGRESS_RISK_MODEL`, `OPERATOR_PROFILE_SCHEMA`, `KERNEL_LIMITS`, `FALSIFIABILITY_CONDITIONS`, `ACTIVE_GUIDANCE_RANKING`, `DESIGN_BEHAVIOR_INVARIANTS`, `CHANGELOG`) are genuinely dense and high-signal *if you read them carefully*, but most are not on the path that changes per-turn agent behavior.

This is not padding — none of the files I sampled were filler. It is **kernel-as-research-artifact** living in the same path namespace as **kernel-as-runtime-control-surface**, with no separation. From a structural-integrity lens, that risks: (a) the load-bearing invariants getting harder to find as the corpus grows; (b) future kernel additions arriving as "another markdown in kernel/" without the discipline of asking "does this change runtime behavior, or is it research about what runtime behavior should be?"

**Impact:** Long-term maintainability cost. Not urgent.

**Fix:** Split `kernel/` into `kernel/core/` (the load-bearing runtime contract — constitution, reasoning surface, failure modes, hooks map, kernel limits, falsifiability conditions) and `kernel/research/` (the rest — the deep philosophy, the extended attribution, the schema designs, the historical changelogs). The split makes the runtime invariants visually obvious and makes future PR reviewers ask the right question on every kernel/ addition.

**Trade-off:** Renames break inbound links. Mitigation: stub redirect files at old paths during a deprecation window. The split itself is mechanical.

#### 💡 Note / Finding 8: Pi's "session as tree" maps to episteme's hash-chained framework, but at very different abstraction levels — a UX learning, not a flaw

**Vector:** Structural Integrity (UX/mental-model consistency).

**What:** Pi's `/tree` and branch/clone/share-session features are *ergonomic* tools for navigating conversation history. Episteme's hash-chained framework (`pending-contracts/`, `framework/`, episodic streams under `core/memory/`) is a *forensic* tool for tamper-evident protocol synthesis. They live at very different points on the rigor-vs-ergonomic curve.

A Pi user arriving at episteme will have a strong "session memory" mental model from Pi's `/tree`. They will expect episteme's memory to feel similar — lightweight, browsable, branchable. They will instead find a hash-chained envelope format and an Evolution Contract.

**Impact:** Friction for newcomers, not a structural flaw. The hash-chain is justified by tamper-evidence (operator's stated requirement) — that justification is correct.

**Fix:** Document the comparison explicitly. In `docs/MEMORY_CONTRACT.md` (or a new `docs/COMPARISON_TO_HARNESS_MEMORIES.md`), add a one-paragraph "Pi-style session memory vs episteme framework memory" section: `/tree` is for navigation, the hash chain is for forensic durability and synthesis. Both can coexist; episteme even has explicit support for substrates as caches under the substrate-bridge contract. The paragraph eliminates the mental-model collision.

**Trade-off:** Adds doc surface. Negligible cost.

---

## Phase 3 — Severity Summary

| Severity | Count | IDs |
| --- | --- | --- |
| 🔴 Critical | 1 | F1 |
| 🟠 Major | 5 | F2, F3, F4, F5, F6 |
| 🟡 Minor | 1 | F7 |
| 💡 Note | 1 | F8 |

---

## Phase 4 — Verdict

**By the swing-review verdict criteria:** **FAIL.**

- F1 (Critical) has a viable mitigation (separate the markdown-portability and enforcement-portability claims in the docs and add the matrix), so the Critical alone would be PASS WITH CONDITIONS.
- 5 Major findings exceed the 3+ Major threshold, which fails the rule.

**Operator-facing translation of the FAIL verdict:** episteme was not built wrong. It was built with 6 specific gaps that pi.dev's existence makes visible at exactly the moment they need to be closed:

1. (F1) Cross-tool enforcement claim is partly aspirational — separate the claims in docs.
2. (F2 + F5) Cognitive-lift claim is unfalsifiable today — start the paired benchmark privately now.
3. (F3) Kernel-edit-mode meta-cognition friction — add a TTL'd escape hatch with audit logging.
4. (F4) Extension threshold is high — add a check scaffolder + verify command.
5. (F6) Marketing tagline doesn't survive 5-second compare with Pi — add the layer-explicit comparative.
6. (F7) Kernel corpus is research+runtime mixed — split into `kernel/core/` + `kernel/research/`.

None of these require an architectural redesign. None invalidate the layer model. Each closes in bounded work (rough estimates: F1 ≈ half day; F2/F5 ≈ multi-week project but bounded; F3 ≈ half day; F4 ≈ 1–2 days; F6 ≈ tagline iteration, hours; F7 ≈ half day mechanical move).

**The non-finding worth stating loudly:** **the layer-distinction itself survived the adversarial review.** Pi's existence does not threaten episteme's slot. Pi competes one floor down. Pi's success would, if anything, give episteme a better-engineered substrate to ride on — and Pi's explicit AGENTS.md support means the cross-tool memory plumbing is already shared. The disconfirmation criterion declared in the Reasoning Surface fired in the second direction (substrate gap pi leaves) — verdict B in the surface, not verdict A.

---

## Hidden Assumptions Exposed

Operator: these are the assumptions episteme's current design depends on. Each is non-fatal, but each is one of the places the project becomes wrong if the world shifts.

1. **That "cognitive governance" is a real category, not a marketing label for structured prompts + hooks.** Status today: defensible by inhabitation (the kernel demonstrably refused this session's own bash op until the surface was refreshed) but not by measurement. F2/F5 close this gap.
2. **That the layer-distinction (cognition above harness) is intuitive without an explicit comparative diagram.** Status today: false — Pi's tagline is doing exactly the work episteme's marketing surface is not doing. F6 closes this gap.
3. **That the operator's audience will absorb the conceptual overhead of distinction-maps and Cognitive Blueprints.** Status today: assumed. The Pi audience absorbs "10 lines of TypeScript" instantly; the equivalent threshold for episteme is much higher. F4 closes this gap (or partially — a scaffolder lowers the floor; the conceptual model is still richer).
4. **That AGENTS.md inheritance gives episteme cross-tool reach automatically.** Status today: partially true. Cognition layer rides AGENTS.md fine; enforcement layer does not. F1 makes this explicit.
5. **That sufficient evidence of episteme's value emerges from inhabiting it, not from controlled measurement.** Status today: matches the operator's `uncertainty_tolerance: 4` posture, but base-rate lens is unforgiving on this class. F2/F5 close this gap.
6. **That the kernel's own friction during meta-cognitive work is acceptable cost.** Status today: empirically demonstrated as friction in this very session (3 hook fires during analysis of the hook regime). Operator decides whether the cost is worth paying. F3 offers a controlled relief valve if the answer is no.

---

## Operator decision points (each independent, each reversible)

If the operator wants to act on this analysis, here is the smallest reversible next move per finding. Operator decides which (if any) to promote into a follow-up Event with its own Reasoning Surface.

| Finding | Smallest reversible next move |
| --- | --- |
| F1 (Critical) | Add a §"Enforcement primitive matrix" section to `docs/LAYER_MODEL.md`. ~half day. |
| F2 / F5 (Major) | Create `benchmarks/cognitive-lift-baseline/README.md` with the methodology spec only. No measurement yet. ~half day. |
| F3 (Major) | Add `kernel-edit-mode` TTL marker spec to `kernel/KERNEL_LIMITS.md` only — no implementation. ~half day. |
| F4 (Major) | Sketch `episteme check new <name>` scaffolder ergonomics in a doc; defer implementation. ~half day. |
| F6 (Major) | Iterate the README hero tagline against 3 candidates above; A/B the layer-explicit framing in the web hero. Hours. |
| F7 (Minor) | Inventory `kernel/*.md` into runtime-control vs research; document the split in `kernel/README.md` before any rename. ~hour. |
| F8 (Note) | One-paragraph addition to `docs/MEMORY_CONTRACT.md`. Minutes. |

The operator's loss-averse posture argues for: **doc-only changes first** (F1, F6, F7, F8 — all reversible single-file edits); **measurement infrastructure design before measurement** (F2/F5 spec before benchmark); **escape-hatch design before escape-hatch implementation** (F3 spec before code). That sequence keeps every step reversible and surfaces the next decision before committing to the one after.

---

## What the operator was right about, and what they should not over-update on

**Right about:** the Pi material is genuinely architecturally informative. It forces the layer-distinction question into the open. It identifies the exact gaps episteme has not closed. The instinct to log this rather than react to it is correct — knee-jerk redesign in response to a viral video would itself be the failure mode `kernel/CONSTITUTION.md` § "story-fit over evidence" warns against.

**Should not over-update on:** Pi is not coming for episteme. Pi makes the harness yours; episteme makes how it thinks yours. The Pi video's argument that "Pi makes Claude Code obsolete" is a within-layer argument and applies entirely at the harness layer — Claude Code's harness vs Pi's harness. It does not apply to the cognition layer at all. If the operator sees a panic-shaped urge to scrap-and-rebuild, the noise filter in `workflow_policy.md` ("false urgency without explicit impact analysis") catches it: the impact is six bounded gaps to close, not an architectural redesign.

The episteme that closes those six gaps is the same episteme that exists today, with sharper edges where the Pi comparison made the dullness visible. That's the right disposition: use the comparison, do not be redirected by it.

---

## Provenance

- **Pi.dev landing page:** fetched 2026-05-08 via WebFetch; quotes verbatim.
- **YouTube transcript:** supplied verbatim by operator (video ID `PzqRRYHHpbw`); not independently verified against the source video.
- **Episteme docs read for the steel-man:** `kernel/CONSTITUTION.md` (282 lines), `kernel/REASONING_SURFACE.md` (276 lines), `docs/HARNESSES.md` (49 lines), `docs/SUBSTRATE_BRIDGE.md` (136 lines), `docs/LAYER_MODEL.md` (307 lines).
- **Hook + adapter footprint audited:** `hooks/` (single file: `hooks.json`), `adapters/{claude,hermes}/` (READMEs only at top level).
- **Kernel corpus measurement:** 4,831 lines across 18 files in `kernel/*.md`; `AGENTS.md` 372 lines.
- **Live empirical evidence:** the kernel hook fired 5 times during this analysis turn (3× pre-Bash staleness check, 2× post-Write workflow advisory). The kernel is operationally live, not spec-ware.

---

*End of analysis. Operator: this artifact is private. It is not committed. Promote, gitignore, archive, or delete at your discretion.*
