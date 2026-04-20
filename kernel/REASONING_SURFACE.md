# The Reasoning Surface

**Operational summary:**
- Four required fields: **Knowns** (verifiable), **Unknowns** (sharp), **Assumptions** (with falsification conditions), **Disconfirmation** (specific observable outcome).
- Two required markers: **domain** (Clear/Complicated/Complex/Chaotic — posture changes accordingly) and **tacit_call** (true when the decision rests on calibrated expert intuition rather than articulable evidence).
- Fill always before irreversible or blast-radius actions; usually before non-trivial design choices.
- Blank Unknowns = refusal signal. Knowns-as-assumptions = most common failure. Unfalsifiable plan = story, not plan.
- **Update mechanic:** evidence updates plausibility; it does not flip booleans. An Assumption moves to Knowns only when the evidence is decisive. Otherwise it carries an updated plausibility and a sharpened falsification condition.
- State stored at `.episteme/reasoning-surface.json` for high-impact ops; enforced via `kernel/HOOKS_MAP.md`.

---

The Reasoning Surface is the operational form of Principle I
(*Explicit > Implicit*). It is the minimum viable explicitness required
before any consequential decision.

If the four fields cannot be filled in, the decision is not ready to be
made. That is not ceremony. It is the kernel refusing to let a
fluent-sounding answer pass for an examined one.

---

## The four fields

### 1. Knowns

What is observably true, right now, with current evidence.

- Must be verifiable. "The function returns `None` on empty input" is a
  known only if the function was read or tested.
- Do not include assumptions phrased as facts. This is the most common
  failure of the field.
- Separate from inferences. If the claim required a reasoning step to
  reach, it belongs in a different field.

### 2. Unknowns

What would change the decision if it were known, and is not known.

- A blank Unknowns section is a red flag. Every consequential decision has
  unknowns; an empty list means nothing has been looked at.
- Prefer sharp unknowns ("does the caller hold a lock here?") over vague
  ones ("edge cases around concurrency").
- Rank by impact on the decision, not by how interesting the question is.

### 3. Assumptions

What is being treated as true in order to proceed, while acknowledged as
unverified.

- Name the assumption itself, not the conclusion that depends on it.
- Include a falsification condition where possible: "assuming input is
  never larger than 10k rows — false if a 50k row job shows up."
- An assumption is a debt. Pay it down (verify, or move to Knowns) as
  cheaply as possible.

### 4. Disconfirmation

What evidence, if observed, would prove the current plan wrong.

- Must be a specific, observable outcome. "If the tests pass" is not
  disconfirmation unless the tests actually exercise the thing that could
  be wrong.
- The purpose is to prevent story-fit over evidence: a plan that cannot be
  falsified is a story, not a plan.
- If no disconfirmation can be named, the decision has not been understood
  yet. Stay there until it sharpens.

---

## When to fill it in

- **Always** before an irreversible action.
- **Always** before an action with blast radius beyond the local change:
  shared systems, data loss risk, external side effects.
- **Usually** before a non-trivial design choice the decision will be hard
  to revisit.
- **Optionally** for small reversible local work — but the habit of
  surfacing unknowns even for small tasks catches many errors cheaply.

---

## Role in the loop

The Reasoning Surface is the input to the Decide step of the feedback
loop. It is also the artifact updated by the Verify step: once the action
is taken, observations move assumptions into Knowns, sharpen Unknowns, or
trigger Disconfirmation.

A decision made without a Reasoning Surface is a closed loop with no
entry point for new information. A decision made with one is an open loop
that can be corrected.

---

## The update mechanic

Evidence arriving after an action is not a boolean verdict on the
Surface. It is a weight. The discipline is to update in proportion to
the evidence, not to overwrite.

- **Assumptions** carry a plausibility — weak, moderate, strong — that
  is updated as evidence arrives. Strong evidence against a strong
  assumption is a major update; strong evidence against a weak
  assumption is a minor one. An Assumption moves to Knowns only when
  the evidence is decisive and the falsification condition has been
  genuinely exercised, not merely not-yet-fired.
