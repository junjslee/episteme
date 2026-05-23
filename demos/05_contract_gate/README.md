# Demo 05 — Contract Gate complement

**Premise.** External feedback (a public critique on the substitute-vs-
complement question) framed deterministic contract testing — OpenAPI /
Hurl / JSON Schema / DDL / state-machines / property-based tests — as
the *real* gate, with episteme's Reasoning Surface positioned as
redundant ceremony.

The critique is technically grounded. Contract testing catches a class
of failures (behavioral drift — code-vs-spec divergence) the Reasoning
Surface does not gate. Treating the feedback as noise would have been
dishonest.

This demo applies episteme **to a critique of episteme itself**: run the
kernel's own workflow loop on the question *"is contract testing a
substitute for, or complement to, the Reasoning Surface?"* — and ship
the resulting artifacts as the demo output.

The four-file pattern is the canonical demo shape:
[reasoning-surface.json](./reasoning-surface.json) ·
[decision-trace.md](./decision-trace.md) ·
[verification.md](./verification.md) ·
[handoff.md](./handoff.md). Reading them in order reconstructs the
reasoning that produced Event 130's five artifacts (Artifact Taxonomy +
Pattern Governance + Contract Gate design + stub hook + contracts/
example) and Event 131's follow-up (FAILURE_MODE 12).

---

## Why this demo

Three reasons.

1. **It is real.** The audit was performed. The five artifacts it
   produced landed on master across two commit chains (`02454f1`,
   `56e83d8`, `711d273` for Event 130; `d22896c` for the Event 131
   Mode 12 follow-up). Nothing in this demo is hypothetical.
2. **It is the smallest viable rejection-of-substitution end-to-end.** A
   single Core Question, three options considered (reject feedback /
   substitute / compose), the chosen option's because-chain, a
   verification against falsifiers, a handoff naming what carries.
   Everything the kernel contracts for, shown once on a substitution
   challenge.
3. **It is dogfood at maximum tension.** The kernel was being asked to
   justify its own existence against a competing architecture. The
   honest response required acknowledging the competing architecture's
   genuine load-bearing role, then naming what would be lost by
   substituting it. The Reasoning Surface forced that distinction to
   become a typed artifact instead of a rhetorical move.

---

## The workflow loop, instantiated

| Stage     | Artifact                  | What it contains                            |
|-----------|---------------------------|---------------------------------------------|
| Frame     | `reasoning-surface.json`  | Core Question, Knowns, Unknowns, Assumptions, Disconfirmation |
| Decompose | `decision-trace.md`       | Signal-vs-noise read, three options considered, because-chain to Option C |
| Execute   | (commit chain)            | The repo edits themselves — `kernel/ARTIFACT_TAXONOMY.md`, `kernel/PATTERN_GOVERNANCE.md`, `docs/CONTRACT_GATE.md`, `core/hooks/contract_gate.py`, `contracts/example.openapi.yaml`, README FAQ, FAILURE_MODE 12 |
| Verify    | `verification.md`         | Did each Knowns / Assumptions claim hold up? Were the disconfirmation conditions triggered? Core Question answered? |
| Handoff   | `handoff.md`              | What landed, residual unknowns, what to watch in soak |

---

## What this demo proves uniquely

Three things demos 01–04 do not.

- **The kernel can survive an attack on its premise.** Demos 01–04 apply
  episteme to questions where the kernel's role is uncontested. Demo 05
  applies episteme to a question where the kernel's existence is itself
  contested. The four-file artifact is the receipt that the question got
  a real answer, not a defensive deflection.
- **The output is an architectural commitment, not a code change.** The
  Execute stage produced four new kernel/docs artifacts and one stub
  hook. The decision changes how episteme composes with neighboring
  tooling forever; the demo is the audit trail for that commitment.
- **The Verify stage actually distinguishes 'held' from 'carries'.**
  Demos that report "all green" are weaker evidence than demos that name
  which assumptions held by design vs which carry into soak. Demo 05's
  verification table does the latter explicitly.

---

## How to read this demo

Start with [`reasoning-surface.json`](./reasoning-surface.json) to see
the decision as it was framed against the critique. Then
[`decision-trace.md`](./decision-trace.md) for the three options and the
because-chain to Option C (compose, not substitute). Then
[`verification.md`](./verification.md) for which assumptions held and
which carry. Then [`handoff.md`](./handoff.md) for what to watch in
soak — Mode 12 firings, copy drift, activation requests.

If you use episteme on a real critique of your own architecture, this is
the shape of artifact you should end up with. Not longer. Not shorter.
