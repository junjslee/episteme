# DESIGN v2.0 — The Epistemic Engine

Status: **ACTIVE — Event 138 (2026-06-10).** Supersedes the enforcement-geometry framing of
`DESIGN_V1_0_SEMANTIC_GOVERNANCE.md` (which remains authoritative for the substrate it
specifies: chain, blueprints-as-vocabulary, telemetry). Operator directive of 2026-06-09:
*"the things you have listed are either deterministic systems or checks I have put on for
passing/failing, but we need something deeper than that… the constraint I built for myself
could be forcing us to fixate on the way we already built it."*

---

## 1. The friction

The Event 137 audit established, with live telemetry, that v1's center had inverted on its
own repo:

- The gate validated **form** — field presence, minimum lengths, lazy-token lists. Form is
  satisfiable without thinking: reasoning-shaped tokens defeat both regex validators and
  LLM judges at high rates (null-model 86.5% LC win on AlpacaEval 2.0, arXiv 2410.07137;
  "master-key" tokens at ~80% FPR against frontier judges, arXiv 2507.08794).
- The genuinely epistemic questions — *is this Unknown real? does the stated mechanism
  hold? would this disconfirmation actually fire?* — had **no implementation anywhere**.
  The kernel named the failure modes; nothing checked for them.
- Worse than neutral: rigid format constraints measurably **degrade** the reasoning they
  are meant to capture (arXiv 2408.02442) — the v1 surface demand had a negative
  second-order term.
- The fixation on *irreversible ops* as the only trigger meant the most common
  senior-vs-junior failure — a fluent, confidently-wrong **conclusion** — was never in
  scope at all. Conclusions are where epistemics live; `git push` is merely where their
  consequences land.

v1's own one-line summary was "a way to think with mechanical teeth." The audit showed the
teeth were biting the wrong layer: they could compel an artifact into existence but could
not tell thinking from theater. The operator's directive names the real product: **the way
of thinking of a senior researcher — causal mechanism (인과관계), domain priors, decomposition
to truth — applied to both the agent's work and the operator's own requests.**

## 2. Core question

> Can the kernel verify *substance* — not form — without trusting either the model's
> self-assessment (which degrades accuracy, arXiv 2310.01798) or hand-written rules
> (which check only shape)?

## 3. Thesis

The research record from 2023–2026 answers with a specific division of labor, and v2
adopts it as architecture:

> **Deterministic structure guarantees that the epistemic work happened and is preserved.
> Model judgment — in a separate context that did not produce the work, anchored to
> external evidence — judges whether it was real. Neither layer does the other's job.**

Three load-bearing results fix the design:

1. **Self-checking without an external signal is worse than nothing.** Intrinsic
   self-correction degrades accuracy (GPT-4 GSM8K 95.5→89.0 over two rounds, arXiv
   2310.01798); the survey literature finds no successful prompted self-correction
   without external feedback (arXiv 2406.01297). Therefore the interrogation's
   verification step **must name an external evidence action** (file read, execution,
   search) per load-bearing claim — a verifier prompt alone is a null op.
2. **Factored verification is the load-bearing component.** CoVe's gains come from the
   verifier answering questions *without access to the draft* (precision 0.17→0.36,
   hallucinated entities 2.95→0.68, arXiv 2309.11495); verification conditioned on the
   draft copies the draft's errors. Therefore verification of load-bearing claims is
   dispatched to a **fresh context given only the claim**, never the reasoning that
   produced it.
3. **Only architectural constraint converts epistemic awareness into behavior.** MIRROR
   (arXiv 2604.19809): feeding models their own calibration scores produces no
   improvement; external constraint cuts Confident Failure Rate 0.600→0.143. Therefore
   the engine remains **hook-enforced** — the interrogation is not a suggestion; its
   verdict artifact is what the gate reads.

