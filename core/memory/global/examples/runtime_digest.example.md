# Runtime Digest

<!-- Copy this file to runtime_digest.md and customize for your setup. -->

The single always-inlined control surface for agent sessions. It carries the
hard rules and posture an agent must have in EVERY session; the deep rationale
lives in the path-referenced profiles at the bottom — Read them on demand, do
not assume their content from memory. Keep this file short: it is always-on
context, so every line costs.

## Hard rules (always apply)

<!-- Personalize: these are example defaults. Replace with the rules you never
     want an agent to violate, and delete any that do not apply to you. -->

1. **Commit hygiene** — follow your project's authorship and trailer policy on
   every commit, PR, and issue comment. State it here so it is never guessed.
2. **Branch discipline** — one bounded task per branch/worktree; one owner per
   lane; independent review for high-impact changes. Name your protected
   branches and merge flow.
3. **Back up before destructive overwrite** — files with no version history get
   archived verbatim BEFORE any overwrite.
4. **Handoff docs are bounded** — state the size/shape contract for your
   authoritative handoff docs (e.g. replace-form, size caps) so they do not
   accrete.
5. **Budgets are code** — count ceilings and size caps live in tests. Raising a
   budget constant IS the decision; make it consciously, in the diff.
6. **No orphaned guardrails** — a mechanism that enqueues work needs an
   automatic or write-path drain. A guardrail wired to no trigger is inert.
7. **Anti-accretion** — a new mechanism must name the failure mode it counters
   AND the mechanism it replaces or bounds.
8. **Name the rule-shape** before choosing it: positive system (enumerate
   allowed, default-deny) vs negative system (enumerate forbidden,
   default-allow). Unconscious choice = hidden constraint = hidden objective.
9. **Correct, never fabricate** — a stale ledger/queue entry gets verified
   against reality and corrected; closing it unverified is confident-wrongness.

## Decision posture

<!-- Personalize: describe how you want reversible vs irreversible actions
     handled, and which lenses to apply first. -->

- **Reversibility is a cost knob.** Prefer the reversible path when it achieves
  the same objective at comparable cost. When only an irreversible action
  achieves the objective, gate it once — necessity named, recovery story
  stated, single checkpoint — then execute without re-litigation.
- **Genuine irreversibles stay operator-gated** (data loss, external
  publication, high blast radius).
- **Explanations trace mechanisms**, not pattern analogies. Direct critique of
  ideas, not people.
- **Noise watch** — slow down on: solution-first without a problem statement,
  hidden assumptions, urgency without impact analysis, information-collecting
  without a core question.

## Working knobs (operator profile digest)

<!-- Personalize: a one-line digest of your operator_profile.md axis values, so
     an agent sees your working style without reading the full profile. -->

planning _N_/5 · risk _N_/5 · testing _N_/5 · docs _N_/5 · parallelism _N_/5 ·
automation _N_/5 · uncertainty tolerance _N_/5. Full data in
operator_profile.md.

## Session flow

Frame (core question, distinction map, constraint regime) → Decompose (method
choice + because-chain) → Execute (bounded lanes, lowest reversibility cost that
advances) → Verify (fresh evidence, never recalled; mark residual unknowns) →
Handoff (authoritative docs updated; exact next action named). After changing
global memory files: `episteme sync` && `episteme doctor`.

## Deep profiles (Read on demand; do not trust recall)

- `~/episteme/core/memory/global/cognitive_profile.md` — mental-model
  foundations and the full Decision Protocol
- `~/episteme/core/memory/global/workflow_policy.md` — full stage definitions,
  signal-over-noise rules, parallelism policy
- `~/episteme/core/memory/global/operator_profile.md` — all axis values with
  confidence/evidence metadata and the expertise map
- `~/episteme/core/memory/global/overview.md` — project topology
