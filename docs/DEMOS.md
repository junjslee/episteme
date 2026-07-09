<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->
# Demos

Five demos. Each one targets a different class of LLM failure mode. The
matrix below is the authoritative cross-reference between named modes from
[`kernel/FAILURE_MODES.md`](../kernel/FAILURE_MODES.md) and the demo that
exhibits the kernel catching it in operation.

This file is part of the project's governance surface: it is the formal
reference a contributor uses to verify that a demo earns its place. A demo
that does not block at least one named failure mode is decoration, not proof.

---

## How to read this index

The order is **load-bearing first**, not chronological:

1. **Demo 04 — Symbiosis.** The thesis demo. Real history on this repository.
   Both parties (operator, kernel) caught each other's failure shapes inside a
   single 24-hour window. No fictional API; no synthetic example. The
   protocol synthesized from the loop is now constitutional in `AGENTS.md`.
2. **Demo 03 — Differential.** The skeptic-conversion demo. Same prompt,
   framework off vs. on. The diff isolates the named failure modes the kernel
   blocks at the Core Question gate.
3. **Demo 02 — Debug a slow endpoint.** The application-layer demo. Shows the
   kernel intercepting a fluent-wrong *"add a cache"* answer and forcing a
   schema-level root-cause investigation instead.
4. **Demo 01 — Attribution audit.** The recursive demo. Kernel applied to
   itself, auditing whether every borrowed concept in its own wording is
   traceable to a primary source. Canonical four-artifact shape.
5. **Demo 05 — Contract Gate complement.** The recursive-defense demo. Kernel
   applied to a public substitution critique of itself (deterministic contract
   testing positioned as replacement for the Reasoning Surface). Output: the
   five-artifact composition (`kernel/ARTIFACT_TAXONOMY.md`,
   `kernel/PATTERN_GOVERNANCE.md`, `docs/CONTRACT_GATE.md`,
   `core/hooks/contract_gate.py` stub, `contracts/` example) plus
   `kernel/FAILURE_MODES.md` § Mode 12 closing the mode↔counter mapping gap.

A reader who only watches one should watch **04**. A reader who needs to
verify the framework changes outputs on identical inputs should watch **03**.
A reader stress-testing the kernel against an attack on its premise should
watch **05**.

---

## Failure-mode coverage matrix

Failure modes are taken verbatim from `kernel/FAILURE_MODES.md`. The first six
are the Kahneman-grounded core taxonomy; the final three are the
governance-layer modes added in v0.11. A check mark means the demo
demonstrably blocks that mode in operation — not that the demo merely
discusses it.

| Failure mode (with mechanism) | 04 Symbiosis | 03 Differential | 02 Debug | 01 Attribution | 05 Contract Gate |
|---|:---:|:---:|:---:|:---:|:---:|
| **WYSIATI** — agent reasons from what's in context, never flags what's absent | ✓ | ✓ |  | ✓ | ✓ |
| **Question substitution** — hard question silently replaced by a nearby easy one | ✓ | ✓ | ✓ |  |  |
| **Anchoring** — first framing dominates; later evidence adjusts insufficiently | ✓ |  |  |  | ✓ |
| **Narrative fallacy** — sparse data assembled into a coherent causal story |  | ✓ | ✓ |  | ✓ |
| **Planning fallacy** — effort/risk underestimated, benefits overestimated |  |  | ✓ |  |  |
| **Overconfidence** — expressed confidence consistently exceeds calibrated accuracy |  | ✓ | ✓ | ✓ | ✓ |
| **Constraint removal** (governance) — fence dropped without reconstructing its purpose | ✓ |  |  |  | ✓ |
| **Measure-as-target drift** (governance) — proxy metric optimized; underlying goal lost |  |  | ✓ |  |  |
| **Cognitive deskilling** (governance) — operator's reasoning capacity erodes from over-reliance | ✓ |  |  | ✓ | ✓ |
| **Silent mutation of frozen-purpose** (governance · Mode 12, v1.2 RC) — frozen-purpose artifact silently edited to fit drifted implementation |  |  |  |  | ✓ |

