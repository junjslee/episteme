# Verification — Contract Gate complement

Did the Knowns hold up? Did the Assumptions survive? Was the Core
Question answered?

---

## Knowns — re-check

| Known | Held up? | Evidence |
|---|---|---|
| External feedback framed contract testing as substitute | **Yes** | Reddit thread preserved in `~/episteme-private/idea_analysis/`; the critique's substitution framing is reproducible |
| Reasoning Surface gates PreToolUse epistemological drift | **Yes** | `core/hooks/reasoning_surface_guard.py` runs at PreToolUse, blocks on vapor framing per `kernel/REASONING_SURFACE.md` |
| Contract testing gates behavioral drift at Stop / CI | **Yes** | arXiv:2506.18315 PBT-for-LLM-code: empirical evidence that runtime conformance checks catch drift that prompt-time review misses |
| The two gates operate at different layers | **Yes** | PreToolUse (decision admission) vs Stop / CI (behavioral conformance) — file-system-level boundaries are non-overlapping |
| arXiv:2506.18315 + 2505.23549 evidence the behavioral-drift class is real | **Yes** | Both Q3-2025 peer-reviewed; cited in `kernel/REFERENCES.md` § Convergent contemporary work |

---

## Unknowns — what got resolved, what carries

| Unknown | Resolution |
|---|---|
| Can 'frozen-purpose' contracts be enforced cleanly without manual marking? | **Resolved.** `kernel/ARTIFACT_TAXONOMY.md` declares the four tiers; tier markers are explicit in file headers. No magic; operator declares the tier per file |
| Default-on / default-off / opt-in for the gate? | **Resolved.** Dual-signal opt-in: `contracts/` directory present + explicit `settings.json` registration. Loss-averse posture preserved; activation is operator-controlled per-project |
| Does FAILURE_MODES already name 'silent mutation of frozen-purpose state'? | **Partially resolved.** Audit during Event 130 showed no existing 1:1 mode↔counter mapping for this class. Closed in Event 131 by adding **Mode 12** to `kernel/FAILURE_MODES.md` (silent mutation of frozen-purpose state — WYSIATI projected onto the artifact axis) |
| Single verifier interface or per-format runner? | **Carries.** The design declares the format set (OpenAPI · Hurl · JSON Schema · DDL · state-machines · PBT); the runner-resolution chain (OpenAPI first, then Hurl, then the rest) requires its own Reasoning Surface before code lands. The stub at `core/hooks/contract_gate.py` is deliberately inert |

---

## Assumptions — falsification check

**Complement (not substitute) is the correct framing.**
- Falsifier: zero scenarios found where both gates catch the same defect
  with the Contract Gate's catch being strictly more reliable.
- Result: **Held.** The Reasoning Surface's MIRROR-aligned epistemological
  catch (false framing producing spec-conforming output) cannot be
  replicated by any deterministic contract gate. Substitution would
  discard this class.

**Dual-signal opt-in is the right activation gate.**
- Falsifier: operator reports failure-to-activate or unintended activation
  after sustained use.
- Result: **Pending.** Stub ships inert; no activation data yet. Soak
  window measures this once a real activation lands.

**Contracts must be frozen-purpose artifacts.**
- Falsifier: gate stays useful when contracts are routinely edited to
  match implementation drift.
- Result: **Held by design.** ARTIFACT_TAXONOMY tier discipline is the
  enforcement; if a contract is mutated to fit drifted code, it has been
  silently demoted out of the frozen-purpose tier and the gate's
  guarantee fails-honest. Event 131's Mode 12 names exactly this
  failure path so it surfaces in audits.

---

## Disconfirmation conditions — none triggered

- No peer-reviewed paper found showing Reasoning-Surface-style gating
  achieving parity on behavioral drift. The closest related work
  (arXiv:2506.18315) reaches the opposite conclusion: runtime
  conformance is load-bearing.
- The Contract Gate stub is inert; no soak data yet to falsify the
  "adds friction without catching anything" condition.
- FAILURE_MODE 12 was reproduced during Event 131's audit — the failure
  class is real, not theoretical.

---

## Core Question — answered

**Complement, not substitute.** The two gates cover orthogonal failure
classes (epistemological drift vs behavioral drift) at orthogonal layers
(PreToolUse vs Stop / CI). Composition is load-bearing; substitution
would discard a class.

Three observable post-conditions:

1. `kernel/ARTIFACT_TAXONOMY.md` + `kernel/PATTERN_GOVERNANCE.md` exist
   and are referenced from `kernel/SUMMARY.md` and `AGENTS.md`.
2. `core/hooks/contract_gate.py` exists as an inert stub; activation
   requires the dual-signal opt-in.
3. `kernel/FAILURE_MODES.md` § Mode 12 names the failure class the
   Contract Gate counters (Event 131 follow-up).

All three confirmed at commits `02454f1` (taxonomy + governance),
`56e83d8` (gate stub + design + contracts/ example + README FAQ),
`d22896c` (FAILURE_MODE 12).
