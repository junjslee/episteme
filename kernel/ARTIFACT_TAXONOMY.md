# Artifact Taxonomy

**Operational summary:**
- Every file in an episteme-governed repository falls into one of **four tiers**: **frozen-purpose**, **authoritative-living**, **working-execution**, **ephemeral**.
- The tier determines what the agent is allowed to do to the file *without explicit operator authorization*: read-only, edit-with-discipline, edit-freely, or untracked-by-design.
- The taxonomy is what makes Principle I (*Explicit > Implicit*) load-bearing on the *artifact* side, the way the Reasoning Surface makes it load-bearing on the *decision* side.
- The failure mode this counters is **silent mutation of frozen-purpose state** — the agent rewrites a declared contract, schema, or invariant to fit the code it is producing, instead of producing code that fits the declared contract.
- Operational enforcement lives in [`../AGENTS.md`](../AGENTS.md) § *Boundaries*. This file is the principled basis.

---

The kernel already has the Reasoning Surface to gate **decisions**. The Artifact Taxonomy gates **mutations**. Both are forms of the same discipline: *what is explicit cannot be silently overridden*.

A decision without a Reasoning Surface is doxa wearing fluency. An artifact without a declared tier is a frozen-purpose contract one inconsiderate edit away from becoming working-execution clay. The kernel exists to make both impossible by accident.

---

## The four tiers

### 1. Frozen-purpose

State whose *meaning has been decided* and now serves as a contract for everything downstream. The agent may **read** these freely; **mutation requires explicit operator authorization** named at the time of the change, not inferred from context.

Examples in this repo:

- `kernel/CONSTITUTION.md` — four principles, nine failure modes
- `kernel/REASONING_SURFACE.md` — schema for the surface itself
- `kernel/FAILURE_MODES.md` — the failure taxonomy the entire kernel maps onto
- `kernel/MANIFEST.sha256` — integrity digest
- `core/schemas/*` — versioned JSON schemas
- A project's declared API contracts (`contracts/*.openapi.yaml`, `contracts/*.hurl`)
- A project's DDL / migration baseline (`schema/baseline.sql`)
- A project's state-diagrams (`docs/state/*.dot`)

The failure this tier blocks: the agent regenerates the `openapi.yaml` to match the handler it just wrote, instead of failing the build because the handler doesn't match the contract. Frozen-purpose state must not be overwritten as a side effect of generation. Code conforms to it; it does not conform to the code.

**Mutation discipline.** Operator authorizes the change *as a frozen-purpose mutation* (not as routine refactoring). The change carries its own Reasoning Surface (Knowns: *why does the contract need to change*; Disconfirmation: *what observable would prove the new contract wrong*). Downstream code is updated to match the new contract in the same Event, not before, not after.

### 2. Authoritative-living

State that is **actively maintained** but **carries authority** — losing or overwriting it without intent is a governance break. Mutation is expected and welcome; mutation *without recording the rationale* is the failure mode.

Examples in this repo:

- `docs/NEXT_STEPS.md`, `docs/EVENTS.md` — operational record (PLAN/PROGRESS retired E168/E170)
- `kernel/CHANGELOG.md` — versioned kernel history
- `kernel/REFERENCES.md` — attribution contract
- `core/memory/global/*.md` — the operator's lived profile (gitignored, but authoritative)
- `AGENTS.md` — operational contract for any agent in the repo
- A project's `CLAUDE.md` / equivalent project-memory file
- A project's `README.md` (positioning surface)

The failure this tier blocks: the agent edits PROGRESS.md to remove a record that contradicts its current narrative, or rewrites CHANGELOG history to make a sequence of commits look cleaner. Authoritative-living state grows append-mostly; supersession is allowed but supersede-with-history is mandatory.

**Mutation discipline.** Edits land with named rationale (which Event, what changed, why). Supersession of prior content is explicit (not silent overwrite). Operators do not need to authorize every edit, but the rationale must survive the edit.

### 3. Working-execution

State whose **purpose is iteration** — code, tests, scripts, intermediate artifacts. Mutation is the point. The agent edits these freely under engineering discipline (typing, tests, formatting) without per-edit authorization.

Examples in this repo:

- `src/**/*.py`
- `tests/**/*.py`
- `core/hooks/*.py` (except the soak-protected hot path — see *Edge cases* below)
- `web/src/**/*.{ts,tsx}`
- `scripts/*.sh`
- `templates/*`

The failure this tier blocks: the agent over-applies discipline to working-execution state and treats every refactor as if it needed kernel-level review. Excessive ceremony on iterable surface is itself a failure mode (see [`KERNEL_LIMITS.md`](./KERNEL_LIMITS.md) § *Cost of thinking exceeds cost of being wrong*).

**Mutation discipline.** Standard engineering (read-the-file, write-tests, run-tests, format, commit). The Reasoning Surface fires only when a working-execution change is *itself a novel decision* (see [`PATTERN_GOVERNANCE.md`](./PATTERN_GOVERNANCE.md) for the novel-vs-mechanical distinction).

### 4. Ephemeral

State that is **untracked by design** — local logs, caches, build artifacts, the operator's private staging. Reading is fine if you know where to look; writing happens as a side effect of the work; mutation is not a governance concern *because nothing downstream depends on the specific bytes*.

Examples in this repo:

