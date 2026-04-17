# Operator Profile Schema

An **operator profile** is the explicit encoding of a human operator's
cognitive preferences, reasoning posture, and working style. It is the
file the kernel reads to personalize its orientation step to a specific
person, so that every session starts with a formed worldview rather
than cold defaults.

This document defines the schema. The author's own instance lives at
`core/memory/global/` and can serve as a worked example.

---

## Why it is a schema, not a template

A template invites the user to fill in blanks. A schema requires them
to have an opinion.

Operator profiles fail when they read like generic best-practice
advice — at that point they contain no information the agent did not
already have by default. The schema below forces each field to express
a preference that distinguishes this operator from the default.

---

## Required sections

### 1. `overview.md` — What is this operator optimizing for?

One paragraph. The highest-level frame: what is the operator's work,
who benefits from it, and what does doing it well look like? This is
the document the agent consults when a lower-level preference is
silent — it is the tiebreaker.

Must include the operator's core working stance in one sentence.
("Systems thinker with engineering precision" is a valid stance;
"wants good code" is not — it does not distinguish anything.)

### 2. `workflow_policy.md` — How should work proceed?

The procedural contract the agent must follow inside this operator's
projects. Required subsections:

- **Standard Flow** — named stages (e.g. Frame → Decompose → Execute →
  Verify → Handoff) with one paragraph per stage describing what that
  stage produces.
- **Risk and Autonomy Policy** — which actions the agent may take
  without confirmation, which require a checkpoint. At minimum,
  name the reversible/irreversible threshold.
- **Project Memory Contract** — where authoritative project state
  lives (which files in `docs/`), and what lives in tool-native memory
  versus repo-committed docs.

### 3. `cognitive_profile.md` — How does this operator reason?

The epistemic layer. This is the operator's answer to: "how do you
decide what is true, what is uncertain, what is a bet?" Required
subsections:

- **Core Philosophy** — 3-5 foundational rules (facts vs inferences
  separation, treatment of certainty, etc.). Opinionated, not generic.
- **Decision Protocol** — the numbered sequence the operator wants
  followed for non-trivial decisions. Must reference the Reasoning
  Surface and the Disconfirmation condition.
- **Cognitive Red Flags** — patterns that should make the agent
  *slow down*, not speed up. False urgency, solution-first framing,
  hidden assumptions, etc.

### 4. `operator_profile.md` — Deterministic working-style scorecard

A numeric scorecard (0-3 scale) across canonical axes, so adapters
can make non-contextual behavioral choices (e.g. whether to run tests
by default, whether to surface risk warnings):

| Axis                      | Meaning (0 → 3)                              |
|---------------------------|----------------------------------------------|
| `planning_strictness`     | ad-hoc → formal planning before any action   |
| `risk_tolerance`          | conservative → willing to take bigger swings |
| `testing_rigor`           | manual only → tests are gating before done   |
| `parallelism_preference`  | serial → many parallel lanes                 |
| `documentation_rigor`     | code-only → docs-first contract each session |
| `automation_level`        | bash one-liners → heavy automated workflows  |

A missing axis means "unknown"; a filled-in axis is a commitment.

---

## Optional but recommended

### `python_runtime_policy.md` (or equivalent toolchain policy)

Machine-specific constraints that the agent would otherwise guess
wrong about: which Python the operator uses, which package manager,
which shell, which editor. One line per constraint. Machine-generated
content goes here if it would otherwise leak into portable docs.

### Domain-specific policy files

If the operator works in a domain with hard rules (e.g. regulated
code, data handling constraints), add a dedicated file rather than
mixing it into `workflow_policy.md`. Each domain file should be
loadable independently.

---

## Authority hierarchy

When rules conflict, the kernel resolves in this order (most specific
wins):

1. Project-level docs (`docs/*.md` inside a specific repo)
2. Operator profile (the files defined in this schema)
3. Kernel defaults (this repository's kernel)
4. Runtime defaults (whatever Claude Code, Hermes, etc. ship with)

This hierarchy is itself a consequence of Principle I
(*Explicit > Implicit*): the most specific explicit truth wins over
general defaults.

---

## How adapters consume the profile

Adapters mount the profile files into the runtime's context-loading
mechanism without transforming their content:

- Claude Code: referenced from `~/.claude/CLAUDE.md` as managed-region
  imports.
- Hermes: written to `~/.hermes/OPERATOR.md` as a managed region.
- Any future runtime: same files, same content, different destination.

If an adapter needs to *transform* the profile to fit a runtime, that
is a sign the kernel's portability is leaking — the profile schema
should be stable enough that no adapter needs to edit it.

---

## Validation

A well-formed profile should:

- Have a stated preference on every required scorecard axis.
- State the Core Question / Reasoning Surface protocol in
  `cognitive_profile.md` so the Orientation step inherits it.
- Define the authority hierarchy for the operator's project docs.
- Contain nothing that could be derived by reading the operator's
  code (project structure, conventions, etc.) — those are properties
  of projects, not of the operator.

If a profile fails any of these, it is probably not actually
personalizing anything — it is a generic best-practices document with
the operator's name on it.