Supporting results shape the protocol itself: decomposition into atomic claims beats
holistic judgment (FActScore, arXiv 2305.14251; SAFE exceeds human raters at 1/20 cost
with per-fact search, arXiv 2403.18802); assigned opposition beats neutral review (LLM
judges 76% with debate vs 48% without, arXiv 2402.06782, and a single consultant is the
worst configuration because it can hide evidence, arXiv 2311.08702); fluent
chain-of-thought systematically misrepresents the real cause of an answer, so "does this
text look like good reasoning" can never be the check (arXiv 2305.04388); and free-form
reasoning followed by structure extraction beats reasoning inside rigid schemas (arXiv
2408.02442).

Industry doctrine converges on the same boundary: Anthropic ranks deterministic
rule-feedback first and LLM-as-judge last among verification strategies, reserves hook
*blocking* for hard policy while everything conditional rides `additionalContext` phrased
as **factual statements, not imperatives** (hooks reference; imperative out-of-band text
can trigger prompt-injection defenses), and requires judge rubrics to pass a two-experts
test with an explicit "insufficient evidence" escape. Adoption data agrees from the other
side: blocking gates get circumvented (tdd-guard's own author documents agents routing
around it), while skill-text methodologies with rationalization pre-emption dominate
adoption (superpowers, 222k stars); epistemic critique survives only when embedded in a
workflow, never as a standalone nag.

## 4. The three layers

| Layer | Owns | Mechanism | Never does |
|---|---|---|---|
| **1 · Cognition** (model-side) | The way of thinking: decomposition, evidence tiers, mechanism (인과관계), base rates, opposition, weakest link, disconfirmation | `epistemic-interrogation` skill; factored verification via fresh subagent; free-form reasoning, structured artifact extracted at the end | Trust its own unverified claims; judge its own draft holistically |
| **2 · Structure** (deterministic) | Trigger routing (decision shapes), artifact contracts (exists, fresh, non-vacuous, verdict enum), traceability (hash chain), the destructive-op boundary (`block_dangerous`, strict mode) | Hooks; `_interrogation.py` validator; chain append | Judge meaning; demand reasoning inside rigid fields; block for anything short of destructive/irreversible |
| **3 · Memory** (compounding) | Lessons from verified interrogations → context-scoped protocols → push-injected guidance at the next matching decision | `write_protocol` from interrogation lessons; existing `_guidance` overlap matching (zero-intent retrieval) | Accumulate write-only exhaust; synthesize from unverified form-fills |

