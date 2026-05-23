# contracts/ — declarative interface specifications

This directory holds **deterministic contract specifications** for the project: declarative artifacts whose conformance to running code can be mechanically tested. Specs in this directory are enforced by [`../core/hooks/contract_gate.py`](../core/hooks/contract_gate.py) when wired into `settings.json` Stop hooks. The full architecture lives in [`../docs/CONTRACT_GATE.md`](../docs/CONTRACT_GATE.md).

## Tier

Contracts are **frozen-purpose** per [`../kernel/ARTIFACT_TAXONOMY.md`](../kernel/ARTIFACT_TAXONOMY.md). The agent may read these files freely; **mutation requires explicit operator authorization** named at the time of the change. A contract's purpose is to be the stable interface that downstream consumers depend on; silent rewrites of a contract to match drifted implementation are exactly the failure class this taxonomy exists to block.

When a contract genuinely needs to change, treat the change as a frozen-purpose mutation: write a Reasoning Surface for it (Knowns: *why does the contract need to change*; Disconfirmation: *what observable would prove the new contract wrong*), update the contract, and update the implementation in the same Event so the spec and the code land synchronized.

## Supported formats

The contract gate's verifier-resolution chain (shipping in a future Event) will support:

| Extension | Format | Verifier |
|---|---|---|
| `*.openapi.yaml`, `*.openapi.json` | OpenAPI 3.x | `schemathesis` or `openapi-validator` |
| `*.hurl` | Hurl HTTP scripts | `hurl` CLI |
| `*.schema.json` | JSON Schema | `ajv` or native validators |
| `*.sql`, `*.dbdiff` | DDL baseline | `apgdiff`, `migra` |
| `*.dot`, `*.graphml` | State machines | custom harness |
| `*.prop.py`, `*.prop.ts` | Property-based tests | `hypothesis`, `fast-check` |

If a project has only one of these (e.g., only OpenAPI), only the OpenAPI verifier needs to be on PATH. The gate runs what is declared; nothing more, nothing less.

## Current contents

[`example.openapi.yaml`](./example.openapi.yaml) — minimal placeholder illustrating the format pattern. **Not a real contract** for this project; safe to delete in a downstream fork that wants to start with its own specs. Kept in-tree as the worked example referenced by the design doc.

## Wire-up

This directory ships with `core/hooks/contract_gate.py` but does NOT auto-activate. To enforce contracts at turn-end:

1. Add real spec files to `contracts/*`.
2. Ensure the relevant verifiers are on PATH.
3. Add the hook to `settings.json` Stop hooks:

   ```jsonc
   {
     "Stop": [
       "core/hooks/contract_gate.py"
     ]
   }
   ```

Until step 3 is taken, the gate is inert. Until the verifier chain ships in a follow-up Event, even a wired gate is a no-op (with a stderr confirmation message). See [`../docs/CONTRACT_GATE.md`](../docs/CONTRACT_GATE.md) § *Implementation status* for the road-map.
