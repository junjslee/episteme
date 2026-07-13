---
name: overnight-loop
description: Design and run unattended or long-horizon loops (overnight hardening, drain queues, iterative sweeps) with a written invariant the harness re-reads every iteration — no manual re-pasting, explicit stop conditions, and correct model routing. Replaces bounded-loop-runner. Use for "overnight", "unattended", "keep iterating until", "밤새 돌려", "루프 돌려", ralph-loop or /loop driven work.
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
  **no-progress rule** (N consecutive iterations without a metric change ends
  the loop — loops that only stop on caps burn the tail doing nothing).
- **Allowed tools / forbidden actions** for unattended operation. No unattended
  code-writing-to-MERGE loops without explicit operator approval — unattended
  work lands on a branch, merge is a human-gated step.
- **Per-iteration verification** — the command that proves the iteration
  helped (test run, metric read). An iteration that verifies nothing is noise.
- **Handoff artifact** — where each iteration appends its one-line result.

## Model routing

Design, judging, and integration run on the session model. **Execution fan-out
runs on Opus**: set `model: 'opus'` on every `Agent`/workflow `agent()` launch —
never fan out parallel subagents on the design-tier model (two session-limit
outages were the cost of learning this).

## Morning close

End the loop with the `progress-handoff` skill: REPLACE-form status, what the
metric did, which stop condition fired, and the exact next action. Leave the
invariant file in place — it is the audit record of what the loop was told.