The decision-shape vocabulary **widens beyond irreversible ops** (operator's explicit
fence removal): irreversible op (kept — consequences), architectural cascade (kept —
coherence), conflict between credible sources (kept — Blueprint A's case), constraint
removal (kept — fences), and — new, and primary — **a load-bearing conclusion about to be
acted on or handed to the operator.** The last shape has no v1 trigger; in v2 it is the
skill's own primary invocation context and the Stop-adjacent surface of future work.

## 5. The interrogation — the senior-researcher protocol, mechanized

What separates a senior researcher from a junior is not a checklist; it is a set of moves
performed under uncertainty. Each move below is the operationalization of one of those,
each grounded in a measured result:

| Move | Senior-researcher behavior | Mechanization | Grounding |
|---|---|---|---|
| **Decompose** | Break the conclusion into atomic claims; know which are load-bearing | `claims[]`, each tiered `measured / cited / inferred / assumed`, `load_bearing` flagged | FActScore, least-to-most (arXiv 2305.14251, 2205.10625) |
| **Demand mechanism** | "Why would that be true?" — causal chain, not pattern-match | every load-bearing claim carries `mechanism`: the causal account, or explicitly `pattern-match` (which demands verification) | Turpin (arXiv 2305.04388): stated reasoning ≠ real cause, so the mechanism must be checkable |
| **Verify factored** | Check the load-bearing facts independently of the argument | fresh subagent receives ONLY the claim + tools (read/execute/search); returns supported / refuted / unverifiable + evidence | CoVe factored (arXiv 2309.11495); SAFE (arXiv 2403.18802) |
| **Oppose** | Argue the strongest case against, as an assigned position | `opposition`: written as an advocate, not a reviewer; materiality threshold — no manufactured flaws, "no material case against" is a valid outcome | Debate (arXiv 2402.06782); over-reporting reviewers (Anthropic best-practices) |
| **Find the weakest link** | Know which single claim, if wrong, collapses the conclusion | `weakest_link` + the **cheapest decisive test** for it | Margin-of-safety lattice (kernel); process-level judgment (arXiv 2305.20050) |
| **Pre-commit disconfirmation** | Name the observable that would prove this wrong, before acting | `disconfirmation` (carried over from v1 — the one v1 field the record vindicates, now anchored to the weakest link) | Popper via kernel; MIRROR's architectural-constraint result |
| **Calibrate** | Hold a confidence that tracks reality | per-claim verbalized confidence, treated as an overconfident estimator, never a gate by itself | Tian/Xiong (arXiv 2305.14975, 2306.13063) |

The artifact (`.episteme/interrogation.json`) is **extracted after** free-form reasoning,
not used as a thinking template — the schema records the thinking; it does not contain it
(arXiv 2408.02442).

## 6. Artifact contract

```json
{
  "timestamp": "ISO-8601 UTC",
  "decision": "one line: what is about to be done or concluded",
  "claims": [
    {
      "claim": "atomic, falsifiable statement",
      "tier": "measured | cited | inferred | assumed",
      "load_bearing": true,
      "mechanism": "causal account of why this holds (or 'pattern-match')",
      "confidence": 0.0,
      "verification": {
        "method": "file-read | execution | search | none",
        "result": "supported | refuted | unverifiable",
        "evidence": "what was observed, specific enough to re-check"
      }
    }
  ],
  "opposition": "strongest case against, argued — or 'no material case against' + why",
  "weakest_link": "which claim most likely fails, and the cheapest decisive test",
  "disconfirmation": "pre-committed observable that proves the decision wrong",
  "verdict": "proceed | proceed-with-revision | stop",
  "lesson": {
    "context": "project/subsystem/decision-shape where this generalizes",
    "rule": "in that context, do Y",
    "because": "the verified observation that grounds it"
  }
}
```

`lesson` is nullable — most interrogations teach nothing durable, and a forced lesson is
Doxa. Deterministic validation (`core/hooks/_interrogation.py`) checks ONLY what
determinism can check: freshness (max of content `timestamp` and file mtime — fixing the
stale-at-birth defect where agents guess wall-clock), ≥ 1 load-bearing claim, ≥ 1
load-bearing claim verified with a non-`none` method and concrete evidence, opposition
and weakest-link non-vacuous (length + lazy-token floor — a floor, not a quality claim),
verdict in enum. **`verdict: "stop"` fails closed** — an artifact that says stop satisfies
nothing.

## 7. Enforcement geometry

- The PreToolUse gate (`reasoning_surface_guard.py`) accepts **either** a valid v1
  Reasoning Surface **or** a fresh interrogation verdict (`proceed` /
  `proceed-with-revision`) for high-impact ops. The surface remains the right tool for
  operator-authored framing; the interrogation is the right tool for agent-side epistemic
  work. Back-compat is total: every v1 path still validates.
- Advisory text becomes **factual statements** per the hooks doctrine: what exists, what
  is missing, what would satisfy the gate — not commands.
- Hard blocking contracts to where the research and the adoption record both say it
  belongs: destructive commands (`block_dangerous`) and strict-mode irreversibility
  boundaries. Everything else is advisory-with-audit-trail.
- Layer 8 spot-checks repurpose to interrogation verdicts (rare, individually reviewable)
  instead of sampling every Bash call (662-deep unreviewable queue, archived Event 138).

## 8. Memory rewire — closing E1 with substance

v1's synthesis arm was starved: the only emit path (Fence Reconstruction) fired on the
rarest op class, and E1 fired silently — zero protocols in 49 days. v2 synthesizes from
**interrogation lessons**: PostToolUse, on a successful op whose fresh verdict carries a
non-null `lesson`, emits a protocol whose text is the lesson and whose
`context_signature` is built from the lesson's context — deduplicated by lesson content
hash. Lessons descend from *verified* weakest-link work, not form-fills, so the protocols
that accumulate are precisely the "in context X, do Y because verified Z" rules the v1
vision promised. The existing guidance loop (`_guidance.query`, push-injection at
matching ops) needs no change — it finally has real input.

## 9. Migration map

| v1 component | v2 role |
|---|---|
| Reasoning Surface + validators | Kept — operator-side framing artifact; one of two gate satisfiers |
| Blueprint A–D vocabulary | Kept as **decision-shape vocabulary** routing interrogation focus; field-demand ceremony no longer the only path |
| Cascade detector (post-Event-137) | Kept — Trigger routing, read-only-exempt |
| `block_dangerous` | Kept — the hard boundary, unchanged |
| Hash chain / telemetry / report | Kept — substrate, unchanged |
| Fence synthesis emit | Kept; joined by lesson synthesis (dominant source) |
| Spot-check sampling of all Bash ops | Retired (archived); resampled over interrogation verdicts |
| Imperative advisory text | Converted to factual statements (guard tonight; remaining hooks logged as deferred discovery) |
| "Forbidden irreversible" as identity | Demoted to one decision shape among five; the engine's identity is the interrogation |

## 10. Falsifiability — v2 conditions

- **E3 · Interrogation bind-rate.** After 30 days: ≥ 5 interrogation artifacts admitted
  ops, OR the mechanism is not in use and this design reverts to proposal status.
  Measured: `grep '"source": "interrogation"' ~/.episteme/audit.jsonl` + artifact chain.
- **E4 · Lesson-sourced protocols.** After 30 days of E3 holding: ≥ 3 protocols with
  `source: "interrogation"` in `protocols.jsonl`, with non-zero guidance bind-rate within
  60 days. This is E1's claim, now with a live source; the E1 self-check (Event 137)
  already monitors the store mechanically.
- **E5 · Substance over form.** A spot-check of ≥ 10 interrogation verdicts finds ≥ 70%
  judged real-engagement (not theater) by the operator. Below that, the structural
  minimums are being gamed and the validator's floors must be redesigned — or the claim
  that structure-plus-factored-verification beats form-checking is falsified for this
  granularity.

## 11. Risks, named

- **The skill is text; text can be skipped.** True — which is why the artifact is
  hook-read (MIRROR: constraint, not awareness). The residual risk is vacuous artifacts;
  E5 measures it, spot-checks sample it, and the floors fail closed on the cheapest
  gaming shapes. This is strictly better than v1, where vacuous-but-valid was the
  *designed* satisfier.
- **Factored verification costs a subagent per interrogation.** Proportionate by
  construction: interrogations attach to decision shapes, not to every Bash call — the
  Event 137 exemption already removed the per-command noise that would have made this
  unaffordable.
- **Judge bias (self-preference, fluency).** Mitigated by rubric-anchored absolute
  checks, evidence-and-falsifiability scoring rather than fluency, and the verifier
  never seeing the draft. Residual bias is real (arXiv 2410.21819) and is why E5 keeps a
  human in the calibration loop.
- **Two satisfiers could mean neither is practiced.** The gate's factual advisory names
  both paths and their exact file targets; telemetry distinguishes them; 30-day E3 review
  decides whether to consolidate.

## 12. Method choice (Decompose-stage record)

Chosen: additive engine (artifact as alternative satisfier; v1 fully preserved) over
(a) full gate replacement — rejected: destroys 1274-test back-compat and the staged-soak
discipline; (b) advisory-only skills with no enforcement — rejected by MIRROR and by the
operator's original, still-correct insight that prompts get skipped under deadline;
(c) LLM-judge inside the PreToolUse hot path — rejected: latency on every action,
circumvention pressure (tdd-guard), and Anthropic's own ranking of judge feedback as
last-resort. The additive path ties to the governing intent: the practice is the product;
v2 changes what the practice *is* (interrogation over form-filling) without surrendering
the structural floor that keeps it practiced.
