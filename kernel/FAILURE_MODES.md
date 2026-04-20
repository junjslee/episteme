# Failure Modes and Their Counters

**Operational summary — six reasoner modes ↔ counters, plus three governance-layer modes:**

| # | Failure mode                          | Counter artifact                                      |
|---|---------------------------------------|-------------------------------------------------------|
| 1 | Reasoning only from what is present   | Unknowns field (Reasoning Surface)                    |
| 2 | Answering a nearby easier question    | Core Question (required in Frame)                     |
| 3 | First-framing persistence (anchoring) | Disconfirmation field                                 |
| 4 | Story-fit over evidence               | Facts / inferences / preferences split                |
| 5 | Systematic underestimation of risk    | Failure-first + 30–50% buffer (high-impact)           |
| 6 | Confidence exceeding accuracy         | Assumptions field + weight-by-track-record            |
| 7 | Constraint removal without understanding | Fence-Check before any constraint is removed      |
| 8 | Measure-as-target drift (scorecard)   | Periodic audit vs outcome evidence; drift is allowed |
| 9 | Controller-variety mismatch (hooks)   | Escalate-by-default for out-of-coverage action shapes|

Removing or bypassing a counter means naming which mode is now unprotected. If the answer is "none," the counter was not earning its place.

---

The [Constitution](./CONSTITUTION.md) names six failure modes as the reason
agents produce confident wrongness. This document maps each one to the
specific kernel artifact that counters it.

The mapping is the audit trail: every element of episteme exists against
a named failure mode. If a proposed change removes or bypasses one of these
artifacts, name which failure mode is now unprotected against. If the answer
is "none" — the artifact was not earning its place.

**These counters are feedforward, not feedback.** They are enforced before
execution begins, not applied as corrections after a failure is observed.
Each field of the Reasoning Surface is a pre-execution gate. An agent that
fills the Surface after acting is doing retrospective documentation, not
cognitive governance.

---

## The six modes

### 1. Reasoning only from what is present

**The mode.** The agent reasons from whatever is in the context window as
if that were the whole picture. Absence of information is not felt; the
model produces a coherent answer from whatever is there, and that coherence
is indistinguishable from sufficiency.

**Why fluent models are especially vulnerable.** A fluent model does not
experience the difference between "I have enough" and "I have what was
given." There is no internal flag for the missing piece.

**The counter.** The **Unknowns** field of the
[Reasoning Surface](./REASONING_SURFACE.md). A blank Unknowns section is
a refusal signal. The kernel treats it as evidence that nothing has been
examined, not as evidence that nothing is missing.

---

### 2. Answering a nearby easier question

**The mode.** When the actual question is hard, the generation process
silently swaps in a nearby easier question and answers that one. The answer
is fluent. It also addresses the wrong problem.

**Why fluent models are especially vulnerable.** The swap happens inside
generation and produces an answer that reads as responsive. There is no
"this is not the question that was asked" flag.

**The counter.** The **Core Question** requirement in the Decompose stage.
Every work cycle must name what it is actually trying to answer, in one
sentence, before any option is generated. A plan without a Core Question
is not a plan — it is a search for a nearby question to answer.

---

### 3. First-framing persistence

**The mode.** The first framing encountered dominates. Later evidence
adjusts from that anchor but almost never enough. The initial framing
becomes the frame even after it is contradicted.

**Why fluent models are especially vulnerable.** The earliest tokens in a
context window disproportionately shape everything that follows. The first
framing an agent receives becomes the frame it reasons from, even when
later context contradicts it outright.

**The counter.** The **Disconfirmation** field of the
[Reasoning Surface](./REASONING_SURFACE.md). Before committing to a frame,
name the evidence that would prove it wrong. The act of naming forces
active engagement with alternative frames, not passive drift away from the
initial one.

---

### 4. Story-fit over evidence

**The mode.** Sparse data gets assembled into a coherent causal story. The
story feels explanatory. The gaps in the data get papered over by the
shape of the narrative, not by the evidence inside it.

**Why fluent models are especially vulnerable.** Producing coherent prose
is what fluent models are optimized for. The failure mode is the skill.

**The counter.** The **facts / inferences / preferences** separation in
the distinction map. Each claim is tagged by epistemic status. A narrative
that does not survive being decomposed into those three categories is a
story, not an analysis.

---

### 5. Systematic underestimation of effort and risk

**The mode.** Effort, time, and risk are systematically underestimated.
Benefits are systematically overestimated. Confidence in plans reliably
exceeds their accuracy.

**Why fluent models are especially vulnerable.** Training data
over-represents plans that succeeded, because plans that failed were
abandoned rather than written about. The models inherit the survivorship
bias baked into their corpus.

**The counter.** The **failure-first + buffer** requirement for
high-impact decisions. Instead of asking only "what does success look
like?", also answer: "what would definitely cause failure?" and "what is
the margin if estimates slip by 30–50%?" If the answer to either is
unacceptable, the plan is not ready.

---

### 6. Confidence exceeding accuracy

**The mode.** Expressed confidence consistently exceeds actual accuracy.
The model does not know what it does not know, and sounds equally certain
about both.

