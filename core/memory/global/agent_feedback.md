# Agent Feedback

Agent-learned behavioral rules that apply across projects. This file is imported into `~/.claude/CLAUDE.md` by `episteme sync`.

This file is **distinct from operator-authored policy** (`overview.md`, `operator_profile.md`, `workflow_policy.md`, `python_runtime_policy.md`, `cognitive_profile.md` — all of which encode what the operator committed to up-front). Entries here are behavioral rules the agent learned during sessions, confirmed by the operator, and promoted to global scope because they apply regardless of project or tool.

## How to classify new agent-learned feedback

When an agent learns a new behavioral rule during a session, classify before filing:

1. **Scope.** Does the rule apply everywhere (**universal**), wherever a specific pattern exists (**universal-principled**), or only in the current project (**project-specific**)?
2. **Source.** Is it **operator-authored policy** — the operator explicitly committed to a posture that predates the session — or **agent-learned feedback** — the operator corrected/confirmed a behavior during interaction?

File accordingly:

- Universal + agent-learned → this file, under "Universal rules"
- Universal-principled + agent-learned → this file, under "Universal-principled rules", with the triggering pattern explicitly named
- Project-specific + agent-learned → per-project auto-memory at `~/.claude/projects/<project>/memory/*.md`; do NOT promote to global
- Operator-authored policy → separate global file (`operator_profile.md`, `workflow_policy.md`, etc.); do NOT mix into this file

**Promotion bar.** An agent should not unilaterally promote a feedback memory to global. Two conditions must hold: (a) the operator explicitly confirms cross-project scope, AND (b) the rule does not contradict existing operator-authored policy. If either is absent, the rule stays per-project until re-audited.

**Anti-duplication.** When a rule lands here, delete the corresponding per-project copy so the same guidance does not live in two places with drift risk. Source of truth moves with the promotion.

---

## Universal rules

Rules that apply everywhere, regardless of project, tool, or context.

### No AI co-author / generated-by trailers in commits, PRs, or issue comments

**Rule.** Do not append any AI-attribution trailer to commit messages, PR bodies, or issue comments. Specifically forbidden:

- `Co-Authored-By: Claude <noreply@anthropic.com>` (or any Claude / Sonnet / Opus / Haiku variant)
- `Co-Authored-By: Codex …` / `Co-Authored-By: GPT …` / `Co-Authored-By: Gemini …` / any AI-model co-author line
- `🤖 Generated with [Claude Code](…)` or any "Generated with / by <AI tool>" footer
- Any equivalent attribution regardless of vendor

Applies to every message the operator's name will appear on: `git commit -m`, `git commit --amend`, `gh pr create --body`, `gh issue comment`, and analogues in other tools.

**Why.** The operator (junjslee) signs off on every commit and owns authorship. AI-attribution trailers (a) muddy provenance on projects whose thesis is cognitive governance — commits should not read as co-authored by the tool being governed — and (b) are Claude Code's default behavior, so the operator has to strip them each time unless the agent remembers not to emit them. This rule exists so the agent never emits them in the first place.

**How to apply.** Write the commit/PR/issue message body. Stop. Do not append any AI-attribution line. The default Claude Code commit-flow instruction to include a `Co-Authored-By` line is explicitly overridden here.

If a past commit already carries the trailer and the operator wants it removed: `git commit --amend` (if unpushed) or amend + force-push (if already pushed). Both are destructive ops and require explicit operator authorization per the repo's risk posture.

---

## Universal-principled rules

Rules whose **principle** is universal but whose **trigger** is a specific pattern. The rule applies wherever the triggering pattern exists, and is a no-op elsewhere.

### Kernel tone discipline — plain-English is marketing only

**Triggering pattern.** Project has a two-tier documentation structure: a marketing/user-facing surface (README.md, landing pages, GTM copy) AND a governance/control surface (kernel/ docs, design specs, authoritative handoff docs). Today this pattern exists in the episteme project; it applies to any future project adopting the same two-tier structure.

**Rule.** Plain-English, accessible, newcomer-friendly tone is reserved for the marketing surface. Governance-surface files must stay highly technical, precise, and rigorous — do not simplify their vocabulary to match marketing tone.

In the episteme project specifically, this means:
- Marketing surface (accessible tone OK): `README.md`, `demos/**/README.md`, landing-page copy, marketplace descriptions
- Governance surface (keep technical precision): `kernel/**`, `docs/DESIGN_V1_0_*.md`, `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/NEXT_STEPS.md`, `docs/COGNITIVE_SYSTEM_PLAYBOOK.md`, `docs/HOOKS.md`, `AGENTS.md`

