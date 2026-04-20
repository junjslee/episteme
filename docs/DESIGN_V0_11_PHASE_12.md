# Design — v0.11 phase 12 · profile-audit loop

Status: **approved** · Drafted 2026-04-20 · Approved 2026-04-20 · Scope: one phase closing 0.11.0.

**Approval record.** Maintainer reviewed 2026-04-20 and signed off on all 6 open questions + the 4 D-countermeasures + the 4 worked axes + the `insufficient_evidence` cold-start behavior. Open-question decisions:

1. **Lexicon governance → accept proposal.** Default lexicon ships in `kernel/PHASE_12_LEXICON.md`; operator override path at `core/memory/global/phase_12_lexicon.md`; audit run records which lexicon was in use.
2. **Cadence marker → accept proposal.** Start with timestamp-inferred cadence; add a mandatory schema field only if inference proves too noisy against real data.
3. **Window default → accept proposal.** 30d cold-start default; revisit to 90d after ~6 months of accumulated tier.
4. **Acknowledgment semantics → accept proposal.** Per `(axis, run_id)`. Same drift in a later run is a new prompt. Drift cannot be permanently silenced by a single ack.
5. **Cross-axis interactions → accept proposal.** Per-axis only for v0.11. Cross-axis consistency checks deferred to a follow-on.
6. **"Done" definition → accept proposal.** Phase 12 ships when the 4 deeply-worked axes (dominant_lens, noise_signature, fence_discipline, asymmetry_posture) are implemented end-to-end. The remaining 11 ship as `insufficient_evidence` stubs pointing to this spec's sketch table. Full coverage of the 11 is 0.11.1 work.

Implementation proceeds against this approved spec. Any deviation surfaces as a spec-amendment request before code lands, not silently.

## Why this exists

v0.11 phases 9–11 made the operator profile a *control signal* (phase 9 derived_knobs), started writing the *lived record* (phase 10 episodic tier), and promoted patterns out of that record (phase 11 semantic proposals). What is missing is the loop that closes the circuit: **compare the lived record against the declared profile and surface drift where they diverge**.

Without this loop, the v2 profile's `Audit Discipline` section in `kernel/OPERATOR_PROFILE_SCHEMA.md` is documentation only. Five of the maintainer's own cognitive-style axes are currently marked `confidence: inferred` pending this audit. The five remain `inferred` not because the maintainer is uncertain — they are inferred because *the mechanism that would make it safe to promote them to `elicited` does not yet exist*. Phase 12 is that mechanism.

