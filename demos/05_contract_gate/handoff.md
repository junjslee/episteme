# Handoff — Contract Gate complement

What landed, what carries, what to watch.

---

## What landed (Event 130, commit chain)

| Commit | Artifact | Status |
|---|---|---|
| `02454f1` | `kernel/ARTIFACT_TAXONOMY.md` (four-tier mutation discipline) + `kernel/PATTERN_GOVERNANCE.md` (novel vs mechanical) + `AGENTS.md` crosslinks + `kernel/CHANGELOG.md` minor entry | shipped |
| `56e83d8` | `docs/CONTRACT_GATE.md` design + `core/hooks/contract_gate.py` stub (inert; dual-signal opt-in) + `contracts/README.md` + `contracts/example.openapi.yaml` + `docs/HOOKS.md` row | shipped |
| `711d273` | `README.md` "Why isn't this just contract testing?" FAQ section after "How episteme compares" — explicit substitution-vs-complement framing | shipped |
| `d22896c` (Event 131) | `kernel/FAILURE_MODES.md` § Mode 12 — silent mutation of frozen-purpose state; closes the 1:1 mode↔counter mapping gap Event 130 opened | shipped |

Tests preserved: `pytest -q` → 1066 passed (Event 130 baseline through
Event 131 capstone unchanged). The composition introduced zero
regressions because the gate stub is inert.

---

## Residual unknowns — what carries

1. **Verifier-resolution chain order.** OpenAPI first, then Hurl, then
   the rest — declared in the design doc but unimplemented. Needs its
   own Reasoning Surface + a separate Event before code lands. Operator-
   gated.
2. **Contract Gate activation in real repos.** Stub is inert; the first
   activation will surface friction and edge cases that this design
   cannot pre-imagine. Soak data is the only honest input.
3. **Auto-discovery of contracts/ across the existing episteme repo.**
   Mechanical scanners are downstream of the taxonomy. Deferred — the
   taxonomy + design land first.

---

## What to watch

- **Mode 12 firings.** Any commit that edits a frozen-purpose artifact
  without the operator pausing for a Reasoning Surface is the failure
  class Mode 12 names. Audits should look for this in `git log` over
  the next soak window.
- **Substitution drift in copy.** Future README / web / pitch copy may
  drift back toward "we do contract testing" — the FAQ section is the
  anchor that explicitly distinguishes substitute from complement. If
  the FAQ disappears or softens, the substitution critique re-opens.
- **Contract Gate activation requests.** When an operator does opt in,
  the verifier-resolution chain Event lands. Until then, the stub is
  protective ballast — it exists so the architecture is named, not so
  it fires.

---

## Why this demo is dogfood

The kernel claims to operationalize a way to think. This demo applies
that way of thinking **to a critique of itself** — accepting that the
critique was technically grounded, naming the failure class the
Reasoning Surface didn't gate, designing the complement so the
composition is load-bearing rather than rhetorical, and refusing to
activate the new gate by default because the loss-averse asymmetry
posture says reversible-first.

Each stage produced a real artifact (kernel doc · design doc · stub
hook · example scaffolding · README FAQ · failure-mode taxonomy entry).
A demo whose Verify stage names *which* assumptions held and *which*
carry is the shape the kernel contracts for. Reading the four files in
order reconstructs the reasoning the operator actually did when the
feedback arrived.
