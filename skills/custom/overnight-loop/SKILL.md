---
name: overnight-loop
description: Design and run unattended or long-horizon loops (overnight hardening, drain queues, iterative sweeps) with a written invariant the harness re-reads every iteration — no manual re-pasting, trustworthy metrics, explicit stop conditions, and correct model routing. Replaces bounded-loop-runner. Use for "overnight", "unattended", "keep iterating until", "밤새 돌려", "루프 돌려", ralph-loop or /loop driven work.
---

**Counters:** unattended-loop drift and the operator manually re-pasting the
per-iteration instruction block each cycle. **Replaces:** `bounded-loop-runner`
(absorbed — it named the limits but no trigger or carrier). **Governs:** any
loop driver — `/loop` (dynamic or cron), `ralph-loop`, `Workflow` scripts.

## The invariant file (write once, carried every iteration)

Before the first iteration, write `LOOP_INVARIANT.md` in the session scratchpad
(or the project's declared planning area) containing:

- **Goal + success metric** — what "done" measures, not what effort looks like.
- **Per-iteration contract** — the exact steps every iteration repeats
  (e.g. pick next item → fix → test → record). This is the block that was being
  re-pasted by hand; now the loop re-reads it at the top of every iteration.
- **Stop conditions (all three):** iteration cap · budget/time cap ·
  **no-progress rule** (N consecutive iterations without a metric change —
  but escalate through the ladder below before halting).
- **Allowed tools / forbidden actions** for unattended operation. No unattended
  code-writing-to-MERGE loops without explicit operator approval — unattended
  work lands on a branch, merge is a human-gated step.
- **Per-iteration verification** — the command that proves the iteration
  helped (test run, metric read). An iteration that verifies nothing is noise.
- **Handoff artifact** — where each iteration appends its one-line result.

## Pre-flight (before iteration 1 — do not enter the loop without it)

- **Dry-run the metric command** on the untouched state: it must exit clean and
  yield a parseable number. **Record that number as the iteration-0 baseline.**
  A loop entered with a broken extractor logs silent zeros for hours.
- Assert a clean working tree on a dedicated branch; note any auto-commit hooks.

## Defending the metric (unattended numbers must be trustworthy)

- **Noise floor, symmetric:** for volatile metrics, set `min_delta` and/or
  median-of-N runs in the invariant. A single reading below the floor neither
  promotes NOR reverts — confirm with a second run before either. False-keeps
  and false-rollbacks are the same disease.
- **Guard vs verify, two channels:** the progress metric says "did it improve";
  a separate guard (regression suite, invariant check) says "did anything else
  break". A kept iteration needs both. **Success-criterion and guard files are
  read-only to the loop** — the change adapts to the tests, never the tests to
  the change.
- **Composite metrics get caps and penalties:** cap cheap-to-inflate components
  and add negative terms for degenerate strategies, so the gaming path is
  score-negative by construction.
- **Simplicity override:** a near-zero metric gain does not buy added
  complexity (discard); a simplification at flat metric is a keep.

## When stuck (between "no progress" and "stop")

On N consecutive discards, escalate through a ladder before halting: re-read
the invariant and goal → combine previously-kept changes → try the opposite of
what has been failing → only then stop. The hard stop stays armed — the ladder
bounds a stall, it does not license a doomed run. For enumeration-shaped sweeps
(drains, audits), track a coverage grid and let uncovered cells pull the next
iteration instead of deepening a covered one.

## Model routing

Design, judging, and integration run on the session model. **Execution fan-out
runs on Opus**: set `model: 'opus'` on every `Agent`/workflow `agent()` launch —
never fan out parallel subagents on the design-tier model (two session-limit
outages were the cost of learning this).

## Morning close

End the loop with the `progress-handoff` skill: REPLACE-form status, what the
metric did vs the iteration-0 baseline, which stop condition fired, and the
exact next action. Leave the invariant file in place — it is the audit record
of what the loop was told.

## Provenance

Metrology hardening (pre-flight dry-run/baseline, symmetric noise floor,
guard/verify split with read-only criterion files, anti-gaming composites,
simplicity override, stuck-ladder) adapted from the retired `autoresearch`
plugin (1.7.5) — see `skills/vendor/SOURCES.md`.
