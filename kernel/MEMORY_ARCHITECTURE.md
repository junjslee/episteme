# Memory Architecture

**Operational summary:**
- Five tiers: **working** (session scratchpad, compresses) · **episodic** (per-decision record + outcome) · **semantic** (cross-session patterns derived from episodic) · **procedural** (operator-specific reusable action templates) · **reflective** (memory about memory — staleness, drift, promotion proposals).
- Retrieval is query-by-situation, not query-by-key. Past decisions are surfaced by Reasoning-Surface-shape match, ranked by `recency × similarity × outcome_validation`.
- Promotion is staged: episodic → semantic (pattern + outcome validation threshold) → profile-drift proposal (gated by human review; never auto-merged).
- Forgetting is declared per tier with TTL + compaction rules. Working: session-scoped. Episodic: 90-day raw + compacted summary. Semantic: persistent, prunable on contradicting evidence. Procedural: persistent, operator-revised. Reflective: fully derivable.
- Write and read discipline is specified per workflow stage (Frame reads profile + semantic + recent episodic; Handoff writes episodic). Bypassing the contract is the failure; adding tiers outside the contract is the other failure.

---

The kernel's memory architecture is the layer that turns a session-
bound agent into an operator-persistent one. It is the infrastructure
behind the claim in [CONSTITUTION.md](./CONSTITUTION.md) that the
kernel is "the frame from which work proceeds," not a session artifact.

The memory contract schemas in `core/schemas/memory-contract/` define
the *shape* of records. This document defines the *contract* —
which records get written when, which tiers they live in, how
retrieval works, how patterns get promoted, and what forgetting
looks like.

Without a declared contract, the schemas become storage with no
discipline about when to write or what to read, and the operator-
persistence claim stays aspirational.

---

## The five tiers

Each tier has a declared purpose, a declared lifetime, a declared
writer, and a declared reader. Tiers do not share responsibilities;
confusing them is the dominant failure mode.

### 1. Working

**Purpose.** Per-session scratchpad. What the agent is reasoning about
*right now*: the current Reasoning Surface, tool outputs just
observed, the user's most recent instructions.