Three modes (Question substitution, Measure-as-target drift, Planning fallacy)
are caught by demos other than 04+05; three modes (Anchoring, Constraint
removal, Cognitive deskilling) are caught load-bearingly by Demo 04. Mode 12
(silent mutation of frozen-purpose state) is caught exclusively by Demo 05,
which is also the only demo that names the failure class the Contract Gate
exists to counter.

---

## Demo 04 — Symbiosis: agent and human debug each other's intent

- **Asset.** [`demos/04_symbiosis/`](../demos/04_symbiosis/) — README, six-act
  scenario directory, alternate-world `DIFF.md`.
- **Recording.** [`docs/assets/demo_symbiosis.gif`](./assets/demo_symbiosis.gif) ·
  [`.cast`](./assets/demo_symbiosis.cast) · ~90s.
- **Script.** [`scripts/demo_symbiosis.sh`](../scripts/demo_symbiosis.sh) —
  hermetic tempdir; pacing matches the real conversation.

### Plot

It is **2026-04-27**, Day 3.15 of a planned 7-day v1.0.0 RC soak. The operator
proposes an irreversible bundle: privatize four forward-vision docs, run
`git filter-repo`, cut the GA tag, end the soak — all today. The proposal is
shaped by a named noise signature (`status-pressure` + `false-urgency`) the
operator's own `cognitive_profile.md` already declares. The Reasoning Surface
required by the kernel — *the same thinking framework the operator built* —
refuses to allow the bundle to ship without adversarial review. The review
produces three Critical findings. Independently, the operator's
profile-audit drift signal had already flagged exactly this failure mode for
weeks (`asymmetry_posture: loss-averse` running at 20% stop-condition rate
against a 55% floor). Two pieces of evidence converge. Path C decomposes the
bundle along reversibility lines. The reversible halves ship; the irreversible
halves defer to evidence-gated authorization events. A protocol is synthesized
into the framework. A day later, the operator catches a follow-up failure —
the rule had been *executed* but not *codified* — and a final event adds the
discipline to `AGENTS.md` so every future agent inherits it.

### Blueprints fired