This spec sits between `kernel/OPERATOR_PROFILE_SCHEMA.md` (section 4b — axis definitions, section 5 — derived knobs, Audit Discipline section — the loop's contract) and the implementation. It names *what* to build and *why*; it does not prescribe every line of code. The maintainer reviews, then I implement against whatever this spec becomes after review.

## Core question

*Does the declared cognitive profile match the lived cognitive profile, measured against the episodic record, in a way that is honest about its own threat model?*

Three sub-questions this spec must answer:

1. **Operationalization.** For each of the 15 axes (6 process + 9 cognitive-style), what does the axis look like in observable episodic-tier behavior? How does a vague claim like `dominant_lens: failure-first` become a concrete, computable signature?
2. **Drift detection.** How do we compare the signature's actual distribution against the declared claim without producing a false-confidence number? What is the honest-null baseline?
3. **Measure-as-target resistance.** How does the loop avoid being gamed by a sufficiently-aware agent that learns to emit features matching the audit? (The `kernel/FAILURE_MODES.md` mode 8 threat.)

## The Goodhart threat, named up front

**The loop is measurably gameable and this spec is designed around that fact, not despite it.**

Any audit that derives a scalar from observable features becomes a target the system can optimize for — *"when a measure becomes a target, it ceases to be a good measure"* (Goodhart, via Strathern; named in `kernel/FAILURE_MODES.md` mode 8). A naive phase 12 that scored `failure-first` by counting the ratio of `failure-frame tokens / total tokens` in the Reasoning Surface's `unknowns` field would, within weeks, produce surfaces stuffed with the word "fails" and "breaks" to pass the audit — *fluent-vacuous* at a new level.

Four countermeasures, built into the design below:

- **D1 · Multi-signature convergence.** No single feature triggers a drift flag. Each axis has ≥ 2 independently-derived signatures; drift is flagged only when ≥ 2 misalign simultaneously. Optimizing for one feature leaves the other misaligned and triggers drift *anyway*.
- **D2 · Retrospective only.** Signatures are computed from already-written episodic records. The agent does not see the signature definition at decision-time; the audit runs in a separate process, later.
- **D3 · Re-elicitation, not correction.** The loop writes a *prompt for the operator* — not a profile mutation, not a score. The operator decides if the drift is real, the claim was wrong, or the axis needs re-elicitation. The profile is never auto-edited.
- **D4 · Named limit.** This spec includes a `Known gaming vectors` section. Phase 12 is not a sufficient safeguard alone; it is one layer in a defense-in-depth story that includes honest operator review, the kernel-doesn't-need-the-kernel dogfood test, and the declared `fence_discipline` axis (which itself is audited by this loop — a small amount of self-reference that is stable because the audit is run by the operator on demand, not continuously).

These four are load-bearing. Any later change to the loop that relaxes D1, D2, D3, or D4 is a governance change, not an implementation tweak.

## Architecture

```
~/.episteme/memory/episodic/*.jsonl           (phase 10 writer; append-only)
        │
        ▼
  feature extraction  ──────────── per-axis signature functions
        │                                      (this spec, §Operationalization)
        ▼
~/.episteme/memory/reflective/              ←─ phase 11 semantic proposals
  semantic_proposals.jsonl                     (treated as evidence-of-pattern
        │                                       for D-cadence / decision-mode)
        ▼
  drift detection  ───────── compare observed distribution vs claim + baseline
        │                                      (this spec, §Drift detection)
        ▼
  ~/.episteme/memory/reflective/
    profile_audit.jsonl                        (one record per audit run)
        │
        ▼
  session_context.py (SessionStart) ──────── emits re-elicitation prompts
                                              above a volume + severity gate
```

Three new artifacts:

1. `src/episteme/_profile_audit.py` — the audit library. Pure Python, no network, local-only. Exports `run_audit(episodic_dir, reflective_dir, profile_path) -> AuditResult`.
2. `src/episteme/cli.py::_profile_audit` — CLI surface `episteme profile audit [--since=30d] [--write] [--json]`. Default runs against the last 30 days of episodic records, writes a text report to stdout, optionally to `profile_audit.jsonl` under `--write`.
3. Extension to `core/hooks/session_context.py` — after reading `NEXT_STEPS.md` and the reasoning-surface state, read the latest `profile_audit.jsonl` entry; if it contains any un-acknowledged drift flag, emit a one-line re-elicitation prompt.

## Operationalization — turning vibes into signatures

This section is the spec's load-bearing part. Four axes are operationalized deeply as worked examples; the remaining eleven are sketched with the pattern they follow. Every axis has the same five fields:

- **Operational definition** — what the axis *is*, translated from the schema's enum / score into observable behavior in an episodic record.
- **Signature(s)** — ≥ 2 computable features per axis (D1 convergence). Each signature is a pure function of the episodic tier + semantic proposals.
- **Baseline** — the distribution of the signature for an operator who has *not* declared this axis. Required so "drift" is measured against a real null, not an absolute target.
- **Evidence minimum** — the minimum volume of episodic records required before this axis is auditable at all. Below this, the audit returns `insufficient_evidence` for the axis — never a false signal.
- **Drift threshold** — the gap between claimed and observed that triggers a re-elicitation flag.

---

### Axis A · `dominant_lens: failure-first` (the user-named example — worked in full)

**Schema.** `dominant_lens` is an ordered enum list. `failure-first` in position 1 means: when the operator frames a decision, they *start from what would make it fail* and reason backwards. This is distinct from pattern-recognition (start from similar cases) or first-principles (start from the axioms).

**Operational definition.** In the episodic record, failure-first behavior shows up in three places:
1. The Reasoning Surface's `unknowns` field contains failure conditions (what could break, what has failed before, what invariant could be violated) *before* or *instead of* success conditions (what needs to work, what the happy path requires).
2. The `disconfirmation` field is written as a fire condition — a specific observable outcome that would falsify the plan — rather than as a success-success absence (e.g. "if no one complains" is not failure-first).
3. When decision-trace artifacts exist (which phase 12 does *not* require — episodic tier only), the rejected options include "do nothing" / "rollback" as live alternatives with explicit fire conditions, not only "we considered X but chose Y."

**Signatures.**
- **S1 · Failure-frame ratio in unknowns.** For each episodic record, tokenize the `unknowns` list + `disconfirmation` field. Count spans matching the failure-frame lexicon `(fails, breaks, rejects, errors, regresses, blocks, denies, timeout, invalidates, violates, leaks, diverges, corrupts, exhausts, stalls, rolls back, reverts)` and the success-frame lexicon `(succeeds, works, passes, completes, validates, approves, renders, delivers)`. Ratio = failure / (failure + success). Claim `failure-first` predicts ratio > 0.6; observe across N ≥ 20 records.
- **S2 · Disconfirmation-is-fire-condition.** For each record, parse the `disconfirmation` field; classify as (a) *fire-condition* — contains an if/when-clause naming a specific observable + a consequence, e.g. "if query-log shows >60% typo-driven failures, semantic search is wrong"; (b) *absence-condition* — phrased as "if no X happens" / "nothing unexpected"; (c) *tautological* — restates the Knowns. Classification via a 20-line regex + syntactic rule set. Claim `failure-first` predicts ≥ 70% fire-conditions; absence-conditions > 30% is evidence against.

**Baseline.** Run S1 + S2 on the maintainer's current episodic tier (already non-empty per phase 10) treating the `dominant_lens` claim as unset. Call the resulting distribution the provisional baseline. Re-derive per-quarter as the tier grows.

**Evidence minimum.** N ≥ 20 episodic records with non-empty `unknowns` and non-empty `disconfirmation`. Below this, the audit returns `insufficient_evidence` for this axis.

**Drift threshold.** Flag re-elicitation if S1 observed < 0.45 (claim predicts > 0.6; 25% shortfall is the threshold) AND S2 observed < 0.55 (claim predicts > 0.70; same proportional shortfall). *Both* must fail (D1 convergence) before the flag fires. A single-signature miss is logged as a weak signal but not surfaced.

---

### Axis B · `noise_signature: primary=status-pressure, secondary=false-urgency` (the hardest — closest to a vibe)

**Schema.** `noise_signature.primary` names the dominant noise source the operator is susceptible to among `{regret, anxiety, status-pressure, social-scripts, false-urgency}`. `status-pressure` specifically means the operator's decisions drift toward what *sounds impressive* rather than what *is measurably correct*.

**Operational definition.** Three observable behaviors:
1. The Reasoning Surface's `core_question` and `knowns` show signs of audience-shaping (language chosen to impress a listener, not to sharpen the question).
2. Under time pressure (decisions tagged with `domain: chaotic` or high cadence markers), the Surface fields *collapse to fluent-minimal* — short, plausible-sounding content that passes the length threshold but doesn't sharpen anything.
3. The `op` distribution skews toward high-visibility actions (`git push`, `npm publish`, `terraform apply`) at a rate higher than the work actually requires — flashy decisions get more careful surfaces than routine ones, by status-pressure's own logic of being-seen-to-care.

**Signatures.**
- **S1 · Buzzword density in Reasoning Surface.** Tokenize `core_question` + `knowns`. Match against a buzzword lexicon (current draft: `robust, seamless, end-to-end, enterprise-grade, world-class, best-in-class, holistic, synergy, cutting-edge, battle-tested, production-ready, scalable, resilient, elegant, idiomatic`). Claim `status-pressure` predicts non-zero density in > 15% of records. Operator's own counter-screen in `operator_profile.md` ("no buzzword names leak into body docs") is a *claim against* susceptibility — audit tests whether the claim holds in praxis. High density against a claim of immunity = drift.
- **S2 · Specificity collapse under cadence.** Partition records by `cadence_marker` (a new lightweight marker on the Reasoning Surface, added as part of phase 12 — not mandatory but tracked when present: `loose` / `medium` / `tight`, or inferred from timestamp clustering). For each partition, compute the mean length of `disconfirmation` + `unknowns[0]`. Claim `status-pressure` + `false-urgency` secondary predicts the `tight` partition shows > 30% shorter content than the `loose` partition — status pressure collapses surfaces under time pressure. If `tight` is *not* shorter, the claimed susceptibility is not showing up.

**Baseline.** An operator with no declared noise_signature has no prediction about buzzword density or specificity-collapse shape. Baseline = flat distribution across cadence partitions; ≤ 5% buzzword density as the repo's own editorial default.

**Evidence minimum.** N ≥ 40 records (higher than Axis A because the signature requires cadence partitioning — need enough records in each partition to be non-trivial).

**Drift threshold.** S1 buzzword-density > 15% *and* S2 shows NO collapse (tight ≥ loose in mean length) → flag: `claimed susceptibility to status-pressure, but episodic record shows neither buzzword leakage nor specificity-collapse — re-elicit noise_signature`. Also flag if S1 > 30% regardless of S2 (decorative language density is itself evidence against the operator's claimed counter-screen).

**Note.** This axis is genuinely hard. Both signatures are weak individually. The spec is honest about this: `noise_signature` is the axis most likely to return `insufficient_evidence` for long stretches, and that is the correct behavior — better a long provisional read than a false drift flag.

---

### Axis C · `fence_discipline: 4` (concrete, countable)

**Schema.** 0–5 scale. 4 = "preserves unexplained constraints until their reason is reconstructed; accepts removal when the reason is named." 5 = refuses removal without a formal review.

**Operational definition.** When the agent proposes removing a constraint (deleting an entry from an `.episteme/*` policy file, removing a forbidden-pattern, rolling back a guard), the Reasoning Surface for that decision contains an explicit reconstruction of *why the constraint was there*. Absence = cut without understanding (Chesterton's Fence violation).

**Signatures.**
- **S1 · Constraint-removal records carry reconstruction.** Identify episodic records where the `op` label is an edit to a file matched by the constraint-file glob (`.episteme/**`, `core/hooks/**`, any file containing `CONSTITUTION.md` or `POLICY.md` in its path, or lockfiles). For each, scan the `knowns` field for a sentence matching the reconstruction pattern: "this constraint exists because X" / "this was added to counter Y" / an `evidence_refs` reference to a prior audit entry or commit. Claim `fence_discipline: 4` predicts ≥ 90% of constraint-removal records carry reconstruction. Below this = drift.
- **S2 · Constraint-removals paired with review-trace.** For the same record set, check whether `decision-trace` artifacts (if present) or the `assumptions` field names at least one "what would break if we remove this." Absence of any counterfactual assumption = removal-without-blast-radius-analysis.

**Baseline.** Operator with `fence_discipline: 0` would show < 30% reconstruction rate. `3` ~ 70%. `4` ≥ 90%. `5` = 100% *plus* a review-trace reference in every case.

**Evidence minimum.** N ≥ 5 constraint-removal records. Lower than other axes because constraint-removals are rare and each one is load-bearing.

**Drift threshold.** S1 reconstruction rate < 70% OR S2 review-trace rate < 50%, across at least 5 removals, over a rolling 90-day window. This axis is one of the few where *either* signature failing is enough — constraint removal is high-consequence and the false-negative cost of waiting for convergence is worse than the false-positive cost of one premature flag.

---

### Axis D · `asymmetry_posture: loss-averse` (irreversible-action behavior)

**Schema.** `loss-averse` / `balanced` / `gain-seeking` on the irreversible-action boundary.

**Operational definition.** On irreversible ops (the `HIGH_IMPACT_BASH` set), loss-averse behavior shows up as:
1. Reasoning Surface `disconfirmation` names a *stop condition* (when to abort) rather than only a *success criterion*.
2. Rollback path named in `assumptions` or `knowns` — operator reasons about what they'd do if the action fails before committing.
3. Margin-of-safety language: explicit buffers, "worst case," "if assumptions slip by 30%."

**Signatures.**
- **S1 · Stop-condition in disconfirmation.** For episodic records with `op` in `HIGH_IMPACT_BASH`, classify `disconfirmation` as (a) stop-condition — names a specific observable that would trigger abort / rollback; (b) success-criterion — names what should hold at completion; (c) both. Claim `loss-averse` predicts (a) or (c) ≥ 70% of the time. Pure (b) dominance > 40% = drift toward `balanced` or `gain-seeking`.
- **S2 · Rollback-path mention.** Text search across `knowns` + `assumptions` for rollback-adjacent tokens: `(rollback, revert, undo, abort, back out, restore from, recovery)`. Claim `loss-averse` predicts ≥ 50% of irreversible-op records mention at least one. Below 25% = drift.

**Baseline.** `balanced` = S1 a-or-c at ~50%, S2 at ~30%. `gain-seeking` = S1 a-or-c < 30%, S2 < 15%.

**Evidence minimum.** N ≥ 15 irreversible-op records.

**Drift threshold.** S1 a-or-c < 55% AND S2 mention < 30% → flag: `claimed loss-averse posture, but irreversible-op records show success-oriented framing without rollback paths — re-elicit asymmetry_posture`.

---

### Remaining axes — pattern sketch

The four worked examples cover: (a) a cognitive-style enum with a lexicon signature, (b) a vibes-heavy axis where both signatures are individually weak, (c) a scored axis over a rare event class, (d) an enum over a bounded op-set. The remaining eleven axes follow these four templates:

| Axis | Template | 1-line signature sketch |
|---|---|---|
| `dominant_lens` positions 2+ | A | Same S1/S2 logic with different lexicons (causal-chain → "because / therefore" chains; first-principles → axiom-anchored references; second-order → "then X which causes Y" sentences). |
| `abstraction_entry: purpose-first` | A | Ratio of records where `core_question` names a *why* before the `knowns` names a *what*. Purpose-first predicts > 65% of surfaces open with why-before-how. |
| `decision_cadence.tempo` | B | Timestamp clustering: median inter-decision gap, tight/loose inferred via k-means on one dimension. Claim `medium` predicts the observed median is within the 25th–75th percentile of the repo's work pattern. |
| `decision_cadence.commit_after: evidence` | C | Ratio of episodic records where a Verify-stage artifact (verification.md or `status: success` outcome record) precedes the next action. High = evidence-cadence; low = impulse-cadence. |
| `explanation_depth: causal-chain` | A | Density of causal connectives in `knowns` + `assumptions` (`because, therefore, so that, as a result, which causes, due to`). Predicts > 15% content by sentence. |
| `feedback_mode: direct-critique` | A | In decision-trace artifacts (optional), ratio of sentences critiquing *the idea* vs *the person*. Low-signal when decision-trace is sparse; degrades to `insufficient_evidence` gracefully. |
| `uncertainty_tolerance: 4` | C | Rate at which `unknowns` fields are left non-empty across records (vs. closed-out as Knowns prematurely). Score 4 predicts rarely-empty unknowns (< 10% of records with zero unknowns). |
| `planning_strictness: 4` | C | Ratio of records with an explicit Frame-stage artifact (Reasoning Surface AND decision-trace AND named because-chain) vs. bare-surface-only. 4 predicts ≥ 80% full-triad. |
| `risk_tolerance: 2` | D | Same shape as asymmetry_posture but measured over *all* ops, not just irreversible. |
| `testing_rigor: 4` | C | Ratio of records where the action was preceded by a test run (verification step) OR followed by a test result in the next episodic record. |
| `parallelism_preference: 2` | B | Concurrent-worktree count at decision-time (if detectable from episodic markers); session-branch count in the last 7 days. |
| `documentation_rigor: 5` | C | Rate of docs/*.md edits per high-impact decision; records where NEXT_STEPS / PROGRESS / PLAN were updated in the same session as the action. |
| `automation_level: 3` | B | Rate of hook invocations vs. manual CLI invocations in the session-context record (if available). |

Each of these gets its own full five-field entry when implementation begins. The sketch is the design-decision record, not the implementation spec — the maintainer reviews the shape here; the full entries emerge during implementation against real data.

## Drift detection algorithm

Per axis, the audit returns one of three results:

```python
class AxisAuditResult(TypedDict):
    axis_name: str                    # e.g. "dominant_lens[0]"
    claim: str                        # "failure-first"
    verdict: Literal["aligned", "drift", "insufficient_evidence"]
    evidence_count: int               # N records contributing
    signatures: dict[str, float]      # S1, S2, ... observed values
    signature_predictions: dict[str, tuple[float, float]]  # (low, high) from claim
    confidence: Literal["high", "medium", "low"]  # function of N and signature convergence
    evidence_refs: list[str]          # episodic-record correlation_ids
    reason: str                       # human-readable
    suggested_reelicitation: str | None
```

Verdict rules:
- **`insufficient_evidence`** — N below the axis's evidence_minimum. Return immediately. Never flag.
- **`aligned`** — all required signatures within their claim-predicted range. No action.
- **`drift`** — ≥ 2 signatures misaligned (D1 convergence rule), OR one signature catastrophically misaligned on a high-consequence axis (fence_discipline, asymmetry_posture). Audit writes a record; session_context.py surfaces at next SessionStart.

## Output shape — `profile_audit.jsonl`

```jsonl
{"version":"profile-audit-v1","run_id":"audit-20260420-...","run_ts":"...","episodic_window":"30d","axes":[{AxisAuditResult},...],"acknowledged":false}
```

Appended, never overwritten. `acknowledged` flips to `true` when the operator runs `episteme profile audit ack <run_id>` after re-elicitation. SessionStart surfacing only fires on unacknowledged drift.

## SessionStart surfacing

`core/hooks/session_context.py` gains one new block, emitted *after* the NEXT_STEPS section and *before* the line separator. The block is one of:

- Silent (no unacknowledged drift) — no output change.
- One line per axis in drift, up to 3: `profile-audit: drift on <axis_name> — <one-line reason>. Re-elicit or run \`episteme profile audit ack <run_id>\`.`
- If > 3 axes in drift, collapse to: `profile-audit: drift on N axes — \`episteme profile audit\` for details.`

This matches the existing `surface: STALE (...)` pattern — short, actionable, never blocking.

## Cold-start + low-volume handling

First 7 days after phase 12 ships, the maintainer's episodic tier has < 20 records on most axes. Nearly every axis returns `insufficient_evidence`. This is the correct behavior. SessionStart surfaces nothing; `episteme profile audit` reports "insufficient evidence on 14/15 axes — continue accumulating."

Five of the maintainer's own axes are currently `confidence: inferred` precisely because they have not yet been lived against a growing episodic tier. Phase 12 does not turn `inferred` into `elicited` automatically — it *enables* the conversation that would. The operator still has to decide.

## Self-audit — kernel doesn't need the kernel

Per the cognitive-adoption RC gate 28 added to `NEXT_STEPS.md`: the maintainer's own profile gets audited by phase 12 during 0.11.0 soak. The dogfood test is: *does the audit detect that ≥ 1 of the 5 `inferred` axes has enough evidence to promote, or that ≥ 1 `elicited` axis is no longer matching the record?* If neither happens over 30 days of real use, phase 12 is producing no signal on a profile the operator already suspected was under-calibrated, and the design needs revisiting.

This is a failure mode for phase 12 itself: **signature-coverage failure**. It is flagged in the implementation as a required log entry on every audit run ("N axes in insufficient_evidence, N aligned, N in drift"); if the distribution stays at `15 insufficient, 0 aligned, 0 drift` for 30 days, the audit's signatures are too-narrow and need expansion.

## Known gaming vectors (honest threat model)

A sufficiently-aware agent can still defeat phase 12:

- **Vector 1 · Signature-aware composition.** If the agent learns that `failure-first` requires failure-frame lexicon > 0.6, it pads unknowns with failure-framed filler. Countermeasure: S2 in axis A (fire-condition classification) catches the padding because the fire-condition check is syntactic, not lexical. But the agent could also learn S2's regex. Beyond S2, the only real defense is operator review — the loop surfaces drift, operator sharpens both the signature and their own definition.
- **Vector 2 · Insufficient-evidence gaming.** An agent that wants to evade the audit indefinitely could reduce episodic-record volume (decline to take high-impact actions, produce bare-minimum surfaces that fail the content threshold and don't get written). Countermeasure: phase 10 writer triggers off op-pattern, not off surface quality — records still land. The volume floor is not agent-gameable.
- **Vector 3 · Profile-mutation races.** An agent authoring the operator profile could set all axes to values that happen to match its own signatures. Countermeasure: profile edits are operator-review-only; no hook writes to `core/memory/global/operator_profile.md` without explicit operator action. Named already in kernel/CONSTITUTION.md; phase 12 does not change this.
- **Vector 4 · Signature drift ≠ cognitive drift.** The signature might capture something other than the axis claims to capture. Countermeasure: every flag is re-elicitation, never correction. Operator reads the flag and decides. Phase 12 is a conversation-opener, not a verdict.

This section is load-bearing. If implementation finds a fifth vector, it joins this list rather than getting silently countered.

## Non-goals

- Auto-mutation of the operator profile. Never. All re-elicitation goes through the operator.
- Real-time audit during a decision. The loop is retrospective (D2). An in-decision version exists only as a future-phase thought experiment.
- Scoring the operator. The output is drift signal + re-elicitation, not a number.
- Multi-operator audit. Single-operator only for v0.11.0; multi-operator coordination lives in the deferred multi-operator roadmap item.
- Replacing the five `inferred` axes with a computed value. The audit surfaces; the operator elicits.

## Open questions (for maintainer review before implementation)

1. **Lexicon governance.** Who owns the failure-frame / success-frame / buzzword lexicons? Kernel? Operator-overridable? Proposal: ship a default lexicon in `kernel/PHASE_12_LEXICON.md`, allow operator override at `core/memory/global/phase_12_lexicon.md`, audit reports which lexicon was in use.
2. **Cadence marker addition.** Axis B's S2 wants a `cadence_marker` on each Reasoning Surface. Adding it is a schema edit to `.episteme/reasoning-surface.json` and is therefore a kernel-contract decision. Alternative: infer cadence from inter-decision timestamps only, no marker. Proposal: start with inferred-only; add the marker if the inferred signal is too noisy.
3. **Window governance.** Default `--since=30d` or `--since=90d`? Longer window = more stable signal but slower drift detection. Proposal: 30d for cold-start; revisit to 90d after 6 months of accumulated tier.
4. **Acknowledgment semantics.** When an operator acks a drift flag, does the axis clock reset or does it keep accumulating? Proposal: acknowledge is per `(axis, run_id)` — the same drift flagged again in a later run is a new prompt. Prevents drift being permanently silenced.
5. **Cross-axis interactions.** `fence_discipline` high + `risk_tolerance` low is expected; `fence_discipline` low + `risk_tolerance` low is internally inconsistent. Does phase 12 surface inconsistencies across axes, or only per-axis drift? Proposal: per-axis only in v0.11; cross-axis lands in a follow-on.
6. **What counts as "implementation done."** Proposal: the Verification section below, plus all four D-countermeasures traceable in the code.

## Verification — phase 12 is "done" when

- `src/episteme/_profile_audit.py` implements `run_audit` with signatures for the 4 deeply-worked axes (A, B, C, D). The remaining 11 axes ship with `insufficient_evidence` stubs that document the planned signatures — in-code TODOs referencing this spec's sketch table. (Phase 12 does not have to implement all 15 to land; it has to establish the pattern and ship the 4 that prove the pattern. The remaining 11 are 0.11.1 / 1.0.0 RC work.)
- Unit tests cover: `insufficient_evidence` on under-volume, `aligned` on a fixture matching the claim, `drift` on a fixture missing the claim, and D1 convergence behavior (single-signature misses don't flag).
- `episteme profile audit` CLI renders a text report from the four implemented axes.
- `session_context.py` surfaces an unacknowledged drift signal at SessionStart against a fixture `profile_audit.jsonl`.
- Self-audit dogfood: running `episteme profile audit` against the maintainer's own tier (≥ 20 records) does NOT crash, produces a well-formed output, and either surfaces ≥ 1 drift flag on the 5 `inferred` axes OR reports `insufficient_evidence` honestly with a log line showing signature coverage.
- `kernel/CHANGELOG.md` gets its 0.11.0 entry (deferred from phases 9–11 until this phase lands, per the coherence-pass discipline).
- This document is updated from `draft` to `approved` with the maintainer's sign-off on §Open questions.

## What this spec does NOT cover

- Implementation-level code (function bodies, error handling, exact JSON serialization shapes beyond the typed dict above). Those emerge during the implementation phase, traceable back to this spec.
- Performance. Audit is run on-demand (CLI) and at SessionStart (one read of the latest JSONL line). No real-time pressure; no optimization target.
- UI. CLI-text + SessionStart one-liner only for v0.11.0. A viewer / dashboard is out of scope.
- Phase 13 + 14 (release packaging). Separate spec when those phases open.

---

## Review checklist for the maintainer

Before signing off, confirm:

1. The four D-countermeasures (multi-signature convergence, retrospective-only, re-elicitation-not-correction, named-limit) are sufficient against the Goodhart threat for your comfort level. If not, which additional countermeasure?
2. The four deeply-worked axes are the right ones to ship first. If not, which four?
3. The six open questions — proposal or alternative?
4. The `insufficient_evidence` dominance during cold-start is acceptable as the first-30-days behavior.
5. The signature-coverage failure is a real failure mode for phase 12 itself and is correctly named as a design risk, not hidden.
6. The 15-axis pattern sketch table converges enough on the four worked examples to be trusted as the implementation guide.

Once signed off, this document changes status to `approved` and implementation begins.
