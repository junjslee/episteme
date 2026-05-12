# Marketing copy — DRAFT (3 positioning hypotheses, all under test)

**Status:** DRAFT — none of these has landed in README.md or any public surface.
**Why:** `docs/PRODUCTIZATION_PLAN.md` § 0b lists three positioning hypotheses under structured testing in Phase 5. Each hypothesis gets its own candidate copy; whichever positioning returns signal in Phase 5 probes is the one that eventually lands in README. Until then, the README stays on its current "Sovereign Cognitive Kernel" framing.
**Discipline:** every claim citing the MIRROR benchmark or any CFR-reduction number must link to [arXiv 2604.19809](https://arxiv.org/abs/2604.19809) inline. No bare "70%" without the source.

---

## Positioning A — Compliance Evidence Layer (Probe 1)

**Target audience:** CCO, Internal Audit, Notified Body assessors.
**Anchor:** EU AI Act Article 12 (record-keeping) and Article 13 (deployer transparency) obligations live 2026-08-02.

### A.1 README headline

```markdown
# episteme

**Cryptographically signed evidence that a real person — not the model — authorized every irreversible AI-assisted decision.**

For high-risk AI deployers under EU AI Act Article 12, episteme produces the per-decision logging artifact the regulation describes: an operator-authored, Ed25519-signed structured commitment captured *before* the irreversible action, with RFC 3161 timestamps and Sigstore-style transparency log inclusion. A third-party auditor verifies the entire chain-of-custody from a standalone CLI, with no dependency on episteme's runtime.
```

### A.2 Manifesto (≤ 250 words)

```markdown
## What episteme is, and what it refuses to be

Every other agent tool in 2026 makes the model more capable, the agent more autonomous, or the trace more searchable. episteme does one thing: it stops the operator from authorizing an irreversible action until the operator has written down — in their own hand, signed with their own key — what they know, what they don't know, and what would prove them wrong.

The mechanism is established. The MIRROR benchmark ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809)) showed that LLMs left to self-evaluate commit confident failures at 0.60 rate; external architectural constraint drops that to 0.14. The paper's own conclusion: *"providing models with their own calibration scores produces no significant improvement; only architectural constraint is effective."*

episteme is that external constraint. The Reasoning Surface is structurally typed — Knowns and Inferences are non-fungible field types. The signing key is not in the agent's reach. The hash chain is public. The standalone verifier ships with no runtime dependency on us, so any third-party auditor can prove or disprove every claim in the packet.

We do not sell compliance theatre. We sell evidence — generated *before* the action, signed by the human, verifiable by anyone. EU AI Act Article 12 happens to require exactly this. We were going to build it anyway because the mechanism is right.

You will type more. You will move slower on irreversible operations. Your auditor will sleep through the night.
```

---

## Positioning B — Operator Decision Audit Trail (Probe 2)

**Target audience:** developer-operators who care about their own judgment quality.
**Anchor:** the second-brain anxiety. "If I outsource my brain to an LLM wiki, will my brain atrophy?"

### B.1 README headline

```markdown
# episteme

**Your own externalized reasoning, signed by you, searchable later.**

For most knowledge work, letting the model remember on your behalf is fine. For irreversible decisions — push, merge, deploy, migrate, publish — it is the failure mode. episteme is a forcing function: before you authorize the irreversible action, you write down what you know, what you don't know, and what would prove you wrong. Six months later when you wonder why you decided what you decided, the surface is there, signed, dated, and unalterable.
```

### B.2 Manifesto (≤ 250 words)

```markdown
## Why we built episteme

The Karpathy LLM Wiki pattern — let the model maintain your knowledge — is genuinely useful for everyday knowledge work. We are not against it. We use it.

But there's a class of decisions where outsourcing your cognition is exactly wrong: irreversible ones. The migration that locks the prod table. The force-push that overwrites three days of someone else's work. The `apply` that propagates a stale variable to a production secret. Frontier models are good enough now that the diff *looks fine*; the model is confident; you stop reading.

We built episteme because we wanted to keep our own judgment intact on those decisions. Not as a compliance product. As a personal forcing function: before the irreversible action, write down what you know, what you don't, and what would prove you wrong. Sign it with your own key. The model cannot author it for you — the signing key is structurally absent from the agent's reach.

The MIRROR benchmark ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809)) shows the mechanism: providing the model with its own calibration scores produces no measurable improvement; only external architectural constraint is effective. episteme is that external constraint, designed so you are the external party.

Six months later when you wonder why you proceeded with the migration, the surface is there. Signed. Dated. Unalterable. Your reasoning, externalized at the moment that mattered.
```

### B.3 "Skeptical of second-brain tools" block (positioning B context)

```markdown
## Why we are skeptical of second-brain tools for irreversible decisions

Karpathy's LLM Wiki, Mem0, Memento, and the broader AI-maintained-knowledge-base pattern share an assumption: it is good for the model to remember on your behalf. For most knowledge work, that may be true.

For irreversible decisions, it is the failure mode.

When the model holds your context, your reasoning chain, and your prior inferences, you do not audit them — you accept them. The MIRROR benchmark ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809)) showed that frontier models, left to self-evaluate, commit confident failures at 0.60 rate. External architectural constraint drops it to 0.14. The "external" in that sentence is doing all the work.

episteme insists the external is a human, signing with a key the model cannot reach. We do not make outsourcing your reasoning easier. We make it costlier — on purpose, only on the operations that cannot be taken back.
```

---

## Positioning C — Pre-Action Reasoning Commitment (Probe 3 / engineering-team adoption)

**Target audience:** tech leads / staff engineers managing teams adopting AI-assisted ops.
**Anchor:** Mitchell Hashimoto's "Harness Engineering" framing — engineer the environment, not the prompt.

### C.1 README headline

```markdown
# episteme

**The engineering-discipline forcing function for AI-assisted irreversible operations.**

Frontier models are good enough that engineers stop reading the diff. The team's audit trail records what the agent did, not what the human believed. episteme is the structural counter: every irreversible-class action (push, merge, deploy, migrate, publish) blocks at the pre-tool-use gate until an engineer authors a typed, signed Reasoning Surface. Knowns and Inferences are non-fungible field types. The model cannot author the surface; the agent's signing-key access is structurally absent. Your team's audit trail records what was *believed*, not just what was *done*.
```

### C.2 Manifesto (≤ 250 words)

```markdown
## Why episteme is harness engineering, not prompt engineering

Mitchell Hashimoto: *"Every time you discover an agent has made a mistake, you take the time to engineer a solution so that it can never make that mistake again."* That's harness engineering. episteme is harness engineering applied to one specific mistake class: the engineer who stopped reading the diff because the model sounded confident.

The MIRROR benchmark ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809)) showed the mechanism: providing an LLM with its own calibration scores produces no measurable improvement on Confident Failure Rate; only **architectural constraint** is effective. You cannot fix this by asking the model to be more careful, or by training a better evaluator. The constraint has to come from *outside* the model's prompt-and-response loop.

In episteme, the constraint is structural: a pre-tool-use hook intercepts every irreversible-class action and blocks it until a typed, signed Reasoning Surface exists. The surface schema makes Knowns and Inferences non-fungible — the model can't slip an inference past as a fact. The signing key is operator-controlled; the agent has no read path to it. The validator is independent of the runtime.

Adopting episteme team-wide is a one-week investment: install the kernel, distribute the validator hook, train engineers on `episteme surface author`. The friction is real and intentional. Operations that should not be taken back become operations that get *thought about* before they happen.

We do not claim faster shipping. We claim fewer Sunday-morning rollbacks.
```

---

## Hedging discipline — applies to ALL three positionings

Every public-facing copy that cites a CFR-reduction number must hedge it precisely as follows:

✅ *"The MIRROR benchmark ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809)) shows external architectural constraint reduces LLM Confident Failure Rate from 0.60 to 0.14. episteme is designed to replicate this effect at human-in-the-loop deployment scale; whether the deployment-scale effect matches the benchmark-scale effect is the empirical question Phase 2 of our trial answers."*

❌ *"episteme reduces Confident Failure Rate by 70%."*

❌ *"70.3% reduction (MIRROR-aligned target; OSF pre-registration TBD)."*

The first form cites the literature accurately and is honest about what we have measured (nothing yet). The second and third forms imply measurement we have not done.

---

## Probe-by-probe deployment

| Probe | Copy used | Channel | Why this positioning |
|---|---|---|---|
| Probe 1 | A — Compliance Evidence Layer | LinkedIn cold outbound to EU CCOs / Notified Body assessors | AI Act tailwind makes compliance the most concretely-priced positioning |
| Probe 2 | B — Operator Decision Audit Trail | Hacker News / Lobsters / dev.to / Substack | Developer-operator audience identifies with the second-brain anxiety |
| Probe 3 | C — Pre-Action Reasoning Commitment | Engineering newsletters (LeadDev, Pragmatic Engineer), team-channel outbound | Tech-lead audience cares about team-level discipline, harness engineering vocabulary fits |

The three probes run in parallel. Whichever positioning returns the strongest Day-90 signal is the one that lands in README at the post-probe Event.
