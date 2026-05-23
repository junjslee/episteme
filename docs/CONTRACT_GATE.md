# Contract Gate — deterministic contract-test complement to the Reasoning Surface

**Operational summary:**
- A deterministic gate that runs **declared contract tests** (OpenAPI conformance, Hurl HTTP scripts, DDL diff, state-diagram coverage) at a kernel-enforced point in the lifecycle.
- Catches a failure class the Reasoning Surface structurally cannot: **behavioral drift between spec and implementation**.
- Composes with the Reasoning Surface; does NOT replace it. Reasoning Surface gates *decisions*; Contract Gate gates *behavior*.
- Contracts live at `contracts/*` and inherit the **frozen-purpose** tier from [`../kernel/ARTIFACT_TAXONOMY.md`](../kernel/ARTIFACT_TAXONOMY.md): the agent reads them freely; mutation requires explicit operator authorization.
- Implementation status (2026-05-23): design + stub hook at `core/hooks/contract_gate.py` (NOT auto-installed). Activation is operator-gated to preserve loss-averse posture; downstream projects opt in by wiring the hook into `settings.json` after their `contracts/` directory is established.

---

## Why this exists

The Reasoning Surface counters **epistemological regressions**: question substitution, WYSIATI, anchoring, narrative fallacy, planning fallacy, overconfidence. It forces the agent to write down what it *would otherwise hallucinate about the decision* — Knowns, Unknowns, Assumptions, Disconfirmation — before it acts. Six Kahneman-named System-1 failure modes structurally blocked, one field at a time.

The Reasoning Surface does *not* counter **behavioral regressions**: the spec says response is `204 No Content`; the implementation returns `200 {"ok": true}`; both fluent-looking; downstream consumer that depended on `204` silently breaks. A passing Reasoning Surface cannot tell you whether the implementation actually conforms to the declared contract, because the conformance question lives below the layer the surface operates on. The agent could fill in every surface field with discipline and still ship a handler whose status code does not match the spec.

This is not a defect in the Reasoning Surface; it is a layer distinction. Reasoning Surfaces gate *what the agent is allowed to decide without explicit examination*. Contract tests gate *what behavior the agent is allowed to ship without the spec catching the mismatch*. Both are constraint-system enforcement; they operate on different parts of the system.

The kernel needed the second layer. This is it.

---

## What counts as a contract

A contract is any **declarative artifact whose conformance to running code can be mechanically tested**, and whose presence in `contracts/*` signals operator intent to enforce. Supported (and intended-to-be-supported) formats:

| Format | What it declares | Example tool |
|---|---|---|
| OpenAPI 3.x (`*.openapi.yaml`) | HTTP endpoint shape, request/response schemas, status codes | `schemathesis`, `openapi-validator` |
| Hurl (`*.hurl`) | HTTP request/response sequences with assertions | `hurl` CLI |
| JSON Schema (`*.schema.json`) | Data shape constraints for stored or emitted objects | `ajv`, native validation |
| DDL baseline (`*.sql`, `*.dbdiff`) | Database schema; migration must not change baseline without explicit migration artifact | `apgdiff`, `migra` |
| State-machine spec (`*.dot`, `*.graphml`) | Allowed state transitions; runtime traces must not exhibit forbidden transitions | custom test harness |
| Property test (`*.prop.py`, `*.prop.ts`) | Invariants expressed as property-based tests; Hypothesis / fast-check | `hypothesis`, `fast-check` |

The kernel does **not** dictate format. A project might have only OpenAPI specs, or only Hurl scripts, or a heterogeneous mix. The gate's job is to:

1. Detect what's in `contracts/`.
2. Resolve each artifact's verifier (by extension or by adjacent `.verifier` file).
3. Run all verifiers; collect pass/fail.
4. Fail the gate if any verifier reports non-zero exit OR any explicit conformance assertion fails.

Spec proliferation is the project's choice. The gate's policy is: *whatever you declared, you ship conformance for.*

---

## Where the gate fires

The gate is a `Stop` hook — same lifecycle event as the existing [`core/hooks/quality_gate.py`](../core/hooks/quality_gate.py). It runs after the agent has indicated work is complete, **before the turn-end checkpoint is allowed to land**.

The gate is **opt-in via dual signal**:

1. A `contracts/` directory exists at repo root with at least one supported spec file.
2. The hook is registered in the project's `settings.json` (or equivalent settings file).

Both conditions must hold. The dual signal is deliberate: condition (1) alone would silently activate on any downstream project that adopts a `contracts/` directory for unrelated reasons (e.g., commercial contracts, vendor agreements). Condition (2) makes activation an explicit operator decision.

Wire-up is one line:

```jsonc
// settings.json — hooks section
{
  "Stop": [
    "core/hooks/contract_gate.py"
  ]
}
```

Once wired, every turn-end fires the gate. If `contracts/*` produces any failure, the gate exits non-zero, the checkpoint hook does not commit the failing state, and the agent must surface the failure or fix it before completion.

