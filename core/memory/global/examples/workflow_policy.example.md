# Workflow Policy

Operator-defined policy derived from top-down cognitive principles. This file is the operational counterpart to `cognitive_profile.md` — cognitive defaults enforced as workflow rules. Edit to match your own working style; the section structure is the canonical schema.

## Standard Flow

1. Frame
2. Decompose
3. Execute
4. Verify
5. Handoff

## Stage Definitions

1) **Frame**
- Define objective, success metric, and scope boundary.
- Declare one Core Question for this cycle.
- Identify uncomfortable friction (anomaly/inefficiency/uncomfortable truth) driving the work.
- Build a distinction map before planning:
  - known facts
  - unknowns
  - assumptions
  - preferences
- Declare constraint regime:
  - allowed actions
  - forbidden actions
  - cost/risk limits
- Classify decision type: reversible vs irreversible.

2) **Decompose**
- Convert non-linear context into explicit tasks via divide-and-conquer partitioning.
- Translate big `why` questions into operational `how` mappings (what can be measured or mapped now).
- For major implementation decisions, state method choice explicitly:
  - chosen method
  - viable alternatives considered
  - why this method was selected for this context
  - how it ties back to the abstract purpose (the governing intent)
- Produce smallest useful next action.
- For high-impact work, include at least 2 options and trade-offs.
- For each chosen action, include a short because-chain:
  - observed signal → inferred cause/constraint → decision.
- State a working hypothesis for the selected path (thinking as a bet).

3) **Execute**
- Run one bounded lane per task owner.
- Prefer reversible moves first.
- A named reversibility tactic: ship behavior changes behind default-OFF toggles recorded with their defaults — the legacy path stays reproducible and reversal is one switch.
- Record assumptions when data is incomplete.

4) **Verify**
- Validate against success metric, not effort spent.
- Run relevant tests/checks before completion.
- Distinguish proven facts from inferred conclusions.
- Explicitly mark residual unknowns at handoff time.
- Evaluate hypothesis result: validated, refined, or invalidated.
- Persist invalidated hypotheses into the handoff as an explicit ruled-out list (with the why) — negative results are artifacts, not exhaust; they stop dead branches being re-litigated next session.
- Encode every cross-artifact sync invariant ("these two must stay consistent") as a build-failing test; tracked exceptions get a ceiling that only moves by resolving items, never by rubber-stamping new drift.
- State how each verification was performed — manual read of real output vs script-mediated. A script you wrote to verify your own work is itself an unverified claim until spot-checked against the raw thing.

5) **Handoff**
- Update authoritative docs: REPLACE `docs/NEXT_STEPS.md`, append one line to `docs/EVENTS.md`, and update `docs/PLAN.md` when the plan changed.
- Capture unresolved risks and exact next action.

## Signal-over-Noise Rules

Before major action, answer briefly:

1. What is the signal (objective evidence)?
2. What is the noise (fear/regret/status-pressure/speculation)?
3. What action is justified by signal only?
4. What evidence would disconfirm the current plan?
5. So what is the concrete cost of remaining ignorant here?

If these cannot be answered, do not escalate execution scope.

## Risk and Autonomy Policy

- Reversible + low-impact: autonomous execution allowed.
- Irreversible, costly, or high-blast-radius: require explicit review checkpoint.
- No unattended code-writing-to-merge loops without explicit approval.

For paid hosted-model runs, estimate cost before triggering and ask:
> `acknowledge the cost and proceed? [y/n]`

## Justified-Irreversible Lane

Reversible-first over-applied is itself a failure mode: perpetual deferral silently costs time, velocity, and truth-freshness (release treadmills, zero-drain queues, deprecation-without-deletion).

An irreversible action executes through ONE decisive checkpoint when all three hold:

1. Necessity: no reversible equivalent achieves the objective — name why.
2. Preparation: recovery story stated — archive/backup where possible; otherwise explicit no-rollback acceptance with the blast radius named.
3. Single gate: one review checkpoint (operator sign-off when high-blast-radius). Once passed, execute without re-litigation; re-opening a passed gate requires NEW evidence, not renewed discomfort.

Reclassification: deletion of a version-controlled file, branch deletion with a recorded SHA, and archive-then-remove of an unversioned file (after the archive copy exists) are reversible by construction — do not route them through the irreversible gate.

Anti-treadmill rule: a decision deferred 3+ times, or open more than 30 days with no new evidence, escalates to a mandatory decide-now checkpoint — decide, or explicitly accept-and-close with the cost of ignorance named.

## Precedence & Project Memory Contract

Two authority tiers govern conflicts between this global policy and a project's own files:

- **[K] Kernel invariants** — epistemic discipline (verify-fresh, correct-never-fabricate), safety gates, authorship policy. Global. A repo file contradicting one is surfaced to the operator, never silently obeyed or ignored. Where an invariant must win against in-repo prose, enforce it with a hook — agent memory is context, not enforcement.
- **[M] Mechanics defaults** — file names, doc forms, branch flow, tooling. The project's `AGENTS.md`/repo docs are the repo operating policy and win on conflict: project > global > episodic. Scope-tag every global-surface rule at write time; untagged = [M]. Repo-scoped decisions never enter global surfaces untagged.

Authoritative truth lives in project docs and repo policy files. The default doc set — applies only where the project declares none:

- `docs/REQUIREMENTS.md` — what is being built.
- `docs/PLAN.md` — staged execution.
- `docs/EVENTS.md` — one-line-per-event history index.
- `docs/NEXT_STEPS.md` — next-session handoff (REPLACE-form).
- `docs/RUN_CONTEXT.md` — runtime assumptions, execution profiles, API env vars.

Tool-native memory (Claude / Hermes / Codex / Cursor) is acceleration only — never the source of truth.

## Automation Layer Policy

Skills, commands, and agent personas are governed artifacts, not accretion:

- **Promotion bar:** a workflow earns a skill after ~3+ observed recurrences — usage evidence, not anticipation. Every new skill names the failure mode it counters AND the mechanism it replaces or bounds.
- **Demotion bar:** zero invocations over a quarter moves a skill to archive — archive-verbatim first; version-controlled removals are reversible by construction.
- **Budget:** the managed-skill count is code (the skill manifest is the ledger); growing it is a conscious decision made in the diff.
- **Cadence:** review the layer against mined usage (invocation counts from history/transcripts, not memory) each quarter.

## Parallelism Policy

- One bounded task per worktree/lane.
- One owner per lane.
- Independent review for high-impact changes.

## Local Integration

After changing global memory files (this file, `operator_profile.md`, `cognitive_profile.md`, `agent_feedback.md`, etc.):

1. `episteme sync`
2. `episteme doctor`
