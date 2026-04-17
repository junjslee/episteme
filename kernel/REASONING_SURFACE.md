# The Reasoning Surface

The Reasoning Surface is the operational form of Principle I
(*Explicit > Implicit*). It is the minimum viable act of explicitness
required before any consequential decision.

If you cannot fill it in, you are not ready to act. That is not a
bureaucratic hurdle — it is the kernel refusing to let a fluent-sounding
answer pass for an examined one.

---

## The four fields

### 1. Knowns

What is observably true, right now, with current evidence.

- Must be verifiable. "The function returns `None` on empty input" is a
  known only if you have read or tested the function.
- Do not include assumptions phrased as facts. That is the most common
  failure mode.
- Separate from inferences: if the claim requires a reasoning step, it
  belongs in another field.

### 2. Unknowns

What would change the decision if it were known, and is not known yet.

- A blank Unknowns section is a red flag. Every consequential decision
  has unknowns; an empty list means you have not looked.
- Prefer sharp unknowns ("does the caller hold a lock here?") over
  vague ones ("edge cases around concurrency").
- Rank by impact-on-decision, not by how interesting the question is.

### 3. Assumptions

What you are treating as true in order to proceed, while acknowledging
you have not verified it.

- Name the assumption explicitly, not the conclusion that depends on it.
- Include a falsification condition where possible: "assuming the input
  is never larger than 10k rows — false if we see a 50k row job."
- An assumption is a debt. It should be paid down (verified, or moved
  to Knowns) as cheaply as possible.

### 4. Disconfirmation

What evidence, if observed, would prove the current plan wrong.

- Must be a specific, observable outcome. "If the tests pass" is not
  disconfirmation unless the tests actually exercise the thing you
  might be wrong about.
- The purpose is to prevent the narrative fallacy: a plan that cannot
  be falsified is not a plan, it is a story.
- If you cannot state a disconfirmation condition, you have not yet
  understood what you are trying to decide.

---

## When to fill it in

- **Always** before an irreversible action.
- **Always** before an action with blast radius beyond the local change
  (shared systems, data loss risk, external side effects).
- **Usually** before a non-trivial design choice, where the choice
  will be hard to revisit later.
- **Optionally** for small reversible local work — but the habit of
  surfacing unknowns even for small tasks catches many errors cheaply.

---

## How it connects to the loop

The Reasoning Surface is the *input* to the Decide step of the OODA
loop. It is also the artifact that is updated by the Verify step: once
the action is taken, observations either move Assumptions into Knowns,
sharpen Unknowns, or trigger Disconfirmation.

A decision made without a Reasoning Surface is a closed loop with no
entry point for new information. A decision made with one is an open
loop that can be corrected.

---

## Failure modes to watch for

- **Filling in Knowns with assumptions.** The single most common
  failure. If the claim was not verified, it is not known.
- **Empty Unknowns.** Treat as a claim of omniscience. Be suspicious.
- **Assumptions without falsification conditions.** Dead weight — they
  cannot be paid down because you have not said what would pay them.
- **Disconfirmation that cannot happen.** "If the approach is wrong"
  is not disconfirmation. Name the observable outcome.
- **Using the surface as ceremony.** If filling it out did not change
  what you were about to do, you probably did not engage with it.
