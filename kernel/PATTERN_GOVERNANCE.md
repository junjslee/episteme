# Pattern Governance

**Operational summary:**
- The Reasoning Surface fires on **novel decisions**, not on **mechanical implementations** of an already-resolved pattern.
- A **pattern declaration** is a Reasoning Surface that has been promoted to authoritative-living state, carrying a stable `pattern_id` that downstream implementations reference.
- Subsequent implementations that follow a declared pattern produce a minimal `implementation-of` reference rather than re-deriving the surface from scratch.
- The failure mode this counters is **PTSP uniform application** — the Reasoning Surface scaling linearly with implementation count rather than with decision count, which turns the kernel into ceremony at any non-trivial codebase scale.
- Operational pairing: see [`ARTIFACT_TAXONOMY.md`](./ARTIFACT_TAXONOMY.md) (a pattern declaration is authoritative-living; an `implementation-of` reference is working-execution).

---

The Reasoning Surface is expensive on purpose. Every field forces the agent to write down what it would otherwise hallucinate. But the expense is justified only when the *decision* is being made — when a question is open, alternatives are live, and the choice could go several ways. Once the decision is closed and a pattern is established, subsequent implementations that follow that pattern do not re-open the question. Requiring a full Reasoning Surface for the 200th endpoint that follows pattern X is not discipline; it is ceremony, which the kernel itself names as a failure mode in [`KERNEL_LIMITS.md`](./KERNEL_LIMITS.md) § *Cost of thinking exceeds cost of being wrong*.

This file specifies how the kernel distinguishes the two cases and what the agent writes in each.

---

## The distinction

### Novel decision

The agent is choosing between live alternatives, and the choice is consequential. Examples:

- "Should this service emit events to Kafka or to a Postgres outbox?" — two viable patterns; the answer determines a substantial downstream surface.
- "Should we authenticate via JWT bearer or session cookie?" — class of attack surface differs by choice.
- "Should the new background job retry on failure, or fail fast and surface to the operator queue?" — failure semantics differ.

**Required output:** full Reasoning Surface (Knowns / Unknowns / Assumptions / Disconfirmation), per [`REASONING_SURFACE.md`](./REASONING_SURFACE.md). If the decision shape matches a named blueprint (Axiomatic Judgment, Fence Reconstruction, Consequence Chain, Architectural Cascade), the blueprint's required fields apply instead of the four-field fallback.

### Mechanical implementation

The agent is producing code that follows a pattern already chosen and recorded. The decisions are closed; only the typing of characters is open. Examples:

- "Implement the `GET /users/:id/orders` endpoint following the standard list-endpoint pattern established in `ENDPOINT_PATTERN_LIST_V1`."
- "Add Postgres outbox emission for the `OrderShipped` event, following `EVENT_EMISSION_OUTBOX_V1`."
- "Wire a new metric counter through the existing telemetry stack, following `METRIC_COUNTER_V1`."

**Required output:** `implementation-of` reference. See § *The implementation-of artifact* below.

---

## What makes a decision novel

A decision is **novel** in this project if at least one of the following holds:

1. **No prior pattern declaration covers it.** The relevant pattern_id is absent from `.episteme/patterns/` (or the equivalent location for the project; the kernel does not dictate path).
2. **A prior pattern declaration exists, but the agent's current case does not satisfy its declared `applies_when` predicate.** A pattern that covers list-endpoints does not cover a streaming-export endpoint, even if both are HTTP GET.
3. **A prior pattern declaration exists and matches, but the operator has flagged it as superseded.** Supersession is named explicitly (per [`ARTIFACT_TAXONOMY.md`](./ARTIFACT_TAXONOMY.md) — authoritative-living mutations supersede-with-history); silent override of a stale pattern is itself a failure mode.

If none of the above holds, the decision is **mechanical**, and the agent writes an `implementation-of` reference.

The shape of this rule is intentionally **positive-system**: novelty is the residual, mechanical-implementation is the enumerated set. The default-allow alternative — "treat every implementation as mechanical unless flagged otherwise" — silently regresses the kernel into ceremony-skip behavior and is therefore forbidden. See [`../core/memory/global/agent_feedback.md`](../core/memory/global/agent_feedback.md) § *Rule shape — positive vs. negative system must be a conscious choice* for the principled basis.

---

## The pattern declaration artifact

A pattern declaration is a Reasoning Surface that has been **promoted** to authoritative-living state. Promotion is operator-gated: the operator names the surface as a pattern by assigning a stable `pattern_id` and an `applies_when` predicate.

### Required fields

```yaml
pattern_id: ENDPOINT_PATTERN_LIST_V1       # SCREAMING_SNAKE_CASE, version-suffixed
declared_at: 2026-05-23T16:00:00Z          # ISO-8601 UTC, set on promotion
declared_in_event: 130                      # Event number that promoted the surface
applies_when:                               # selector predicate; the kernel
  http_method: GET                          # uses this to decide whether a
  url_shape: "/{resource}"                  # mechanical implementation can
  response_kind: list                       # reference this pattern
  exclusions:
    - "{resource}=stream-*"                 # streaming exports are NOT this pattern

reasoning_surface:                          # the original surface that became
  core_question: "..."                      # the pattern; copied in verbatim
  knowns: [...]
  unknowns: [...]                           # MUST be empty or marked resolved at promotion time
  assumptions: [...]                        # MUST carry concrete falsification conditions
  disconfirmation: "..."

constraint_regime:                          # what implementations MUST honor
  allowed: [...]
  forbidden: [...]
  cost_limits: [...]

verification:                               # how a mechanical implementation
  test_pattern: "tests/test_{resource}_list.py::test_list_returns_paginated"
  contract_ref: "contracts/list-endpoints.openapi.yaml#/paths/~1{resource}/get"
  observable: "200 status, max 100 results per page, cursor in next_page_token"

supersedes: null                            # set to prior pattern_id if this
                                            # promotion supersedes an earlier one
```