- `.episteme/reasoning-surface.json` — current surface state (TTL-checked)
- `.episteme/telemetry/*.jsonl` — calibration / friction records
- `~/.episteme/framework/protocols.jsonl` — synthesized framework state
- `.git/` — version-control internals
- `node_modules/`, `__pycache__/`, `*.pyc`, `web/.next/`
- `.venv/`
- Operator-private symlinked content (e.g. `docs/NEXT_STEPS.md` → `~/episteme-private/docs/NEXT_STEPS.md`)

The failure this tier blocks: the agent treats ephemeral state as authoritative and reasons from it ("the cache says X, therefore X"). Ephemeral state is the *consequence* of authoritative state, never the *source*.

**Mutation discipline.** The agent writes to ephemeral state freely when the work requires it. The agent does *not* commit ephemeral state to git, and does *not* recover from a missing ephemeral file by treating absence as evidence — absence of ephemeral state means *not yet computed*, not *known absent*.

---

## Edge cases

**Soak-protected hot path.** `core/hooks/reasoning_surface_guard.py` is structurally working-execution but operationally frozen-purpose during a soak window. The fix is in the soak protocol, not the taxonomy: a working-execution file can be temporarily promoted to frozen-purpose by an explicit constraint regime (see kernel CHANGELOG entries that name "soak-protected" surfaces).

**Generated artifacts.** SVGs rendered from DOT, PNGs rasterized from SVGs, `kernel/MANIFEST.sha256` regenerated from kernel content. These are **derived ephemeral** — they appear in git for distribution convenience, but their authority is their source. If the manifest disagrees with the kernel content it covers, the manifest is wrong; if a rendered SVG disagrees with its `.dot` source, the SVG is wrong. The taxonomy applies to the source, not the artifact.

**The agent's own working-execution surface.** When the agent is iterating on a feature, the in-progress code is working-execution to the agent and ephemeral to the operator until merged. Pull requests are the promotion mechanism: the agent's working state crosses the operator-review checkpoint, and on merge becomes authoritative-living.

---

## Why this matters — the failure class

LLM agents are auto-regressive generators. The training objective rewards local fluency: producing the next token that fits the immediate context. When the agent is generating code and the immediate context includes a contract, schema, or invariant, the locally-fluent move is to *modify the constraint to match the generated code*, because that makes the surrounding tokens "consistent."

This is the same failure class the Reasoning Surface counters on the decision side. There, the failure is silently substituting an easier question for the harder one. Here, the failure is silently modifying a frozen contract to match a fluent (but wrong) implementation.

A typical instance: the agent is asked to implement a handler. The OpenAPI spec declares the handler returns `204 No Content`. The agent's first draft returns `200 { "ok": true }`. Instead of changing the implementation to return 204, the agent regenerates the OpenAPI spec to say `200 { ok: boolean }`. The handler and the spec now agree — and the consumer that depended on 204 silently breaks.

The Reasoning Surface cannot catch this: the agent is not making a decision, it is doing what looks like routine code-generation. The Artifact Taxonomy catches it: the spec is frozen-purpose; modifying it requires explicit authorization; the build fails when the handler does not match the spec; the operator is in the loop before the consumer breaks.

This is also why the kernel's complement-not-substitute relationship to contract testing is load-bearing (see [`../docs/CONTRACT_GATE.md`](../docs/CONTRACT_GATE.md)). Contract tests verify *behavior matches spec at runtime*. The Artifact Taxonomy prevents the *spec itself from being silently rewritten to match drifted behavior*. Without the taxonomy, contract tests can be defeated by spec mutation. Without contract tests, the taxonomy can be defeated by behavior drift. The pair holds where either alone leaks.

---

## How tiers interact with the Reasoning Surface

The Reasoning Surface fires when a *decision* is being made. The Artifact Taxonomy fires when a *file is being touched*. They overlap:

- **Frozen-purpose mutation** ⇒ ALWAYS triggers a Reasoning Surface, regardless of how small the change looks. Editing `kernel/CONSTITUTION.md` to add a comma still requires a surface because the *act* of editing is the load-bearing event, not the byte delta.
- **Authoritative-living mutation** ⇒ TRIGGERS a Reasoning Surface when the edit changes operational direction (e.g., PROGRESS.md superseding a prior Event); does NOT trigger one for routine append (e.g., adding a new Event entry that does not invalidate any prior content).
- **Working-execution mutation** ⇒ TRIGGERS a Reasoning Surface when the change is itself a novel decision (per [`PATTERN_GOVERNANCE.md`](./PATTERN_GOVERNANCE.md)); does NOT trigger one for mechanical implementation of an already-declared pattern.
- **Ephemeral mutation** ⇒ NEVER triggers a Reasoning Surface. Ephemeral state has no authority; nothing to gate.

This is what makes the kernel scalable without going either over-strict (Reasoning Surface on every line edit) or under-strict (Reasoning Surface only on explicit `episteme` commands). The tier of the artifact carries part of the gating decision.

---

## Attribution

The taxonomy formalizes a discipline already present implicitly in [`../AGENTS.md`](../AGENTS.md) § *Boundaries*. The framing as four distinct tiers crystallized in Event 130 (2026-05-23) in response to external feedback that contract-test enforcement and reasoning-surface enforcement are complements at different layers — the layer distinction is exactly the frozen-purpose / working-execution distinction generalized.

The agent's silent-mutation failure mode is a specific instance of Kahneman's WYSIATI (*What You See Is All There Is*) applied to file content: the agent reasons from what is *in* the file as if that were the *purpose* of the file, and rewrites the file to make its current generation consistent — losing the distinction between *what the file says* and *what the file is for*. Per Principle I, the purpose must be explicit; the tier is how the purpose is encoded.