This composes additively with existing Stop hooks ([`core/hooks/quality_gate.py`](../core/hooks/quality_gate.py), [`core/hooks/checkpoint.py`](../core/hooks/checkpoint.py)). Order of execution is governed by `settings.json`; recommended order is `quality_gate` → `contract_gate` → `checkpoint` (cheapest test first, then conformance, then commit).

---

## CLI surface

Operators and CI systems invoke the gate directly via:

```bash
episteme contract verify                    # run all contracts in contracts/
episteme contract verify <path>             # run a single contract artifact
episteme contract verify --format json      # machine-readable output
episteme contract verify --since <ref>      # only contracts changed since git ref
```

Exit codes follow the kernel's standard pattern (mirroring `episteme verify`):

| Exit | Meaning |
|---|---|
| 0 | All contracts passed |
| 10 | One or more contract assertions failed |
| 11 | A declared verifier was not found on PATH |
| 12 | A contract artifact's syntax did not parse |
| 30 | Internal error in the gate itself |

The CLI invocation is the path for CI integration. The hook invocation is the path for in-session enforcement. Both call the same verifier resolution logic; results are identical between the two paths.

---

## Composition with the Reasoning Surface

The two layers compose, with three named interactions:

1. **Contract changes require a Reasoning Surface.** A contract is frozen-purpose per [`../kernel/ARTIFACT_TAXONOMY.md`](../kernel/ARTIFACT_TAXONOMY.md). Mutation is explicit. Editing `contracts/orders.openapi.yaml` to change a response shape from `204` to `200` is exactly the kind of frozen-purpose mutation that requires a Reasoning Surface (Knowns: *why is the contract changing*; Disconfirmation: *what observable would prove the new contract wrong*). The Reasoning Surface guards the *intent to change*; the gate then enforces the *new contract* against the implementation that follows.

2. **Pattern declarations declare their contract.** Per [`../kernel/PATTERN_GOVERNANCE.md`](../kernel/PATTERN_GOVERNANCE.md), a pattern declaration carries a `verification` block with `contract_ref` pointing into `contracts/*`. Implementations-of that pattern inherit the contract by reference. The gate enforces conformance even when the implementation skipped a full Reasoning Surface (because it claimed to be mechanical) — *the gate cannot be skipped by claiming mechanicality*.

3. **The gate cannot replace the Reasoning Surface.** Even with perfect contract coverage, the questions *should this endpoint exist*, *should this state transition be allowed*, *should this schema field be added* live above the contract layer. Adding a `204` response for `POST /orders` to the spec passes the gate trivially; whether the project should be accepting orders this way is the question the Reasoning Surface gates. Substitution is a category error.

---

## What the gate does not do

The gate is deliberately narrow. It does not:

- **Generate contracts.** Generation is the agent's existing competence; the gate is the consumer, not the producer.
- **Inferring intent from passing tests.** A contract that does not exist is not a contract that passes — it is uncovered surface. The gate does not synthesize coverage from observed behavior; that is the inversion of declarative intent that the gate exists to prevent.
- **Replace the existing quality_gate.** Unit / integration / type tests answer different questions (does the code do what we wrote, in isolation). Contract tests answer the cross-system question (does the running system match the declared interface). Both ship; both fire.
- **Police format.** A project may ship OpenAPI without Hurl, or vice versa, or both, or neither. The gate runs what is declared; the kernel is not opinionated about which formats are "right."
- **Verify cross-contract consistency at this version.** If `orders.openapi.yaml` and `orders.hurl` disagree about the response shape, the gate fails on the Hurl assertion (because Hurl tests the running system) but does not flag the OpenAPI/Hurl divergence itself. Cross-contract consistency is its own future Event.

---

## Attribution

The architecture lands in response to external feedback received during Event 130 (2026-05-23) framing deterministic contract testing as substitute for Reasoning Surfaces. The substitution framing is incorrect (the two layers cover non-overlapping failure classes — behavioral drift and epistemological drift), but the underlying observation — that the kernel had no deterministic-contract enforcement complement — was correct. This document and the associated stub at [`../core/hooks/contract_gate.py`](../core/hooks/contract_gate.py) close the gap.

The behavioral-drift failure class is what Bertrand Meyer's *Design by Contract* (1986) was designed to counter: preconditions, postconditions, and invariants made explicit and checked at execution boundaries. The Contract Gate is DbC applied at the system-integration layer rather than the function-call layer — the same architectural move, scaled up to interfaces between services.

The complement-not-substitute framing follows Munger's latticework discipline: a single lens (contract tests) has a structural blind spot (cannot see decision-quality failures); a different lens (Reasoning Surface) has a non-overlapping blind spot (cannot see behavioral conformance failures); convergence across both is what closes the failure space. Either lens alone leaks. See [`../kernel/CONSTITUTION.md`](../kernel/CONSTITUTION.md) and `core/memory/global/cognitive_profile.md` § *Latticework of Mental Models* for the principled basis.
