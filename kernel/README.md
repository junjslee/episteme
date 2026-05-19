# The Cognitive Kernel

The canonical specification of episteme.

Pure markdown. No code. No tooling. Nothing vendor-specific.

The kernel defines **how an agent should think** — before any platform,
framework, or adapter gets involved. Everything else in this repository
(the CLI, the hooks, the adapters, the skills) exists to deliver this
kernel into a specific runtime.

If the kernel is sound, the adapters are small. If an adapter starts
growing, the fix is in the kernel's portability, not in more adapter code.

## The ultimate why — a living thinking framework, not a stateless guardrail

An operator drowning in conflicting sources (Stack Overflow, vendor docs,
teammate folklore, LLM-synthesized "best practice") cannot reliably
distinguish which source fits THIS context — and a stock auto-regressive
LLM will not do it for them. Each conflicting pair of cases hides a
context-dependent protocol ("in context X, do Y because Z"); extracting
the protocol requires modeling *why* the sources conflict, not averaging
them. The kernel exists to force the extraction — and, over time, to
build a **living thinking framework** that synthesizes accumulated
context-fit protocols, surfaces them proactively as operator guidance at
the point of future decisions, and maintains its own architectural
coherence as the agent edits the system. Four jobs: per-action causal
decomposition, per-case protocol synthesis, active guidance at future
decisions, continuous self-maintenance. Full specification (v1.0 RC):
[`../docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md`](../docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md).

**Primary identity.** What this kernel *enforces* is named in
[`../docs/THE_WAY_TO_THINK.md`](../docs/THE_WAY_TO_THINK.md) — the primary
identity doc. The practice is the product; the Reasoning Surface schema,
hash chain, gate, and adapters are enforcement geometry, not the thing
itself. The practice is authored operator-side in
[`../core/memory/global/cognitive_profile.md`](../core/memory/global/cognitive_profile.md)
+ [`../core/memory/global/workflow_policy.md`](../core/memory/global/workflow_policy.md);
this kernel is the substrate-side specification that makes an LLM respect it.

## BYOS — bring your own skill

episteme is a **cognitive and execution governance kernel**. It is not a
skill provider, tool provider, or agent framework. The kernel does not
give agents capabilities; it intercepts state mutation at the point of
action and enforces the Reasoning Surface regardless of which external
tool, MCP server, or agent framework generated the command. A
`kubectl apply` from Claude Code, a `terraform plan` from a Cursor agent,
a `gh pr merge` from a home-grown MCP server — the kernel does not care
about provenance. It intercepts the mutation and enforces the
blueprint-shaped cognitive contract before the mutation lands. The
ecosystem provides the skills; the kernel provides the episteme.

---

## Files

- **[CONSTITUTION.md](./CONSTITUTION.md)** — the north-star document.
  Root claim, failure modes being addressed, the four principles, and what
  follows from them.

- **[REASONING_SURFACE.md](./REASONING_SURFACE.md)** — the operational
  protocol that operationalizes Principle I (Explicit > Implicit). The
  minimum viable explicitness required before any consequential action.

- **[FAILURE_MODES.md](./FAILURE_MODES.md)** — the named failure modes the
  kernel is built against, mapped to the specific artifact that counters
  each one. Nine at v0.11.0 (six Kahneman-derived + three governance-layer:
  Fence-Check / Goodhart / Ashby); two more land with v1.0 RC
  (framework-as-Doxa, cascade-theater).

- **[OPERATOR_PROFILE_SCHEMA.md](./OPERATOR_PROFILE_SCHEMA.md)** — the
  schema for encoding an operator's cognitive preferences so they travel
  with the agent across tools and sessions. Two scorecard layers (process
  + cognitive-style), per-axis metadata, expertise map, and the derived
  behavior knobs adapters compute from the axes.

- **[MEMORY_ARCHITECTURE.md](./MEMORY_ARCHITECTURE.md)** — the memory
  contract. Five tiers (working / episodic / semantic / procedural /
  reflective), retrieval by situation-match, gated promotion from
  episodic through semantic to profile-drift proposal, and declared
  forgetting per tier. The layer that turns a session-bound agent into an
  operator-persistent one.

- **[REFERENCES.md](./REFERENCES.md)** — external sources that informed
  the kernel's contents. The kernel body does not import jargon from these
  sources; concepts are described in the kernel's own vocabulary. This
  file is the attribution trail for readers who want to go deeper.

- **[HOOKS_MAP.md](./HOOKS_MAP.md)** — mapping from kernel invariants to
  runtime hooks that enforce them. Also documents the Reasoning Surface
  state file and the integrity manifest commands.

