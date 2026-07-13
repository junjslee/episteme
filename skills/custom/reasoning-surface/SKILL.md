---
name: reasoning-surface
description: Author the episteme gate artifact (.episteme/reasoning-surface.json) correctly on FIRST contact — schema, lens order, honest values, strict-vs-advisory, and when to escalate to epistemic-interrogation instead. Use the moment a PreToolUse hook reports a missing or stale Reasoning Surface, or BEFORE starting a session's first high-impact operation. Triggers on "reasoning surface", "Episteme Strict Mode", "surface stale", "blocked by episteme", "게이트 막힘", "서피스 갱신".
---

Use this skill the moment the episteme gate mentions a missing/stale Reasoning
Surface — do not retry the blocked operation first. Trial-and-error against a
fail-closed gate is the failure mode this skill removes: author once, correctly,
then proceed.

## Choose the satisfier

The gate accepts either artifact. Pick by decision weight, not convenience:

- **Reasoning Surface** (`.episteme/reasoning-surface.json`) — the default. Op-level
  gating: you are about to do bounded work and must surface knowns/unknowns/blast
  radius. Cheap, honest, 5 minutes.
- **Interrogation verdict** (`.episteme/interrogation.json`, via the
  `epistemic-interrogation` skill) — when the turn delivers a **load-bearing
  conclusion** the operator will act on: tiered claims, factored verification,
  argued opposition. If a `conclusion-shape` marker was dropped on your prompt,
  this is the one that satisfies the Stop-gate.

A long session often needs both: surface for the work, verdict for the conclusion.

## Authoring rules (violations are rejected by the gate)

1. **Real timestamp**: run `date -u +%Y-%m-%dT%H:%M:%SZ` and embed it — never guess.
   A guessed timestamp creates a stale-at-birth surface. TTL is ~30 minutes:
   **re-author per phase** (analysis → patch → handoff), updating posture and
   blast radius each time; do not stretch one surface across the session.
2. **Lens order** for Unknowns/Disconfirmation: failure-first → causal-chain →
   first-principles → second-order → base-rate.
3. **Unknowns and disconfirmation are fire-shaped**: conditional trigger word
   (if/when/should/once/after/unless) + a specific observable (number, metric
   name, failure verb, log/dashboard ref), ≥15 chars. "If issues arise" is not
   observable.
4. **No lazy values** (`none`, `n/a`, `tbd`, `없음`) — every field earns its content.
5. **`patch_vs_refactor_evaluation` names concrete modules/layers** of THIS
   change; generic phrasing is rejected.
6. **Blast radius includes what you deliberately do NOT touch**, each
   `not-applicable` with a rationale — untouched surfaces are decisions too.
7. **Every `needs_update` surface gets a matching `sync_plan` action.**

## Mode awareness

- `strict` (default, fail-closed — even in repos without `.episteme/`): the op
  blocks until a valid artifact exists.
- `advisory` (a zero-byte `.episteme/advisory-surface` marker exists): the op
  proceeds, but the gap is recorded in the audit trail — author the surface
  anyway; an audit trail of skipped surfaces is confident-wrongness in ledger form.

## Anti-theater

A schema filled without the thinking is theater, and the spot-check loop samples
for exactly that. Reason first, record second: the artifact documents work that
already happened.
