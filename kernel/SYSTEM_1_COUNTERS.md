# System 1 Counters

The [Constitution](./CONSTITUTION.md) names six System 1 failures as the
reason agents produce confident wrongness. This document maps each
failure to the specific kernel artifact that counters it, so the
protocol is auditable: every element of cognitive-os exists against a
named failure mode.

If you are considering removing or bypassing one of these artifacts,
you are removing a named counter. State which failure you are now
unprotected against.

---

## The six failures and their counters

### 1. WYSIATI — What You See Is All There Is

**The failure.** Reasoning from what is present in context, with no
accounting for what is absent. The model feels complete even when it is
missing critical information.

**Why agents are especially vulnerable.** A fluent model does not
experience the absence of information. It produces a coherent answer
from whatever context it has, and that coherence is indistinguishable
from sufficiency.

**Counter.** The **Unknowns** field of the
[Reasoning Surface](./REASONING_SURFACE.md). A blank Unknowns section
is a refusal signal — the kernel treats it as evidence that the model
has not yet examined what it does not know.

---

### 2. Question substitution

**The failure.** When the actual question is hard, System 1 silently
replaces it with a nearby easier question and answers that instead.
The answer is fluent. It is also about the wrong problem.

**Why agents are especially vulnerable.** The substitution happens
inside the generation process and produces an answer that reads as
responsive. There is no internal flag for "this is not what was asked."

**Counter.** The **Core Question** requirement in the Decompose stage.
Every work cycle must name what it is actually trying to answer, in
one sentence, before options are generated. A plan without a Core
Question is not a plan — it is a search for a nearby question to
answer instead.

---

### 3. Anchoring

**The failure.** The first framing encountered dominates. Later evidence
adjusts from that anchor, but almost never enough. Initial problem
framings become sticky even when wrong.

**Why agents are especially vulnerable.** The earliest tokens in a
context window disproportionately shape everything that follows. The
first framing the agent receives becomes the frame it reasons from,
even if later context contradicts it.

**Counter.** The **Disconfirmation** field of the
[Reasoning Surface](./REASONING_SURFACE.md). Before committing to a
frame, the agent must name what evidence would prove it wrong. This
forces active engagement with alternative framings, not passive drift
away from the anchor.

---

### 4. Narrative fallacy

**The failure.** Sparse data gets assembled into a coherent causal
story. The story feels explanatory but is constructed, not discovered.
The gaps in the data are papered over by the shape of the narrative.

**Why agents are especially vulnerable.** Producing coherent prose is
exactly what fluent models are optimized for. The failure mode *is*
the skill.

**Counter.** The **facts / inferences / preferences separation** in
the distinction map. Each claim is tagged by epistemic status.
A narrative that cannot be decomposed into these three categories is
a story, not an analysis.

---

### 5. Planning fallacy

**The failure.** Effort, time, and risk are systematically
underestimated; benefits are systematically overestimated. Confidence
in plans reliably exceeds their accuracy.

**Why agents are especially vulnerable.** Models trained on plans that
succeeded (because plans that failed were abandoned and not written
about) inherit survivorship bias in their estimates.

**Counter.** The **inversion + margin of safety** requirement for
high-impact decisions. Instead of only asking "what does success look
like?", the agent must also answer "what would definitely cause
failure?" and "what is the buffer if estimates are wrong by 30-50%?"
If the answer to either is unacceptable, the plan is not ready.

---

### 6. Overconfidence

**The failure.** Expressed confidence consistently exceeds actual
accuracy. The model does not know what it does not know, and sounds
certain about both.

**Why agents are especially vulnerable.** The same training signal
that produces fluent outputs rewards delivery-level confidence.
Uncertainty is dispreferred even when it is the correct signal.

**Counter.** Two layered counters:

- The **Assumptions** field of the [Reasoning Surface](./REASONING_SURFACE.md)
  forces conclusions to sit on their scaffolding in plain sight.
- The **believability-weighting** rule (Dalio) weights inputs by
  demonstrated track record, not by expressed confidence. Loud and
  right are not the same signal.

---

## Using this as a review checklist

When auditing a decision or a change, walk this list:

1. What did WYSIATI miss? (Did the Unknowns section catch it?)
2. What Core Question did this cycle claim to answer? Did it actually answer that one?
3. What was the anchor? What disconfirmation was named?
4. Which claims are facts, which are inferences, which are preferences?
5. What is the failure mode for this plan? What is the margin of safety?
6. Where is the expressed confidence higher than the evidence supports?

Six questions, six named failures. If any is uncovered, you know which
kernel artifact to reach for.