**Why fluent models are especially vulnerable.** The same training signal
that rewards fluent output also rewards delivery-level confidence.
Uncertainty is dispreferred even when uncertainty is the correct signal.

**The counter.** Two layered counters:

- The **Assumptions** field of the [Reasoning Surface](./REASONING_SURFACE.md)
  forces conclusions to sit on their scaffolding in plain sight.
- The **weight-by-track-record** rule, when inputs conflict: prefer the
  source with demonstrated accuracy on this class of problem over the
  source that is loudest, fastest, or most assertive. Loud and right are
  different signals.

---

## Governance-layer failure modes

The six modes above are Kahneman-derived — they address how a fluent
reasoner produces confidently wrong *answers*. The kernel itself is also
a system, and a system has its own failure modes. These three are not
modes of the reasoner; they are modes of the governance layer wrapped
around it. They are named separately to keep the six-mode taxonomy
intact while acknowledging the kernel's own exposure.

### 7. Constraint removal without understanding

**The mode.** An agent encounters a rule, a policy, or a piece of code
whose purpose is not immediately obvious. The cheapest narrative is that
the constraint is legacy, unnecessary, or in the way. The removal is
fluent, the justification is coherent, and the original reason — often a
paid-for lesson from a prior failure — is gone.

**Why fluent models are especially vulnerable.** Constraint-removal is
almost always a short-term local improvement: fewer rules, less
friction, cleaner code. The cost shows up later, elsewhere, under
conditions the current context window does not contain.

**The counter.** A **Fence-Check** before any constraint is removed:
name the reason the constraint was put there, from evidence available
now. If the reason cannot be reconstructed, the removal is not ready —
either route it to a human who may know, or leave the constraint and
add a ticket to investigate. "I don't see why it's there" is not a
reason to remove; it is a reason to investigate.

### 8. Measure-as-target drift

**The mode.** The kernel scores axes of the operator profile
(`testing_rigor`, `risk_tolerance`, etc.) so adapters can make
non-contextual behavioral choices. Once a score becomes visible and
actionable, it becomes something to optimize for rather than a reading
to report honestly. Over time, the scorecard describes what the
operator thinks they should be, not how they actually reason.

**Why a cognitive kernel is especially vulnerable.** The profile is
both the measurement *and* the control signal. That is the exact
configuration under which measurements stop being faithful.

**The counter.** Scorecard axes are periodically re-audited against
outcome evidence from the episodic tier (did the operator actually act
with the testing rigor their score claims?), and drift is allowed — the
kernel would rather carry a noisy but honest profile than a clean but
aspirational one. The friction analyzer's output is one signal; the
episodic tier's record of the operator's actual behavior under pressure
is another. A profile axis whose claimed value and observed behavior
diverge for N consecutive cycles is flagged for re-elicitation, not
silently kept.

### 9. Controller-variety mismatch

**The mode.** The hook layer (the rule-based governance surface around
the agent) has a fixed coverage of action shapes: a set of patterns, a
set of filenames, a set of verbs. A general-capability agent has a much
larger action space. When the action's shape falls outside the
controller's declared coverage, the controller cannot refuse — it
defaults open because it has nothing to match against.

**Why rule-based layers are especially vulnerable.** Every closed rule
set is a claim about what the agent can do. The agent's actual action
space is open. The gap between them is always nonzero, and it is where
the interesting failures live.

**The counter.** **Escalate-by-default** for action classes outside the
controller's declared coverage: route to human review rather than
silently allow. This is a weaker position than "block everything
unrecognized" (which breaks work) and a stronger position than "allow
everything unrecognized" (which is the failure mode). The controller's
coverage itself is a living document; what was out-of-coverage yesterday
may be in-coverage tomorrow once the rule is written, but never by the
rule silently expanding to fit an action it had no basis to evaluate.

---

## Using this as a pre-execution checklist

These are feedforward gates — run them before the Execute stage opens,
not after a problem surfaces. The cost of skipping is deferred, not avoided.

1. What did "reasoning only from what is present" miss? Is the Unknowns
   section non-empty and honest?
2. What Core Question does this cycle claim to answer? Is it the actual
   question, or a nearby easier substitute?
3. What is the anchor framing? What disconfirmation condition is named
   against it?
4. Which claims are facts, which are inferences, which are preferences?
   Can each survive being labeled?
5. What would definitely cause this plan to fail? What is the margin if
   estimates slip by 30–50%?
6. Where is expressed confidence higher than the evidence supports? Name it.

Six gates, six failure modes. If any gate is skipped, execution proceeds
with that failure mode unprotected. Name the trade-off explicitly rather
than leaving it implicit.

---

## Attribution

The six-mode taxonomy is Kahneman's (*Thinking, Fast and Slow*, 2011),
re-expressed in kernel language and mapped against specific artifacts rather
than left as general advice. Counter-artifacts draw on Popper
(disconfirmation), Shannon (signal vs noise), and Dalio
(weight-by-track-record). Full citations: [REFERENCES.md](./REFERENCES.md).
