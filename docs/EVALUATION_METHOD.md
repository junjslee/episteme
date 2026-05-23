# Evaluation Method — Does episteme actually make a difference?

> Status: **landed Event 135 (2026-05-23). Calibration data accumulates
> via lived behavior; first quantitative results expected after the
> Tier 1 soak window clears (N ≥ 20 ops, ≥ 7 days). Formal pre-registered
> evaluation deferred to OSF submission per
> [`OSF_PRE_REGISTRATION_DRAFT.md`](./OSF_PRE_REGISTRATION_DRAFT.md).**

Episteme is a cognitive-governance kernel. The thesis is that forcing
explicit reasoning before irreversible AI-assisted decisions reduces the
rate of confidently-wrong outcomes. The thesis is testable. This document
specifies how.

The methodology has three modes — each answers a different shape of "is
episteme making a difference?" — and is operationalized in the
`episteme evaluate` CLI.

---

## Mode 1 — Self-audit (lived behavior, no setup)

**Question answered:** Across this operator's actual work, how often did
episteme's discipline fire on high-impact decisions, and did the
decisions that passed the gate survive their own predictions?

**Inputs:**
- `~/.episteme/telemetry/YYYY-MM-DD-audit.jsonl` — primary calibration
  trail; one record per high-impact op the hook saw.
- `~/.episteme/telemetry/tier1.jsonl` — Tier 1 advisory dispatches +
  outcomes (Event 135+).

**Metrics:**

| Metric | Definition | Healthy range |
|---|---|---|
| `surface_authoring_rate` | High-impact ops where the operator/agent authored a Reasoning Surface before proceeding | ≥ 80% |
| `tier1_confirm_survival_rate` | Of Tier 1 ops the operator confirmed, fraction where no subsequent revert fired within 24h | ≥ 90% |
| `disconfirmation_fire_rate` | Surfaces whose stated disconfirmation condition was later observed (forced a re-plan) | informative — no threshold; signals the discipline is engaged with reality, not ceremony |

**Invocation:**

```bash
episteme evaluate self-audit             # human-readable
episteme evaluate self-audit --json      # machine-readable
```

**Empty-state behavior:** with no telemetry, the CLI returns a
`verdict: "empty-state"` message and exits 0. This is honest — episteme
cannot evaluate something that has not happened yet.

**Limitation:** self-audit is correlational, not causal. The data shows
*whether* the discipline fired, not *whether the discipline changed the
decision*. Modes 2 and 3 are designed to answer the causal question.

---

## Mode 2 — Challenge-set (controlled scenarios)

**Question answered:** Given a decision scenario with a known System-1
failure mode embedded in it, does the Reasoning Surface's structure
force the failure mode to the surface where it can be addressed — or
does the surface let the failure mode through?

**Inputs:** A bundled set of decision scenarios where the System-1
answer is wrong and the System-2 answer is recoverable through one of
the surface's structural gates (Knowns must be verifiable, Empty
Unknowns is a refusal signal, Disconfirmation must be observable, etc.).

The MVP shipping in Event 135 includes five scenarios covering five
of the six System-1 failure modes named in
[`kernel/CONSTITUTION.md`](../kernel/CONSTITUTION.md) Dual-Process Theory
section:

- **ch-001** — Knowns-as-assumptions (migration safety with mocked
  tests).
