# Design-Behavior Invariants

**Operational summary** (load first if you have a token budget):

- The kernel has 600+ unit tests. Tests verify *code correctness* (the implementation does what the test asserts). They do NOT verify *specification conformance* (the implementation does what the spec claims at runtime).
- This document declares the invariants — observable behavioral properties that must hold across the kernel surfaces — so the spec-vs-runtime gap is structurally checkable, not just hopeable.
- Per-surface invariants below are the framework. Each carries a status (RUNNING / PARTIAL / SCHEDULED / ASPIRATIONAL) and an action-on-conformance-drift commitment.
- v1.1 first slice (Event 81 / CP-DESIGN-BEHAVIOR-VERIFICATION-01): **doc + per-surface invariant declarations + 2-3 example invariants per surface**. Continuous specification-conformance audit (similar shape to Phase 12 audit but applied to the kernel itself) is deferred to a follow-up Event.

---

## What this is (vs unit tests)

A unit test verifies "the code does what the test asserts." That is necessary but insufficient. If the spec claims one behavior and the code (and its tests) drift to a slightly different behavior, the unit-test suite stays green while the kernel becomes a different system than the one its docs describe.

**This document is the spec-side of the conformance contract.** The unit-test suite is the code-side. A *runtime conformance audit* (deferred — Component 2 of CP-DESIGN-BEHAVIOR-VERIFICATION-01) is the bridge between them: walks a corpus of representative ops, observes actual behavior at runtime, and reports drift between declared invariants here and observed behavior in the wild.

The kernel's central thesis is "evidence before assertion." If the EVIDENCE for an invariant is missing — i.e., we declare it but never check it at runtime — then the invariant is itself an assertion-without-evidence. This file makes the assertions explicit; future Events make the evidence explicit.

---

## Status taxonomy

Each invariant carries one of four status values, mirroring `kernel/FALSIFIABILITY_CONDITIONS.md` honesty discipline:

- **RUNNING** — invariant has both unit-test coverage AND runtime-observable evidence (audit log, hook output, episodic record). Currently held + verifiable.
- **PARTIAL** — unit-test coverage exists, but runtime-observable evidence is incomplete or scoped to a fixture rather than the wild.
- **SCHEDULED** — invariant declared; conformance audit designed but not yet running.
- **ASPIRATIONAL** — invariant declared; no infrastructure to check it at runtime yet. Honestly flagged.

Rounding ASPIRATIONAL → RUNNING is confirmation theater. The honest 4-tier enum is itself anti-Doxa discipline applied to this matrix (same pattern as `kernel/FALSIFIABILITY_CONDITIONS.md`).

---

## § A · Hook layer invariants

### A1 · PreToolUse Reasoning Surface guard refuses high-impact ops without a fresh surface

- **Invariant.** Under strict mode, a high-impact op (cascade:architectural, fence:constraint-removal, irreversible-tier ops) cannot proceed without a Reasoning Surface present at `.episteme/reasoning-surface.json` AND with timestamp within the configured TTL.
- **Property-based assertion shape.** *For every PreToolUse Bash hook fire matching the high-impact pattern: if RS is missing OR RS.timestamp older than TTL, hook exits non-zero AND the audit log records a refusal event.*
- **Status.** **RUNNING.** Verified across Events 36-50 (soak window) + Gate 28 dogfood + the current session's repeated RS-stale advisories.
- **Action on drift.** If runtime audit shows RS-missing high-impact ops proceeding without refusal, this is a hook regression. Immediate kernel patch; root-cause analysis of which validator path bypassed.

### A2 · PostToolUse hook writes episodic records on high-impact firings

- **Invariant.** *For every PostToolUse fire matching a tracked high-impact pattern: an episodic record is appended to `~/.episteme/memory/episodic/<date>.jsonl` within N seconds of the op completing.*
- **Status.** **RUNNING.** Events 36-38 fixed the silent-failure mode in `episodic_writer.py` + `fence_synthesis.py`; current state shows records writing on every matching op.
- **Action on drift.** If audit shows tracked-pattern firings without companion episodic records, the writer has regressed. Re-instrument with `_hook_log()` per Event 36's fix pattern; verify the silent-failure path is loud again.

### A3 · SessionStart banner suppresses acked profile-audit drift

- **Invariant.** *For every SessionStart hook fire: if the latest profile-audit record's `run_id` is acked in `~/.episteme/state/profile_audit_acks.jsonl` (latest entry per id is `profile_audit_ack`, not revoked), the drift banner is suppressed.*
- **Status.** **RUNNING.** Event 78 shipped the ack-store + the suppression logic. Verified end-to-end via Events 78-79 dogfood.
- **Action on drift.** If a session shows a banner for an acked id, the suppression integration has regressed. Re-verify `_is_acked_in_store()` walks the chain correctly + matches by exact run_id (Event 79 closed the prefix-mismatch UX gap).

---

## § B · Blueprint layer invariants

### B1 · Blueprint D blast_radius_map status enum is closed