### Promotion gate

A Reasoning Surface becomes a pattern declaration only when **all** of:

1. The operator explicitly names the pattern_id at promotion time. Pattern_ids are not auto-generated; their stability is the contract.
2. The surface's `unknowns` are either empty or each marked `resolved` with the resolution noted.
3. The surface's `disconfirmation` is concrete enough to test mechanically (an `implementation-of` reference will assert it).
4. The pattern's `applies_when` predicate is structurally testable — the kernel will use it to gate the `implementation-of` reference.

If any condition fails, the surface remains a one-off Reasoning Surface and cannot be referenced by mechanical implementations.

---

## The implementation-of artifact

When the agent writes code that mechanically implements a declared pattern, instead of a full Reasoning Surface it produces:

```yaml
implementation_of: ENDPOINT_PATTERN_LIST_V1
implemented_at: 2026-05-23T16:30:00Z
context_signature:                          # minimal selector tying THIS
  http_method: GET                          # implementation to the pattern's
  url_shape: "/orders"                      # applies_when predicate
  response_kind: list

deviation_from_pattern: null                # null OR a structured object
                                            # naming the specific deviation
                                            # and a Reasoning Surface for it

verification_run:                           # filled at PostToolUse by the hook
  test_id: tests/test_orders_list.py::test_list_returns_paginated
  exit_code: 0
  contract_ref_verified: true
```

The hook's job is mechanical: confirm `implementation_of` matches an extant pattern_id; confirm `context_signature` is consistent with the pattern's `applies_when`; confirm `verification_run` lands with exit 0.

### When deviation_from_pattern is non-null

If the agent finds the pattern almost applies but a specific aspect of the current case requires deviation, that deviation **promotes the decision back to novel**. The `deviation_from_pattern` field holds a Reasoning Surface for the deviation only (not for the entire decision — the original pattern still governs the un-deviated parts).

This is the structural counter to the failure mode where the agent claims "this is just an implementation of pattern X" and silently embeds a novel choice inside it. The deviation must be named or the implementation-of reference is rejected.

---

## Why this scales

Without pattern governance, 200 endpoints that follow one architectural pattern require 200 Reasoning Surfaces. The cost of the kernel scales with codebase size, which the operator's profile correctly identifies as a kernel failure (see [`KERNEL_LIMITS.md`](./KERNEL_LIMITS.md) § *Cost of thinking exceeds cost of being wrong*).

With pattern governance, the same 200 endpoints require: 1 pattern declaration + 199 `implementation-of` references + 0 to N deviation surfaces where N is the number of endpoints that diverge non-trivially. The cost of the kernel scales with **decision count**, which is bounded by the architectural surface area of the project, not by line-of-code count. This is the correct scaling.

The base-rate argument: in any non-trivial codebase, the ratio of mechanical implementations to novel architectural decisions is at least 10:1, usually 100:1. A discipline whose cost scales with the larger of the two ratios is unsustainable; a discipline whose cost scales with the smaller one is sustainable.

---

## What this does NOT solve

This file specifies the artifact shapes and the promotion gate. It does not specify the **hook-side resolution mechanism** — the code that reads an `implementation-of` reference, finds the pattern declaration, evaluates the `applies_when` predicate against the `context_signature`, and decides whether to admit the implementation. That mechanism is its own future Event.

Until the resolution mechanism ships, the artifact shapes here serve as **documentation discipline**: operators and agents can write pattern declarations and implementation-of references by hand, the kernel honors them as authoritative-living state per [`ARTIFACT_TAXONOMY.md`](./ARTIFACT_TAXONOMY.md), and the scaling benefit accrues even without hot-path enforcement. Hook enforcement is the next layer; the artifact shapes are the prerequisite.

This is the kernel's standard pattern of incrementalism: ship the discipline first, ship the enforcement second. A discipline without enforcement still produces audit-readable artifacts; enforcement without prior discipline produces hooks that fire on something the agent does not know how to satisfy.

---

## Attribution

The novel-vs-mechanical distinction was sharpened by external feedback in Event 130 (2026-05-23) which correctly identified that uniform Reasoning Surface application at scale becomes a bottleneck rather than a forcing function. The counter — patterns are the unit of decision, not lines of code — is the same move Christopher Alexander makes in *A Pattern Language* (1977): a pattern is a *resolved tension* in a context, named once and re-applied wherever the context recurs.

The promotion gate's "unknowns empty or resolved" requirement is the structural counter to **pattern decay**: a pattern declared before its unknowns close is a fluent answer to a still-open question, and downstream implementations inherit its undisclosed gaps. Per [`KERNEL_LIMITS.md`](./KERNEL_LIMITS.md) § *Framework-as-Doxa*, a synthesized protocol that is too vague silently reintroduces the averaging the kernel was built to resist. The promotion gate is what prevents patterns from becoming that vehicle.