- **ch-002** — Empty Unknowns (rewrite with "no unknowns").
- **ch-003** — Unfalsifiable disconfirmation ("if the approach is
  wrong").
- **ch-004** — Question substitution (ship deadline vs. ship readiness).
- **ch-005** — Narrative fallacy (metric drop → first-noticed cause).

**Invocation:**

```bash
episteme evaluate challenge-set
episteme evaluate challenge-set --json
```

**Output:** for each scenario, the System-1 answer the surface is
designed to block, plus the specific surface structure that catches it.
The MVP shape is illustrative — it shows *what episteme is supposed to
catch*. Formal RCT-style measurement (multiple agents, blinded prompts,
inter-rater reliability) is deferred to the OSF pre-registration.

**Why this matters even before formal measurement:** the challenge-set
makes the kernel's claims falsifiable in the small. A skeptic can read
each scenario and check whether the structural gate the kernel cites
would actually have caught their own past mistakes. The accumulating
operator response to the challenge-set is itself informative.

---

## Mode 3 — Before-after (window comparison)

**Question answered:** Did adopting episteme change the rate at which
the operator's high-impact decisions produced subsequent reverts /
incident reports / re-plans?

**Inputs:** Telemetry windows. The operator names a `--before` window
(pre-episteme baseline or pre-Event-N baseline) and an `--after` window
(post-adoption). The CLI computes the delta on the Mode 1 metrics.

**Invocation:**

```bash
episteme evaluate before-after --before=2026-03-01 --after=2026-04-01
episteme evaluate before-after --before=-30d --after=-7d
```

**Limitation:** confounded by everything else that changed between
windows (operator skill growth, project complexity shift, etc.). The
delta is suggestive, not causal. To make Mode 3 causal would require
either (a) a within-operator A/B with random assignment per op (not
ergonomic — episteme is on or off), or (b) cross-operator A/B with
matched cohorts (Phase 2 recruitment territory; deferred).

What Mode 3 IS useful for: catching regressions in the operator's own
practice. If `surface_authoring_rate` drops over time, the discipline
is rotting into ceremony or being bypassed; the CLI surfaces the trend
before the operator notices it personally.

---

## How the three modes compose

Each mode answers a different shape of "is episteme making a
difference?":

- **Mode 1 (self-audit)** — *Is the discipline being applied?* No
  causal claim, but high signal/cost ratio. Required gate before
  Modes 2/3 produce meaningful comparisons.
- **Mode 2 (challenge-set)** — *Does the discipline's structure
  catch known failure modes?* Illustrative-MVP shape today; pre-registered
  RCT design is the next step (operator-gated OSF submission).
- **Mode 3 (before-after)** — *Did adoption correlate with outcome
  improvement?* Correlational, confounded, but practically informative
  for the single operator's own practice.

The kernel's strongest empirical claim — *episteme's calibration
curve trends toward the diagonal across windows on the same operator* —
is testable today via Mode 1 + the existing
[`kernel/CALIBRATION_TELEMETRY.md`](../kernel/CALIBRATION_TELEMETRY.md)
metrics. Falsification is observable: if the curve does NOT trend toward
the diagonal across N ≥ 100 high-impact ops, the kernel's central claim
is wrong.

---

## What "making a difference" means here

Episteme's promise is **not** that it produces better decisions on
average. The promise is more specific:

> *The discipline catches the class of decision errors that have
> high blast radius and low recovery — confidently-wrong irreversible
> moves — at the cost of some friction on every high-impact op.*

The right metric is therefore not "average decision quality went up,"
which is unmeasurable for individual operators on small samples. The
right metric is **the rate at which the worst category of error
occurred** — production-incident-class, irreversible-rollback-class,
"I should have caught that" class. Episteme catches these by making
the would-be decision visible at the moment of irreversibility, with
the structural gates Kahneman / Dalio / Boyd / Munger argue against.

The evaluation method specified above tests *that* claim, not "is the
agent smarter when episteme is on." The kernel's value is asymmetric
loss-aversion at the moment of irreversibility, and the evaluation
should measure that, not aggregate brilliance.

---

## What this method explicitly does NOT do

- **Does not establish causality on a single operator.** Single-operator
  before-after designs are inherently confounded. Pre-registered OSF
  protocol is the path to causal claims.
- **Does not compare episteme against other governance approaches.**
  That's a different study (e.g., MIRROR benchmark territory).
- **Does not measure "decision quality" as an absolute.** Decision
  quality is a moving target; the evaluation measures *survival of the
  decision's own predictions* (rationale-accuracy + disconfirmation
  fire rate), which is the falsifiable property.
- **Does not require Phase 2 recruitment.** All three modes work
  single-operator. Phase 2 multi-operator data is an additive layer,
  not a prerequisite.

---

## What's next

Lived-behavior soak window: N ≥ 20 Tier 1 ops across ≥ 7 calendar days.
At soak clearance, `episteme tier1 audit` reports OPEN, the live hook
begins dispatching Tier 1 ops through the advisory path, and `episteme
evaluate self-audit` starts producing quantitative results that
distinguish surface-fired ops from non-surface ops.

After that, the next gates are operator-action: Probe 3 (operator + 2-3
colleagues, 30-day instrumented) and OSF pre-registration submission,
both of which are documented at
[`PRODUCTIZATION_PLAN.md`](./PRODUCTIZATION_PLAN.md) § 3.4 and
[`OSF_PRE_REGISTRATION_DRAFT.md`](./OSF_PRE_REGISTRATION_DRAFT.md).

---

## Attribution

- **Three-mode design** (self-audit / challenge-set / before-after) is
  the cheapest set of cuts that cover the orthogonal questions a
  potential user actually asks: *Am I using it? Does it catch what it
  claims to catch? Did adopting it correlate with better outcomes?*
- **Falsifiability primacy** follows Popper — every metric in this
  document has a stated observable outcome that would falsify the
  episteme thesis. A kernel that promises better decisions but
  cannot be measured wrong is a story, not a kernel.
- **Single-operator MVP before multi-operator RCT** follows Tetlock's
  calibration discipline — the per-operator calibration loop is the
  load-bearing claim; multi-operator aggregation is downstream
  validation, not the core test.