- **Invariant.** *Every entry in `blast_radius_map[]` carries a `status` value drawn from the enum {`needs_update`, `not-applicable`}. Other strings reject in the validator.*
- **Status.** **RUNNING.** Validator in `core/hooks/_blueprint_d.py`; tests in `tests/test_blueprint_d.py`. The current session has hit this gate multiple times (e.g., Event 72 RS schema violation when `"deferred"` was used — caught and corrected).
- **Action on drift.** If ops bypass with non-enum statuses, the validator has regressed; tighten the enum check.

### B2 · Blueprint D sync_plan covers all blast_radius_map needs_update surfaces

- **Invariant.** *For every Blueprint D-validated op: every entry in `blast_radius_map[]` with status `needs_update` has a corresponding entry in `sync_plan[]` whose `surface` field exactly matches.*
- **Status.** **RUNNING.** Validator enforces; this session's RS schema violations (when the surface strings didn't match) were caught and corrected.
- **Action on drift.** If unmatched needs_update entries pass, validator string comparison logic regressed; tighten or add fuzz tests for surface-name normalization.

### B3 · Blueprint B fence-removal emits synthesis protocol on clean resolution

- **Invariant.** *For every Blueprint B (Fence Reconstruction) firing where the constraint-removal op exits with code 0 AND no rollback marker is recorded within the configured window: a synthesized protocol is emitted to `~/.episteme/framework/protocols.jsonl` with the canonical schema.*
- **Status.** **PARTIAL.** Verified via CP-FENCE-02 (Event 50) end-to-end test. Real-world emission in operator usage is the SCHEDULED measurement (per `kernel/FALSIFIABILITY_CONDITIONS.md` § E1).
- **Action on drift.** If clean fence resolutions don't emit protocols at the expected rate, the emit path has a silent-failure mode (Events 36-38 pattern); audit `_fence_synthesis.py` for swallowed exceptions.

---

## § C · Audit (Phase 12) invariants

### C1 · Phase 12 audit is retrospective-only (D2 invariant)

- **Invariant.** *`run_audit()` reads the episodic + reflective tiers; it does NOT mutate the operator profile, does NOT trigger writes outside the reflective audit-record stream.*
- **Status.** **RUNNING.** Module docstring + code review; tests in `tests/test_profile_audit.py` verify no profile-write side effects.
- **Action on drift.** If a future change adds a profile-write side effect inside `run_audit`, that's a D2 invariant violation; reject in code review; root-cause why the boundary was crossed.

### C2 · Phase 12 surfaces re-elicitation, not correction (D3 invariant)

- **Invariant.** *Phase 12 audit emits re-elicit prompts (operator decides) and never auto-corrects an axis value. The audit record's `verdict: "drift"` is a finding, not an action.*
- **Status.** **RUNNING.** Verified via the asymmetry_posture re-elicit pattern (Event 48 detected; Events 65-67 closed via lived-behavior; Event 68 re-elicit was operator-driven; Event 78 ack pathway is operator-driven).
- **Action on drift.** If audit ever auto-corrects, that's a D3 invariant violation AND a measure-as-target-drift failure mode (`kernel/FAILURE_MODES.md` mode 8); reject + investigate why automation crossed the human-judgment boundary.

### C3 · Audit detects drift when claimed value diverges from observed behavior