**Why.** The operator needs the technical vocabulary in governance docs to control the LLM's cognitive posture. Rigorous terms (doxa, episteme, praxis, gyeol, Reasoning Surface, Blueprint D, context-signature, hash-chain, BYOS, cascade-theater, etc.) are load-bearing — they are how the kernel forces the agent into specific cognitive moves. Dumbing them down would degrade the control signal. Plain-English README is GTM accessibility; it explicitly does not propagate inward to the governance surface.

**How to apply.** When asked to rewrite, simplify, or reframe a docs file, check the target path first:

- Marketing-surface file → accessible tone OK; can front-load practical value; can soften academic framing
- Governance-surface file → preserve technical precision; do NOT swap load-bearing terminology for plain-English equivalents; cross-reference the marketing surface for readers who want accessibility, but do not dilute the governance surface itself

### Rule shape — positive vs. negative system must be a conscious choice

**Triggering pattern.** A design decision where the rule-shape itself is the question: broad rule with exceptions vs. explicit narrow enumeration. Examples: "auto-render every `docs/*.md`" with a skip-list vs. enumerate `/readme` + `/commands` as single-file exceptions; "permit all shell commands" with a deny-list vs. allow-list of known-safe commands; "agents can edit any file" with forbidden paths vs. agents can edit only a declared path list.

**Rule.** Before choosing the rule-shape, explicitly classify it as **positive system** (enumerate allowed, default-deny) or **negative system** (enumerate forbidden, default-allow). Do not default to generalization because it looks algorithmically elegant; do not default to enumeration because it feels conservative. State the choice, then make it.

**Why.** From the operator's own monologue (discussion with his father when moving from South Korea to the US in 7th grade), which is the causal root of this rule:

> *"Depending on where you are, the system a society is built upon can unconsciously shape our mindset. This idea comes from a concept my dad and I discussed when I moved to the U.S. in 7th grade: the 'Discrepancy between Positive and Negative systems.'*
>
> *A Positive System dictates that you can only do what is explicitly allowed, essentially banning everything else by default. In contrast, a Negative System lists only what you cannot do, meaning you are free to do anything else. These divergent frameworks don't just govern laws; they fundamentally shape how people within those societies think and act."*

This is the causal root of two load-bearing episteme principles already enshrined in the operator-authored cognitive_profile.md Governance Core:

- *"Constraint systems shape cognition and behavior."*
- *"Always make constraints explicit (allow-list vs deny-list, reversible vs irreversible)."*
- *"Hidden constraints become hidden objectives."*

The specific risk this rule blocks: an unconscious rule-shape choice silently constructs the opposite system. When someone says "let's auto-render everything under `/docs`" without naming it, they have just chosen a negative system by default — the skip-list they'll eventually add becomes the hidden object of their actual decision-making, and every exception earns itself against an implicit permission. When someone says "let's enumerate only these two routes" without naming it, they have just chosen a positive system — every new file is a fresh conscious decision with its own audience test. Both are valid; neither is default-correct. **The failure mode is unconscious choice**, because the implicit side becomes the hidden objective — and hidden constraints are exactly what the episteme kernel exists to make visible.

**How to apply.**

When a rule-vs-exception decision is on the table, work through:

1. **State the scope.** Is the set of instances bounded (enumerable in a sitting) or unbounded (growing with unpredictable shape)?
2. **State the cadence.** Is each new instance a fresh judgment call (audience test, contextual fit), or mechanical (pattern-match)?
3. **Classify the rule-shape you're about to choose** as positive-system or negative-system. Name it aloud.

Default tendencies (rebuttable when the specific case argues otherwise):

- **Case-by-case judgment + bounded scope** → positive-system enumeration. Each new instance is a distinct decision; a whitelist on a default-allow rule silently recreates the hidden-constraint problem at each growth point.
- **Mechanical pattern-match + unbounded scope** → negative-system enumeration. Positive enumeration doesn't scale when the allowed set is "all shell commands that aren't in a short danger list."
- **Mechanical pattern-match + bounded scope** → either can work; default to negative-system because enumeration of "all safe" is usually longer than "all unsafe."
- **Case-by-case judgment + unbounded scope** → rare and suspicious. Usually means the scope hasn't been bounded enough to decide well; bound it first.

Previous applications of this rule that established the pattern (three data points from the 2026-04-22 to 2026-04-23 window): Event 27 applied fix-only-what-the-error-names discipline to the manifest `skills` field (did NOT preemptively audit other fields despite same-class drift risk — positive-system posture on fix scope); Event 29 rejected `/docs/[...slug]` generalization in favor of single-file `/readme` route (positive-system enumeration on docs-auto-render); Event 31 added `/commands` as a second single-file exception rather than re-opening generalization (positive-system preserved). Each case explicitly named the scope, the cadence, and the rule-shape before choosing.
