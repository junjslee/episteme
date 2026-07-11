<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->
# episteme docs index

Primary navigation for episteme documentation.

## Start here

- `../README.md` — project overview, what problem it solves, quickstart, full command surface
- `../kernel/` — the canonical markdown spec: constitution, reasoning surface, system-1 counters, operator-profile schema
- `../kernel/CONSTITUTION.md` — the governing philosophy: why this system exists, what it believes, and what it is not

## Full documentation index (generated)

Every tracked `docs/*.md`, with its lifecycle status and a one-line purpose. This
section is generated from the lifecycle markers by `episteme docs index` — do not
hand-edit between the markers; run the command and commit the result.

<!-- episteme-docs-index:start -->
- [`ADAPTER_PORTABILITY.md`](./ADAPTER_PORTABILITY.md) · report · Adapter Portability Audit
- [`ANTHROPIC_MANAGED_AGENTS_BRIDGE.md`](./ANTHROPIC_MANAGED_AGENTS_BRIDGE.md) · living · Anthropic Managed Agents Bridge
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) · living · Architecture — The Sovereign Kernel (1.10.0-rc)
- [`COMMANDS.md`](./COMMANDS.md) · living · episteme — command reference
- [`COMPLIANCE_CROSSWALK.md`](./COMPLIANCE_CROSSWALK.md) · living · Compliance Crosswalk — `signed-surface@1.0` → Regulatory Clauses
- [`CONTRACT_GATE.md`](./CONTRACT_GATE.md) · living · Contract Gate — deterministic contract-test complement to the Reasoning Surface
- [`CONTRIBUTING.md`](./CONTRIBUTING.md) · living · Contributing to episteme
- [`CUSTOMIZATION.md`](./CUSTOMIZATION.md) · living · Customization
- [`DEMOS.md`](./DEMOS.md) · living · Demos
- [`DESIGN_V1_0_SEMANTIC_GOVERNANCE.md`](./DESIGN_V1_0_SEMANTIC_GOVERNANCE.md) · living · Design — Causal-Consequence Scaffolding & Protocol Synthesis — v1.0 RC
- [`DESIGN_V2_0_EPISTEMIC_ENGINE.md`](./DESIGN_V2_0_EPISTEMIC_ENGINE.md) · living · DESIGN v2.0 — The Epistemic Engine
- [`EVALUATION_METHOD.md`](./EVALUATION_METHOD.md) · report · Evaluation Method — Does episteme actually make a difference?
- [`EVOLUTION_CONTRACT.md`](./EVOLUTION_CONTRACT.md) · living · Evolution Contract v1
- [`HARNESSES.md`](./HARNESSES.md) · living · Harness System
- [`HOOKS.md`](./HOOKS.md) · living · Deterministic Safety Hooks
- [`HOW_TO_AUTHOR_SIGNED_SURFACE.md`](./HOW_TO_AUTHOR_SIGNED_SURFACE.md) · living · How to author a Signed Reasoning Surface
- [`HOW_TO_VERIFY_EVIDENCE_PACKET.md`](./HOW_TO_VERIFY_EVIDENCE_PACKET.md) · living · How to verify a Regulator Evidence Packet
- [`LAYER_MODEL.md`](./LAYER_MODEL.md) · living · episteme Architecture
- [`LIVE_REKOR_DECISION.md`](./LIVE_REKOR_DECISION.md) · design-history · Live transparency-log substrate — decision research
- [`MEMORY_CONTRACT.md`](./MEMORY_CONTRACT.md) · living · Memory Contract v1
- [`OPEN_SOURCE_YOUR_PROFILE.md`](./OPEN_SOURCE_YOUR_PROFILE.md) · living · Open Source Your Profile
- [`OSF_PRE_REGISTRATION_DRAFT.md`](./OSF_PRE_REGISTRATION_DRAFT.md) · report · OSF Pre-Registration — DRAFT (Phase 2 Calibration-Lift Trial)
- [`PROPOSAL_TIERED_IRREVERSIBLE_GATE.md`](./PROPOSAL_TIERED_IRREVERSIBLE_GATE.md) · spec-implemented · Proposal — Tiered Irreversible-Op Gate (v1.4.x candidate)
- [`README.md`](./README.md) · living · episteme docs index
- [`SETUP.md`](./SETUP.md) · living · Setup — Profile, Cognition, One-Command
- [`SKILLS_AND_PERSONAS.md`](./SKILLS_AND_PERSONAS.md) · living · Skills and Agent Personas
- [`SPEC_REASONING_SURFACE_BRANCHING.md`](./SPEC_REASONING_SURFACE_BRANCHING.md) · spec-implemented · Spec — Reasoning Surface branching
- [`SPEC_RIGOR_KNOB.md`](./SPEC_RIGOR_KNOB.md) · spec-implemented · Spec — `episteme rigor` (rigor knob)
- [`SUBSTRATE_BRIDGE.md`](./SUBSTRATE_BRIDGE.md) · living · Substrate Bridge — A Generalizable Contract for External Memory Systems
- [`SYNC_AND_MEMORY.md`](./SYNC_AND_MEMORY.md) · living · Sync and Memory Model
- [`THE_WAY_TO_THINK.md`](./THE_WAY_TO_THINK.md) · living · The Way to Think — 생각의 틀
<!-- episteme-docs-index:end -->

## Recommended reading order

Read the kernel first. Everything else is derived from it.

1) `../kernel/CONSTITUTION.md`
2) `../kernel/REASONING_SURFACE.md`
3) `../kernel/FAILURE_MODES.md`
4) `../kernel/OPERATOR_PROFILE_SCHEMA.md`
5) `../README.md`
6) `ARCHITECTURE.md`
7) `LAYER_MODEL.md`
8) `MEMORY_CONTRACT.md`
9) `EVOLUTION_CONTRACT.md`

## Contribution quality gate (docs changes)

For major docs updates, ensure:
- clear problem statement and intended user outcome
- knowns/unknowns/assumptions/disconfirmation for substantive claims
- consistency with `episteme` naming and command examples
- links and commands verified
