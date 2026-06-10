---
name: epistemic-interrogation
description: Senior-researcher interrogation of a load-bearing decision or conclusion — decompose into claims, verify the load-bearing ones in a fresh context with external evidence, argue the opposition, name the weakest link, pre-commit disconfirmation, record the verdict artifact the episteme gate reads.
---

# Epistemic Interrogation

Use this skill when a **load-bearing decision or conclusion** is about to be acted on or
handed to the operator: an irreversible or high-impact operation, an architectural change,
a conflict between credible sources you are about to resolve, a constraint you are about
to remove, or an analysis whose conclusion the operator will rely on. The episteme
PreToolUse gate accepts this skill's verdict artifact as a satisfier for high-impact ops.

This is not a form to fill. Reason free-form first; the artifact records what you did at
the end. A schema filled without the work is theater, and the spot-check loop samples for
exactly that.

## The protocol

**1 · Name the decision.** One line: what is about to be done or concluded. If you cannot
state it in one line, you have not isolated the decision yet.

**2 · Decompose into claims.** List the atomic, falsifiable claims the decision rests on.
Mark which are **load-bearing** (if this claim is wrong, the decision collapses). Tier
each claim:
- `measured` — you observed it yourself in this session (ran it, read it)
- `cited` — an external source states it (name the source)
- `inferred` — it follows from other claims by a mechanism you can state
- `assumed` — you are taking it on faith (these demand the most scrutiny)

**3 · Demand the mechanism.** For each load-bearing claim, state *why it would be true* —
the causal chain (인과관계), not the pattern-match. "This usually works" is a pattern-match;
"this works because X causes Y under condition Z" is a mechanism. If the honest answer is
pattern-match, write `pattern-match` — that claim now requires verification.

**4 · Verify, factored.** For each load-bearing claim that is not already `measured`:
dispatch a **fresh subagent that receives ONLY the claim** — not your reasoning, not the
conversation, not the draft — with instructions to verify it via external evidence:
file reads, command execution, or search. Record the result (`supported` / `refuted` /
`unverifiable`) and the specific evidence observed.

Why factored: a verifier that sees your draft copies your errors — independence of the
checking signal is the load-bearing component, not the act of checking. Why external
evidence: self-review without a new signal measurably degrades accuracy; a verification
step that reads no file, runs no command, and searches nothing is a null op.

**5 · Argue the opposition.** Write the strongest case **against** the decision — as an
advocate assigned that position, not as a neutral reviewer summarizing risks. What would
the person who disagrees say, and what is their best evidence?

Materiality threshold: flag only objections that would change the decision. If the honest
opposition is weak, write "no material case against" and why — a manufactured objection
is as dishonest as a suppressed one.

**6 · Name the weakest link.** Which single claim is most likely to be wrong? What is the
**cheapest decisive test** that would settle it? If that test costs less than being wrong,
run it now instead of finishing this artifact.

**7 · Pre-commit disconfirmation.** The concrete observable that would prove the decision
wrong after the fact. Anchor it to the weakest link. "If issues arise" is not observable;
"if X exceeds Y within Z" is.

**8 · Verdict.**
- `proceed` — load-bearing claims verified, opposition answered
- `proceed-with-revision` — proceed only after the named revision (make it first)
- `stop` — a load-bearing claim was refuted or the opposition wins; do not proceed, and
  say so to the operator

A refuted load-bearing claim with a `proceed` verdict is a contradiction; the gate
rejects it.

**9 · Extract the lesson (usually null).** If this interrogation taught something durable
and context-specific — "in this project/subsystem/decision-shape, do Y, because verified
Z" — record it. It becomes a hash-chained protocol that resurfaces at the next matching
decision. Most interrogations teach nothing durable; a forced lesson pollutes the
framework. Null is the honest default.

## Rationalization pre-emption

| The thought | The reality |
|---|---|
| "The conclusion is obviously right" | Obviousness is fluency, and fluency is the failure mode this exists for. Decompose it; obvious claims verify fast. |
| "Verification will just confirm what I found" | Then it is cheap. The cases where it doesn't are the entire value. |
| "There's no real opposition here" | Then write "no material case against" and why — that line, honestly earned, is the check. |
| "I already reasoned carefully in-context" | Your reasoning text does not reliably reflect what produced your answer. The artifact exists because re-reading your own draft cannot catch this. |
| "This is a small decision" | Small decisions don't trigger this skill. If it triggered, something classified the blast radius as load-bearing. |

## The artifact

Write `.episteme/interrogation.json` in the project root when the protocol is done:

```json
{
  "timestamp": "<ISO-8601 UTC — run `date -u +%Y-%m-%dT%H:%M:%SZ`, do not guess>",
  "decision": "one line",
  "claims": [
    {
      "claim": "atomic, falsifiable",
      "tier": "measured | cited | inferred | assumed",
      "load_bearing": true,
      "mechanism": "causal account, or 'pattern-match'",
      "confidence": 0.85,
      "verification": {
        "method": "file-read | execution | search | none",
        "result": "supported | refuted | unverifiable",
        "evidence": "what was observed, specific enough to re-check"
      }
    }
  ],
  "opposition": "the argued case against, or 'no material case against' + why",
  "weakest_link": "the claim most likely wrong + the cheapest decisive test",
  "disconfirmation": "pre-committed observable that proves this wrong",
  "verdict": "proceed | proceed-with-revision | stop",
  "lesson": null
}
```

The gate validates structure only (freshness, floors, verdict consistency) — substance is
your job, and the spot-check loop audits it. On a successful operation, a non-null
`lesson` is synthesized into the framework automatically.