- **Unknowns** do not get answered; they get *sharpened*. A vague
  unknown ("how do callers use this?") becomes a specific one ("does
  any caller depend on the return-type being exactly `str` vs
  `Optional[str]`?") as the investigation proceeds. Sharpening is
  progress even when no answer is yet in hand.
- **Disconfirmation** can be *partially* fired. Evidence that partly
  matches the disconfirmation condition is not "the plan was wrong" —
  it is a signal that the plan's shape is off by some amount that
  should be named. The correct response is to tighten the plan, not to
  discard it, unless the mismatch is near-total.

This is the discipline that separates a reasoning protocol from a
one-shot checklist: the Surface is alive across cycles, accumulating
calibrated belief, not reset to blank between decisions.

---

## The domain marker

Before the four fields, declare the **domain** this decision sits in.
The posture required changes with the domain, and a Surface filled as
if the domain were Complicated when it is actually Complex produces
fabricated confidence, not useful analysis.

- **Clear.** Cause and effect are known. Best-practice applies. A
  minimum Surface is acceptable; the unknowns are genuinely narrow.
- **Complicated.** Cause and effect are discoverable with expert
  analysis. Full Surface applies as stated.
- **Complex.** Cause and effect are visible only in retrospect. The
  Unknowns section must acknowledge the domain explicitly, and the
  execution plan must be scoped to the smallest reversible probe.
  A Knowns section that claims confident causal understanding on a
  Complex problem is a fabrication failure, not a reasoning success.
- **Chaotic.** No discernible cause-effect in the moment. Act first to
  stabilize, then fill the Surface retrospectively once there is
  something to reason about.

The domain marker precedes the Surface. Misclassifying the domain
defeats the Surface's protections regardless of how carefully the four
fields are filled.

---

## The tacit-call marker

Some decisions are made well by calibrated intuition — craft judgment,
aesthetic taste, clinical instinct, negotiation read — and poorly by
forced articulation. Forcing a full Surface over a tacit-dominated
decision produces a Knowns section that either omits the actual driver
or fabricates a legible basis in its place, and the fabricated basis is
indistinguishable from the real one at the point of writing.

The counter is the **tacit_call** marker: a boolean on the Surface
that, when true, explicitly labels the decision as judgment-driven
rather than evidence-driven. Under tacit_call:

- The Knowns section may be small or empty — the absence is explicit,
  not a failure to fill in.
- The Assumptions section carries the operator's stake: "acting on
  pattern-match from N years of similar calls."
- The Disconfirmation field still applies: even tacit calls name
  observable outcomes that would prove them wrong. The tacit-call
  marker relaxes Knowns; it does not relax accountability.

Tacit calls are recorded in the episodic tier with the marker attached.
Over time, tacit patterns whose outcomes validate can be lifted into
explicit Knowns; tacit patterns whose outcomes don't validate are the
beginning of a recalibration.

---

## Failure modes to watch for

- **Knowns filled with assumptions.** The single most common failure.
  Unverified claims are not knowns.
- **Empty Unknowns.** Treat as a claim of omniscience. Be suspicious.
- **Assumptions without falsification conditions.** Dead weight — nothing
  is named that would pay down the debt.
- **Disconfirmation that cannot happen.** "If the approach is wrong" is
  not disconfirmation. Name the observable outcome.
- **The surface as ceremony.** If filling it out did not change what was
  about to happen, the surface was not engaged with.

---

## Attribution

- **Disconfirmation** is Popper's falsification criterion operationalized
  for a per-decision artifact. A plan that cannot be falsified is a story.
- **Knowns / Unknowns / Assumptions** separation counters Kahneman's WYSIATI
  (what-you-see-is-all-there-is) and the narrative fallacy.
- **Assumptions with falsification conditions** follow Dalio's radical
  transparency: the debt is named, not hidden under confident phrasing.
- **Update mechanic (evidence-weighted plausibility).** Follows the
  Laplace/Jaynes discipline of updating belief in proportion to
  evidence, without requiring formal probabilistic machinery. The
  active-open-mindedness posture also draws on Tetlock's calibration
  work.
- **Domain marker.** Cynefin framework (Snowden), applied before the
  Surface rather than inside it.
- **Tacit-call marker.** Polanyi on tacit knowledge (some skill
  resists explicit capture) and Klein's recognition-primed decision
  (expert pattern-match as legitimate, not a System-1 defect).

Full citations: [REFERENCES.md](./REFERENCES.md).