- **Axiomatic Judgment** (Blueprint A) — resolves the conflict between Source A
  (*"ship the bundle now to lock down IP"*) and Source B (*"reversible-first
  policy, evidence-gated irreversible ops"*). Resolution hash-chained to
  `~/.episteme/framework/protocols.jsonl`.
- **Architectural Cascade** (Blueprint D) — fires on Event 67 when the
  operator catches that the protocol was executed but not codified. The
  discipline is added to `AGENTS.md` so every future agent reads it at session
  start.

### What this demo proves that no other demo proves

- **Bidirectional symbiosis.** Every other demo shows the kernel catching the
  agent. This one shows the kernel catching the *operator*, then the operator
  catching the *agent's* incomplete codification. Three loops closed in 24
  hours.
- **The kernel's telemetry independently predicted the live finding.** The
  profile-audit drift on `asymmetry_posture` had been firing for weeks. When
  Munger's latticework ran the live review, it produced the same diagnosis.
  Two independent epistemic sources, same conclusion. That is what
  *episteme is bidirectional* means in lived form.
- **Constitution received forward.** The synthesized protocol is now
  `AGENTS.md` § *Doc Classification Policy*. Every future agent on this repo
  inherits the rule through the kernel's constitution.

### What it costs to run

90 seconds to watch. Reading the six-act scenario directory, the alternate-world
`DIFF.md`, and the cross-references into `AGENTS.md` and the framework
protocols takes ~20 minutes and is the maintainer's recommended path before
running episteme in anger on your own repository.

---

## Demo 03 — Differential: same prompt, framework off vs on

- **Asset.** [`demos/03_differential/`](../demos/03_differential/) —
  `prompt.md`, `kernel_off/`, `kernel_on/`, `DIFF.md`.
- **Recording.** [`docs/assets/demo_posture.gif`](./assets/demo_posture.gif) · ~75s · cinematic differential.
- **Script.** [`scripts/demo_posture.sh`](../scripts/demo_posture.sh).

### Plot

A PM asks for a 2-sprint scope on a *"semantic search"* feature. Same prompt
walked twice. **Off:** the agent answers *how to build it* — fluent, plausible,
context-blind, and substitutes the easy *"how"* for the hard *"whether."*
**On:** the agent is forced onto the Reasoning Surface. The Core Question
reframes from *how to ship* to *whether semantic search is the right shape for
this corpus*. Unknowns are enumerated as classifiable failure modes.
Disconfirmation is pre-committed as a falsifiable pivot — *"abandon if
recall@10 on the eval set is < 0.6 after the embedding-tuning sprint."*

### Blueprints fired

- **Axiomatic Judgment** — resolves the *how* vs *whether* conflict by naming
  which feature of the context (corpus shape, query distribution, eval set
  presence) selects between them.

### What this demo proves that no other demo proves

- **Identical input, different output.** The differential isolates the
  framework's contribution. A reader who suspects the kernel just makes the
  agent slower can read the off vs on diff and see what the on path *adds* —
  the falsifiable pivot, the named Unknowns — that the off path does not.
- **Skeptic conversion.** This is the demo to show a contributor who has not
  yet decided whether episteme is worth the friction. The off output is the
  control; the on output is the experiment; the diff is the result.

---

## Demo 02 — Debug a slow endpoint

- **Asset.** [`demos/02_debug_slow_endpoint/`](../demos/02_debug_slow_endpoint/)
  — full four-artifact shape (reasoning-surface → decision-trace →
  verification → handoff).

### Plot

A p95 regression on a customer-list endpoint. Backend has been told *"add a
Redis cache."* The fluent-wrong path: do exactly that, ship, watch p95
deteriorate further at higher request volume. The framework intercepts at the
Core Question gate. The Core Question is *"what is causing the p95
regression"* — not *"how do I add a cache."* Investigation reveals the root
cause is a missing index on the `customers(org_id, created_at)` composite
sort order; the cache would have masked the symptom and made the underlying
cost worse under load. The decision trace pre-commits a Disconfirmation: if
adding the index does not move p95 below 200ms within a 15-min staging soak,
the diagnosis is wrong and the cache hypothesis is reopened.

### Blueprints fired

- **Consequence Chain** (Blueprint C) — decomposes the irreversible (*"add a
  cache"*) operation into first-order effect (latency masked at low load),
  second-order effect (cost amplified at high load via stale reads + cache
  invalidation churn), failure-mode inversion (what does failure look like
  *with* the cache vs *without*), and base-rate reference (cache-as-first-fix
  base rate is high; cache-as-correct-fix base rate is much lower for sort-bound
  queries).

### What this demo proves that no other demo proves

- **Application-layer interception.** Most demos in the field exhibit kernels
  catching kernel-level mistakes. This one catches an application-engineering
  mistake — the kind a working software team makes weekly. The interception
  is at the Core Question, before any code is written.
- **Disconfirmation as a falsifiable pivot.** The pre-committed Disconfirmation
  is the contract that allows the team to move fast on the diagnosis without
  having to re-litigate it later. If the index does not move p95, the
  diagnosis is wrong; if the index does move p95, the diagnosis is validated
  on a falsifiable observable, not on a feeling.

---

## Demo 01 — Attribution audit

- **Asset.** [`demos/01_attribution-audit/`](../demos/01_attribution-audit/) —
  `reasoning-surface.json`, `decision-trace.md`, `verification.md`,
  `handoff.md`.

### Plot

The kernel applied to its own `kernel/REFERENCES.md`. Question: is every
load-bearing concept in the kernel's wording traceable to a primary source?
The audit walks every term that appears in `kernel/CONSTITUTION.md`,
`kernel/REASONING_SURFACE.md`, and `kernel/FAILURE_MODES.md` against the
attribution list in `REFERENCES.md`. Concepts without a primary-source entry
are flagged for either a citation addition or a wording change. Verification
is the kernel's own MANIFEST: a concept claimed without attribution violates
Principle I (*explicit > implicit*).

### Blueprints fired

- **Axiomatic Judgment** — resolves any conflict between the kernel's wording
  and the cited primary source. The kernel must either match the source or
  acknowledge the deviation.

### What this demo proves that no other demo proves

- **Recursion.** The kernel can audit itself. The four-artifact shape produced
  is identical to the shape any user produces when running episteme on a
  real engineering decision. The kernel does not exempt itself from its own
  discipline.
- **Canonical output shape.** This is the demo to read first if you want to
  know *what artifacts episteme produces* without reading any philosophy.
  Open the four files in this directory in order; that is the kernel's output
  contract.

---

## Demo 05 — Contract Gate complement

- **Asset.** [`demos/05_contract_gate/`](../demos/05_contract_gate/) — full
  four-artifact shape (reasoning-surface → decision-trace → verification →
  handoff), plus a README that positions the demo against the substitution
  critique.

### Plot

External public feedback frames deterministic contract testing (OpenAPI ·
Hurl · JSON Schema · DDL · state-machines · property-based tests, per
arXiv:2506.18315) as a *substitute* for the Reasoning Surface — kernel
positioned as redundant ceremony. The critique is technically grounded:
contract testing genuinely catches a class of failures (behavioral drift —
code-vs-spec divergence) the Reasoning Surface does not gate at PreToolUse.
Defending the kernel rhetorically would be dishonest. The kernel is applied
to the critique itself. The audit produces a binary answer — **different
failure classes** (epistemological drift vs behavioral drift), at **different
layers** (PreToolUse decision admission vs Stop / CI behavioral conformance).
Substitution would discard the missing class. The shipped composition lands
the Contract Gate as an opt-in Stop-hook alongside the Reasoning Surface,
with `kernel/ARTIFACT_TAXONOMY.md` declaring four-tier mutation discipline
(contracts must be `frozen-purpose`), `kernel/PATTERN_GOVERNANCE.md`
separating novel-decision from mechanical-implementation, and a follow-up
Event 131 closing the failure-mode taxonomy with `kernel/FAILURE_MODES.md`
§ Mode 12 — *silent mutation of frozen-purpose state*. The Reasoning Surface
schema is unchanged; the composition is at the hook layer.

### Blueprints fired

- **Axiomatic Judgment** (Blueprint A) — resolves the conflict between
  Source A (*"contract testing is the real gate; Reasoning Surface is
  ceremony"*) and Source B (*"both gate orthogonal failure classes;
  substitution loses one"*) by naming which feature of the architectural
  context (PreToolUse vs Stop / CI layer; epistemological vs behavioral
  failure class) selects between them.
- **Fence Reconstruction** (Blueprint B) — the substitution critique
  proposed removing the Reasoning Surface gate; the demo reconstructs its
  purpose (gating the epistemological-drift class the Contract Gate cannot
  reach) before accepting any reduction in scope. The fence stays because
  the purpose holds.
- **Consequence Chain** (Blueprint C) — Auto-activating the Contract Gate
  by default would blast every existing episteme repo. The decision
  decomposes first-order (gate fires on commit with no `contracts/`
  directory → unhelpful failure), second-order (operator disables the
  gate via env-var workaround → kernel loses signal that contracts/
  is missing), failure-mode inversion (what does failure look like *with*
  auto-activation vs *without*), base-rate reference (default-on
  enforcement features historically generate downstream workarounds at high
  rate). Conclusion: dual-signal opt-in (`contracts/` dir present + explicit
  `settings.json` registration) is the loss-averse posture.

### What this demo proves that no other demo proves

- **Stress-test against substitution.** Demos 01–04 apply the kernel to
  questions where the kernel's role is uncontested. Demo 05 applies the
  kernel to a question where the kernel's *existence* is contested. The
  four-file artifact is the receipt that the question got a real answer,
  not a defensive deflection.
- **Architectural-commitment output.** The Execute stage produced five new
  kernel/docs artifacts and one stub hook — not a code change, a
  composition rule. Demo 05 is the audit trail for that commitment.
- **Verify-stage honesty distinguishes held vs carries.** The Verify table
  names which assumptions held by design (complement-not-substitute;
  dual-signal opt-in) vs which carry into soak (activation friction,
  verifier-resolution chain order). Demos that report all-green are weaker
  evidence than demos that name which Unknowns carry.

### What it costs to run

No recording. The four artifacts are the demo. Reading
[`reasoning-surface.json`](../demos/05_contract_gate/reasoning-surface.json),
[`decision-trace.md`](../demos/05_contract_gate/decision-trace.md),
[`verification.md`](../demos/05_contract_gate/verification.md), and
[`handoff.md`](../demos/05_contract_gate/handoff.md) in order takes ~15
minutes. The shipped artifacts the demo records (`kernel/ARTIFACT_TAXONOMY`,
`kernel/PATTERN_GOVERNANCE`, `docs/CONTRACT_GATE.md`, the stub hook, the
example) are linked from the demo's README.

---

## Runnable script demos (appendix)

Two older bash demos remain runnable as local sanity checks. They do not ship
as rendered GIFs and are not the hero demos; they exist for contributors who
want to exercise the strict-mode enforcement path on their own machine.

### `scripts/demo_strict_mode.sh`

Three acts, run hermetically in a tempdir:

1. **Lazy surface caught.** A surface with `disconfirmation: "None"` (or any
   listed lazy token) is rejected by the semantic validator.
2. **Cross-call indirection caught.** Agent writes a script that runs an
   irreversible op, executes the script in a later tool call. The stateful
   interceptor (v0.10) reads the script's contents at execute-time via sha256
   + deep-scan and blocks.
3. **Calibration learns from praxis.** `episteme evolve friction` pairs
   prediction-with-outcome telemetry, ranks the unknowns the operator keeps
   under-naming, and emits a Friction Report.

### `scripts/demo_posture.sh`

The recording source for Demo 03's GIF. Runs the off vs on differential
locally with the cinematic pacing the rendered asset uses.

---

## Recording the hero demos

The two rendered GIFs (Demo 04 Symbiosis, Demo 03 Posture-differential) are
produced from `asciinema` recordings rendered through `agg`. The reproducible
incantation:

```bash
# Demo 04 — Symbiosis
asciinema rec --cols 100 --rows 32 --idle-time-limit 2 \
  -c ./scripts/demo_symbiosis.sh \
  docs/assets/demo_symbiosis.cast
agg --speed 0.9 --cols 100 --rows 32 --font-size 15 --theme monokai \
  docs/assets/demo_symbiosis.cast docs/assets/demo_symbiosis.gif

# Demo 03 — Posture differential
asciinema rec --cols 100 --rows 32 --idle-time-limit 2 \
  -c ./scripts/demo_posture.sh \
  docs/assets/demo_posture.cast
agg --speed 0.8 --cols 100 --rows 32 --font-size 15 --theme monokai \
  docs/assets/demo_posture.cast docs/assets/demo_posture.gif
```

Full recording workflow and contributor checklist:
[`docs/CONTRIBUTING.md`](./CONTRIBUTING.md#recording-the-hero-demo).

---

## Why this index is itself a kernel artifact

A demo that does not block a named failure mode does not earn its place in
the index. Adding a demo to `demos/` without a row in the matrix above is a
governance violation: the kernel exists to make implicit constraints
explicit, and the implicit constraint here is *"every demo proves
something specific."* If a future contributor adds Demo 05, the matrix gets
a new column and at least one ✓; otherwise the demo is decoration and must
either earn the ✓ or be removed.

The matrix is the contract. The demos are evidence under the contract.