- **MANIFEST.sha256** — sha256 digest of every managed kernel file.
  `episteme kernel verify` detects drift; `episteme kernel update`
  regenerates after intentional edits. `episteme doctor` surfaces
  drift as a non-blocking warning.

---

## Corpus inventory — runtime-control vs research vs attribution

The kernel/ directory contains 18 markdown files at v1.1.0-rc1 (4,831 lines total). They split structurally into three classes by their effect on per-turn agent behavior. This classification is the spec for an eventual `kernel/core/` + `kernel/research/` directory split. The split is held back to its own gated Event because the rename has repo-wide link-breakage blast radius (every `docs/`, `web/`, `adapters/`, and external referrer carries hardcoded `kernel/<file>.md` paths).

### Runtime-control — load-bearing for per-turn agent behavior

These files directly shape what the gate fires on, what the blueprints require, and how the agent reasons before action. Editing one of these changes observable behavior in the next session.

- `CONSTITUTION.md` — the four principles. Every other kernel artifact derives from this.
- `REASONING_SURFACE.md` — the operational protocol for Principle I. The fallback four-field shape and the v1.0 RC blueprint-polymorphic surface.
- `FAILURE_MODES.md` — the named failure modes the gate is built against. Each maps to the artifact that counters it.
- `HOOKS_MAP.md` — the mapping from kernel invariants to runtime hooks that enforce them. The actual enforcement spec.
- `KERNEL_LIMITS.md` — the declared boundary of kernel applicability. When the kernel should be suspended, relaxed, or replaced.
- `FALSIFIABILITY_CONDITIONS.md` — the disconfirmation conditions for kernel claims themselves. Used by `episteme check verify`.
- `OPERATOR_PROFILE_SCHEMA.md` — the schema for encoding operator cognitive preferences. Hooks read profile axes and tune posture before firing.
- `MEMORY_ARCHITECTURE.md` — the memory contract (five tiers, gated promotion, situation-match retrieval). Defines what counts as authoritative.
- `DESIGN_BEHAVIOR_INVARIANTS.md` — the invariants the kernel preserves across edits. Self-maintenance contract.

### Research — high-signal but not on the per-turn enforcement path

These files are dense and load-bearing for design decisions, but they do not directly fire the gate. Reading them informs how kernel changes should be made; not reading them does not silently weaken any specific check.

- `ACTIVE_GUIDANCE_RANKING.md` — protocol surfacing logic. Spec for how synthesized protocols rank at future decisions.
- `CHAIN_RECOVERY_PROTOCOL.md` — recovery procedure when the hash chain detects tampering or corruption.
- `CONTINUITY_PLAN.md` — what guarantees continuity across kernel upgrades.
- `MODEL_PROGRESS_RISK_MODEL.md` — the model of risk classes the kernel mitigates.
- `PHASE_12_LEXICON.md` — kernel terminology, formalized for cross-session consistency.
- `CHANGELOG.md` — historical record of kernel-version changes.

### Attribution / index — read-on-demand only

- `REFERENCES.md` — external sources informing each principle. The kernel body uses its own vocabulary; this file is the trail.
- `SUMMARY.md` — operational summary index.
- `README.md` — this file.
- `MANIFEST.sha256` — drift-detection digest (binary-shaped, not a markdown spec; included in the count for completeness).

### Why the split is held back

The eventual `kernel/core/` (runtime-control) + `kernel/research/` (research) + `kernel/` (attribution + index) directory rename is gated to its own Event because:

1. The rename breaks every inbound link from `docs/`, `web/`, `adapters/`, and external referrers.
2. The rename also requires updating `MANIFEST.sha256`, every cross-reference inside kernel files, and the `episteme kernel verify` path-mapping.
3. Doing the rename in the same Event as the inventory loses the correction opportunity Principle IV ("the loop is the unit of progress") requires.

The inventory above settles the spec. The rename Event executes it once the inventory is reviewed and stable.

---

## How the kernel is delivered

An adapter is a thin shim that injects kernel files into a runtime's
native context-loading mechanism:

- Claude Code: concatenated into `CLAUDE.md` or referenced from global
  memory.
- Hermes: mounted as `OPERATOR.md`.
- Any future runtime: same files, different destination.

The kernel does not care which runtime loads it. The runtime does not
know what the kernel contains. That decoupling is the point.

---

## What lives here vs. elsewhere

- **kernel/** — portable spec. Markdown only. Vendor-neutral.
- **adapters/** — per-runtime delivery. Should be tiny (<100 LOC each).
- **core/memory/global/** — the *author's* personal instance of the
  operator profile, using the schema defined here.
- **docs/** — project-level documentation about the system itself
  (architecture notes, contract docs, PRDs). Not kernel.
