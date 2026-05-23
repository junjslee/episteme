# Decision Trace — Contract Gate complement

This document records the Decompose stage: the options considered, the
method chosen, and the because-chain from external-feedback signal to
shipped artifacts.

---

## Core Question (reprise)

Is deterministic contract testing (OpenAPI / Hurl / JSON Schema / DDL /
state-machines / PBT) a **substitute for**, or a **complement to**,
episteme's Reasoning Surface?

---

## Signal vs noise

The feedback arrived as a public critique: *contract testing is the real
gate; the Reasoning Surface is ceremony*. Two ways to read it.

**Noise reading.** Status-pressure: a more-engineered alternative exists;
the project's positioning is at risk. Default response would be defensive
("we already do that") or rhetorical ("but our framing matters too").
Both ignore the actual technical claim.

**Signal reading.** Contract testing is genuinely load-bearing in the
ecosystems it covers. The question is whether it covers the same failure
class as the Reasoning Surface — if yes, the critique stands; if no, the
critique conflates layers. The signal-only response is to enumerate the
failure classes and check whether each gate covers the other's.

The audit produced a binary answer: **different failure classes** —
epistemological drift (Reasoning Surface) vs behavioral drift (Contract
Gate). No overlap that would make either redundant.

---

## Options considered

### Option A — Reject the feedback ("Reasoning Surface is enough")

Maintain that the Reasoning Surface gates everything important; contract
testing is downstream tooling, not architecture.

- **For:** zero net-new artifacts; positioning unchanged.
- **Against:** dishonest about the behavioral-drift class. The Reasoning
  Surface gates a *decision* at PreToolUse; it cannot catch a code change
  that drifts away from its declared spec at PostToolUse / Stop. Failing
  to name the class doesn't make the class go away. Violates Principle I
  (make constraints explicit).

### Option B — Replace the Reasoning Surface with contract testing

Concede the substitution claim: deprecate the Reasoning Surface, adopt
contract testing as the primary gate.

- **For:** simpler architecture; one gate, one mental model.
- **Against:** loses the epistemological-drift class entirely. A
  contract gate cannot catch *false framing* — the operator confidently
  acting on a wrong premise that still produces spec-conforming output.
  The MIRROR finding ([arXiv 2604.19809](https://arxiv.org/abs/2604.19809))
  is exactly this class. Substitution discards the load-bearing finding.

### Option C — Compose both gates as a layered architecture (chosen)

Add the Contract Gate as a **dual-signal opt-in** Stop-hook alongside the
Reasoning Surface's PreToolUse gate. Ship five new artifacts to make the
composition load-bearing rather than rhetorical:

1. `kernel/ARTIFACT_TAXONOMY.md` — four-tier mutation discipline
   (`frozen-purpose` · `authoritative-living` · `working-execution` ·
   `ephemeral`). Contracts must be frozen-purpose; otherwise the gate
   enforces nothing.
2. `kernel/PATTERN_GOVERNANCE.md` — novel-decision vs
   mechanical-implementation distinction; pattern-declaration artifact +
   implementation-of reference. Counter to PTSP uniform-application
   bottleneck.
3. `docs/CONTRACT_GATE.md` — design doc; layer distinction; supported
   formats (OpenAPI · Hurl · JSON Schema · DDL · state-machines · PBT);
   composition rules with the Reasoning Surface.
4. `core/hooks/contract_gate.py` — Stop-hook stub. **Inert by default**:
   activates only when `contracts/` directory present AND explicit
   `settings.json` registration. Loss-averse posture; no blast on
   existing episteme repos.
5. `contracts/` scaffolding — declared-spec example so the format isn't
   abstract.

Plus a README FAQ section that addresses the substitution critique
directly so future readers don't re-discover the same question.

- **For:** honest about both failure classes; the composition is
  load-bearing (each gate covers a class the other can't); the dual
  signal makes activation explicit and reversible.
- **Against:** five new artifacts to author and audit; requires the
  Artifact Taxonomy to land *before* the gate makes sense (taxonomy
  defines what counts as a contract).

---

## Chosen: Option C

**Because-chain:**

- *Signal:* The feedback is technically grounded — deterministic
  contract testing genuinely catches a class of failures the Reasoning
  Surface does not gate.
- *Inferred constraint:* Both classes exist in real AI-coding-agent
  workflows; ignoring either is dishonest. The right architecture
  composes both, not substitutes one for the other.
- *Decision:* Add the Contract Gate as opt-in Stop-hook; ship the
  taxonomy + governance + design + stub + example as a single coherent
  Event so the composition is named, not implicit.
- *Loss-averse caveat:* Default the gate to inert. Activating it changes
  the failure-on-Stop semantics for any repo that adopts episteme; that
  is a blast-radius change operators must opt into per-project, not
  inherit by upgrade.

---

## What did not ship in this decision

- Live contract-gate activation by default. This is a separate Event;
  activation requires the verifier-resolution chain (OpenAPI runner
  first, then Hurl, then the rest) to have a Reasoning Surface defining
  its order before code lands.
- Auto-discovery of contracts/ across the existing episteme repo. The
  taxonomy + design ship first; mechanical scanners are downstream.
- Reasoning Surface schema changes. Substitution would have required
  rewriting `signed-surface@1.0`; complement requires zero schema
  changes. The composition is at the hook layer, not the schema layer.