- **Invariant.** *For each axis with a measurable behavioral signal (e.g., asymmetry_posture's stop-condition rate + rollback-mention rate): the audit emits `verdict: "drift"` when claimed value diverges from observed behavior across N≥10 records below the configured floor.*
- **Status.** **RUNNING.** Verified via Event 48 — Phase 12 detected `asymmetry_posture` drift at 20% stop-condition / 7% rollback-mention against the loss-averse floor.
- **Action on drift.** If a known divergence isn't flagged, the threshold or measurement-window calibration has degraded; calibrate and re-run.

---

## § D · Profile-derivation invariants

### D1 · Every load-bearing axis has a consuming derived knob

- **Invariant.** *Every axis declared in `core/memory/global/operator_profile.md` is either (a) consumed by at least one derived knob in `core/hooks/_derived_knobs.py`, OR (b) explicitly flagged as documentation-only (orphan-by-design).*
- **Status.** **PARTIAL.** Pre-Phase-A audit found 5 of 7 orphan derived knobs; Phase A/A2 closed some; post-Event-78 audit confirmed `dominant_lens` (preferred_lens_order), `noise_signature` (noise_watch_set), `explanation_depth` (explanation_form), `asymmetry_posture` (Phase 12 audit floor) are wired. Remaining axes need re-audit.
- **Action on drift.** For each currently-orphan axis: either wire it into a derived knob + hook consumer (Phase B-class work), OR demote to documentation-only in `kernel/OPERATOR_PROFILE_SCHEMA.md` (and reflect in this file's § D1 list).

### D2 · Derived knobs read latest axis value (no stale-cache reads beyond TTL)

- **Invariant.** *Every derived-knob read of an axis value either (a) reads from disk on every invocation, OR (b) carries a documented TTL beyond which a fresh read is forced.*
- **Status.** **PARTIAL.** Hot-path knobs (preferred_lens_order, etc.) read on each invocation. Some session-cached knobs need TTL audit.
- **Action on drift.** If audit finds a knob serving a stale value past its TTL, force a fresh read; document the TTL explicitly per knob.

---

## § E · Reflexive — what would falsify this matrix itself

This file is itself a kernel claim ("the kernel has identifiable invariants per surface and we know which ones are checked at runtime"). It must meet its own thesis (per `kernel/FALSIFIABILITY_CONDITIONS.md` § G reflexive-falsifiability discipline).

- **Decorative-matrix risk.** After 6 months of kernel use, no invariant in this file has had its conformance checked at runtime — the matrix is shelfware.
- **Confirmation-theater risk.** Tested invariants all hold AND none were "unexpected" — we only declared what we already knew worked.
- **Coverage-gap risk.** A confident-wrongness episode in operator usage maps to a kernel surface that has NO declared invariant in this file.
- **Ceremonial-action risk.** A drift fires AND no kernel patch / claim demotion / CP follow-up actually happens.

**Mitigation.** Quarterly review at v1.1 cycle close (~3 months post-v1.0 GA): walk this matrix; for each invariant, has the conformance check been run? What was the result? Was the action-on-drift commitment honored when it fired?

---

## Action-on-conformance-drift policy

When a runtime conformance audit reports drift between a declared invariant and observed behavior:

1. **Investigate the drift before demoting the invariant.** Per `kernel/FALSIFIABILITY_CONDITIONS.md` action-on-disconfirmation precedent (Gate 27 reclassification): drift may be real OR a measurement-dimension mismatch. Run the investigation first.
2. **Treat invariant revisions as governance events, not silent edits.** Per Pillar 2 ethos: claim revisions land via Evolution Contract gate (propose → critique → gate → promote). Mark the row in this file with the drift event + investigation outcome + revision rationale.
3. **Demote, don't delete.** A falsified invariant becomes a demoted claim (e.g., RUNNING → PARTIAL → ASPIRATIONAL → removed-at-next-major). Delete-on-falsification is a Doxa-shape that hides prior commitments.
4. **Open a CP** when drift surfaces a fixable mechanism gap. The CP carries the work; this file carries the audit trail.

---

## Deferred follow-ups (named with dependencies)

- **Component 1 — Formal specification language for kernel behaviors.** Property-based assertion DSL or schema for declaring invariants in machine-checkable form. Substantial design work; deserves its own focused Event after this declarative doc lands.
- **Component 2 — Runtime conformance test against op-corpus.** Walk a corpus of representative ops; observe actual behavior; compare against declared invariants; report drift. Substantial; needs benchmark/fixture infrastructure.
- **Component 4 — Continuous specification-conformance audit.** Same shape as Phase 12 audit but applied to the kernel itself, not the operator. Quarterly cadence; runs on a CI schedule or operator-triggered.

All three deferred-by-design with named dependencies. Component 3 (THIS doc enumerating verifiable behavioral properties per kernel surface) is the spec input for Components 1, 2, 4.

---

## Cross-references

- [`kernel/CONSTITUTION.md`](./CONSTITUTION.md) — the four principles whose invariant-shape this file makes explicit.
- [`kernel/FAILURE_MODES.md`](./FAILURE_MODES.md) — the 11-mode taxonomy that motivates each per-surface invariant; failures-mapped-to-counters is the parent of this file's invariants-per-surface.
- [`kernel/FALSIFIABILITY_CONDITIONS.md`](./FALSIFIABILITY_CONDITIONS.md) — the load-bearing-claims falsifiability matrix; this file is the per-surface-invariants matrix that operationalizes those claims at the runtime layer. § A1 (Pillar 2 hash chain), § A3 (PreToolUse refusal), § C2 (counters fire feedforward), § D1 (profile axes are control signals) are the most direct overlap.
- [`kernel/HOOKS_MAP.md`](./HOOKS_MAP.md) — the existing hook inventory; this file's § A invariants map onto specific hook surfaces named there.
- `~/episteme-private/docs/cp-v1.1-architectural.md` § CP-DESIGN-BEHAVIOR-VERIFICATION-01 — spec source.

---

## Maintenance

This file is correct when:

- Every load-bearing kernel surface has at least one declared invariant.
- Every invariant carries an honest status (RUNNING / PARTIAL / SCHEDULED / ASPIRATIONAL).
- Every action-on-drift commitment is concrete (a specific patch / claim demotion / CP follow-up), not "we'll think about it."
- The reflexive-falsifiability section (§ E) is reviewed quarterly + on each major-version cycle close.

Version: v1.0 (Event 81, 2026-04-29). First slice covers framework + 2-3 invariants per surface. Components 1, 2, 4 (formal spec language + runtime conformance test + continuous audit) deferred to follow-up Events.