**Lifetime.** Session-scoped. Compresses under context pressure
(runtime-specific: Claude Code's PreCompact event, etc.).

**Writer.** The agent, continuously, as part of normal operation.

**Reader.** The agent, continuously.

**Persistence contract.** None. Anything the agent wants preserved
across sessions must be promoted to another tier before the session
ends. The `PreCompact` hook is the last chance to make that choice
explicit; anything left in Working at compaction is lost by design.

### 2. Episodic

**Purpose.** Per-decision records. Each consequential decision
produces one record containing: the Reasoning Surface as filed, the
domain marker, the action taken, the observed outcome, any fired
Disconfirmation, the delta between predicted and observed.

**Lifetime.** 90 days raw; then compacted into a summary record that
retains the decision's shape and outcome but drops verbatim content.

**Writer.** The Handoff stage of the workflow. Writing an episodic
record is part of what it means to close a cycle. Skipping the write
is the "workflow bypass" failure mode — the cycle produced a result
but left no trace usable for future retrieval.

**Reader.** The Frame stage of the next cycle, via the retrieval
contract below. Also the semantic-tier promotion process and the
profile audit loop.

**What makes a decision episodic-worthy.** Four cases, no others:

1. Any action covered by the high-impact pattern set (git push,
   publish, migrations, cloud deletes, DB destructive ops, lockfile
   edits).
2. Any action that the hook layer blocked or escalated.
3. Any decision that fired a named Disconfirmation condition (full
   or partial).
4. Any decision where the operator explicitly elected to record.

Recording everything makes the tier noise; recording only successes
makes it a highlight reel. The four cases above are the ones whose
outcomes carry calibration information.

### 3. Semantic

**Purpose.** Cross-session patterns derived from episodic records.
Not raw decisions — *generalizations* across them: "for this
operator, decisions tagged `risk: high` + `domain: frontend` + noise
signature `false-urgency` validate 40% of the time; the operator
should probably slow down in that shape."

**Lifetime.** Persistent. Pruned when accumulating contradicting
evidence invalidates a pattern.

**Writer.** The promotion process (below). Never written directly by
the agent during a cycle.

**Reader.** The Frame stage, to propose priors on the Reasoning
Surface. Proposals, not autofills — the kernel's rule is that the
semantic tier surfaces relevant past patterns, and the operator or
agent decides whether they apply to *this* decision.

**What semantic memory looks like operationally.** Less a table of
facts, more a set of "in decisions shaped like this, the outcome
distribution was this" records. Retrieval gives the Frame stage a
distribution, not a conclusion.

### 4. Procedural

**Purpose.** Operator-specific reusable action templates. Distinct
from `workflow_policy.md` (which is universal across the operator's
projects) and from project-level templates (which are project-
scoped). Procedural captures things like: "when this operator says
'refactor', the action sequence is A → B → C," "when this operator
debugs a flaky test, the diagnostic order is X → Y → Z."

**Lifetime.** Persistent. Operator-revised — procedural knowledge
is edited deliberately, not accumulated.

**Writer.** The operator, explicitly, or the agent via a proposal
gated by operator review (same gating as profile-drift proposals).

**Reader.** The Decompose stage of the workflow, to generate the
initial task breakdown in a shape the operator recognizes.

**Why this tier exists.** Without it, procedural knowledge lives
either in the workflow policy (too general, not operator-specific) or
in the operator's head (not reusable by the agent). The tier gives
the agent a legitimate place to remember "this operator does X this
way" without forcing every such fact into the universal policy.

### 5. Reflective

**Purpose.** Memory about memory. Which axes of the profile are
drifting? Which unknowns does the operator chronically under-
elaborate? Which semantic patterns are high-conviction vs
low-conviction? What has the operator been asked to elicit, and
when?

**Lifetime.** Fully derivable from the other tiers. Held as a
materialized view for efficiency, not as a source of truth.

**Writer.** Scheduled job: the reflective layer is rebuilt from
episodic + profile on a cadence (daily or per-session-start).

**Reader.** The adapter, at SessionStart — to surface staleness
warnings, drift flags, and pending elicitation prompts.

---

## Retrieval contract

Retrieval is **query-by-situation**, not query-by-key. The Frame
stage does not retrieve "everything tagged `auth`"; it retrieves
"past decisions whose Reasoning Surface is shaped similarly to this
one, weighted by recency and outcome validation."

### Similarity

Two Reasoning Surfaces are *similar* when:

- Their Core Questions overlap semantically (embedding similarity
  above threshold, or keyword overlap above threshold for the
  embedding-free path).
- Their Unknowns sets overlap — sharp unknowns match sharp unknowns,
  not vague ones.
- Their domain markers match.
- Their action-class classification matches.

Similarity is a scalar in [0, 1]. It is computed, not asserted.

### Ranking

Retrieved records are ranked by:

```
rank = similarity × recency_decay × outcome_weight
```

Where:

- `recency_decay` = exp(-age_days / tau), with tau configurable per
  tier (shorter for episodic, longer for semantic).
- `outcome_weight` = 1.0 for decisions whose Disconfirmation did
  *not* fire (the plan held), 0.5 for partial-firing decisions, 0.2
  for fully-falsified decisions (those are still informative but
  should not dominate the prior).

### Retrieval result shape

Every retrieved item carries its similarity score, its age, and its
outcome weight, so the Frame stage can visibly see why the record
was surfaced. A record that is top-ranked through recency alone is
treated differently from one that is top-ranked through similarity
+ outcome — the operator sees both sources of rank.

### Retrieval refusal

The retrieval layer is allowed to return no matches. "No similar
past decisions found" is a valid output, and it is more useful than
a low-similarity match presented as a prior. The cognitive cost of
a spurious match is higher than the cost of no match — see the
"first-framing persistence" failure mode.

---

## Promotion contract

Promotion moves patterns up the tier stack: episodic → semantic →
profile-drift proposal. Each step has a gate; no promotion happens
silently.

### Episodic → semantic

**Trigger.** A pattern (a cluster of similar episodic records)
appears at least N times across a window, and the outcome
distribution across the cluster is stable (not flipping between
validate/invalidate).

**Action.** A semantic record is proposed, describing the pattern
and its outcome distribution. The proposal enters a review queue.

**Review.** The agent can accept the proposal during a Frame stage
(lightweight review) or the operator can explicitly review during a
scheduled audit. Silent auto-promotion is not allowed: the semantic
tier is what the kernel uses to pre-shape future decisions, and a
silently promoted pattern is an unaudited change to the agent's
default priors.

### Semantic → profile-drift proposal

**Trigger.** A semantic pattern persists with high conviction across
a long window (e.g., 30+ episodic records consistent with the
pattern over 90+ days), and the pattern's implied operator disposition
diverges from the profile's currently-claimed value on an axis.

**Action.** A profile-drift proposal is written to the reflective
tier. The next SessionStart surfaces the proposal to the operator
as a "your claimed `testing_rigor` is 3, but your last 40 high-
impact decisions imply 1.5; re-elicit?" prompt.

**Review.** Operator-only. The agent never updates the profile
from the semantic tier without explicit operator confirmation. The
kernel's rule that the operator owns their own profile is stronger
than the convenience of auto-update.

---

## Forgetting contract

Forgetting is declared, not incidental. Every tier has a rule for
what decays, when, and how.

| Tier         | Forgetting rule                                                                                  |
|--------------|--------------------------------------------------------------------------------------------------|
| Working      | Session-scoped. Compresses under context pressure. Nothing persists past session end.            |
| Episodic     | 90 days raw. Then compacted into a summary preserving decision shape + outcome but dropping verbatim content. Compacted records remain retrievable but at lower fidelity. |
| Semantic     | Persistent. Pruned when N contradicting episodic records accumulate (the pattern is no longer stable). |
| Procedural   | Persistent. Operator-revised only — no automatic pruning. An obsolete template is removed by the operator, not by the kernel. |
| Reflective   | Derivable. Rebuilt on schedule; no independent lifetime.                                         |

The compaction of episodic records at 90 days is a Principle-I move,
not a storage optimization: the verbatim content of decisions older
than 90 days carries less signal per byte than the compacted summary
(decision shape + outcome + lesson), so the tier's signal-to-noise
ratio actually improves under compaction.

### What is never written

Two categories never enter any tier:

1. **Secrets.** API keys, tokens, passwords, any content matching
   secret-like patterns. Detected at write time, rejected with a
   visible error — the record is blocked, not silently redacted.
2. **Operator-identifying paths.** Absolute home paths, usernames,
   device identifiers. Normalized to portable forms before write.

---

## Write discipline — what each stage writes

The workflow stages are the points where memory is written. Each has
a declared write responsibility; writes outside the declared set are
the failure mode.

| Stage      | Writes                                                                                     |
|------------|--------------------------------------------------------------------------------------------|
| Frame      | Reasoning Surface to working tier; snapshot of retrieved episodic/semantic priors.         |
| Decompose  | Task breakdown, option set, because-chain — to working tier only.                          |
| Execute    | Tool-call records, observations — to working tier. Episodic write deferred to Handoff.     |
| Verify     | Evaluation result, which Assumption moved to Known, which Unknown sharpened — to working.  |
| Handoff    | Episodic record assembled from the cycle's working content. Authoritative project docs (PROGRESS, NEXT_STEPS) updated. |

The Handoff write is the one the workflow policy is protecting with
its "update authoritative docs" rule. Without it, every cycle is a
leak.

---

## Read discipline — what each stage reads

| Stage      | Reads                                                                                                                    |
|------------|--------------------------------------------------------------------------------------------------------------------------|
| Frame      | Profile (all tiers); semantic tier (priors on this shape of decision); recent episodic tier (last N high-impact records in this project). |
| Decompose  | Procedural tier (this operator's action templates for this task shape); profile (`dominant_lens` and `preferred_lens_order`). |
| Execute    | Working tier (the cycle's own prior state). The operator profile's `default_autonomy_class` gates which actions need confirmation. |
| Verify     | Working tier; the Reasoning Surface's named Disconfirmation.                                                             |
| Handoff    | Working tier (to assemble the episodic record); the project's authoritative docs (to write the delta).                   |

Reads outside the declared set are not a policy violation — they are
a signal that the stage definitions are too narrow. The response is
to update this document, not to silently broaden reads.

---

## Integrity guarantees

- **Episodic is append-only.** Never edited in place. Compaction
  produces new records that supersede originals via the
  `supersedes` / `superseded_by` fields in the common schema.
- **Promotion is idempotent.** Re-running the promotion job on the
  same episodic records produces the same semantic proposals,
  whether or not the earlier proposals were accepted.
- **Forgetting is logged.** Compaction and pruning events are
  themselves recorded in the reflective tier, so "why does this
  record no longer exist in the form I expect?" has an answer.

---

## How this interacts with the rest of the kernel

- The **Reasoning Surface** is the shape memory is indexed by.
  Every field of the Surface contributes to similarity matching on
  retrieval.
- The **operator profile** is the static prior; the memory tiers
  are the dynamic update layer. Together they answer "how does this
  operator think, and what does their recent record show?"
- The **friction analyzer** reads the episodic tier to produce its
  ranked under-elaborated unknowns, and writes its output as
  reflective-tier records.
- The **evolution contract** (propose → critique → gate → promote)
  is implemented on top of the promotion contract above. The
  gate is the human-review step between semantic and profile-drift.

---

## Attribution

- **Tiered memory (working / episodic / semantic / procedural).**
  Draws on cognitive psychology's long-memory taxonomy (Tulving,
  Squire) without importing the research-specific terminology.
  Reflective memory is named by analogy to metacognition research.
- **Query-by-situation retrieval.** Klein's recognition-primed
  decision framing — experts retrieve past situations by shape, not
  by key. The kernel generalizes this from human expertise to
  agent retrieval.
- **Promotion contract (gated, never auto-merged).** Argyris/Schön
  double-loop learning: frame-level updates (profile drift) are
  consequential and should be accountable, not silent.
- **Forgetting as discipline, not incident.** Shannon on
  signal/noise — older verbatim content has lower signal per byte
  than compacted summaries. Forgetting is active, not passive.
- **Integrity guarantees.** Event-sourcing / append-only discipline
  from systems engineering. Cited here because the discipline
  differs from general-purpose database design.

Full citations: [REFERENCES.md](./REFERENCES.md).
