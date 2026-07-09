<!-- episteme-lifecycle: status=spec-implemented; reviewed_as_of=E147 -->
# Proposal — Tiered Irreversible-Op Gate (v1.4.x candidate)

> Status: **Stages 0 + 1 + 2 + 3 + 4 + FINAL all landed (Events 134, 134.1, 135).**
> Live hook wire-up at `core/hooks/reasoning_surface_guard.py:_try_tier1_dispatch`;
> kernel doc surfaces the Tier 1 path at `kernel/REASONING_SURFACE.md`;
> classifier + tests at `core/practice/irreversible_tier.py` and four test
> files. Calibration CLIs at `episteme tier1 audit` + `episteme evaluate`.
> Evaluation method at `docs/EVALUATION_METHOD.md`. **Only remaining gate
> is Stage 5 — lived-behavior soak clearance** (N ≥ 20 Tier 1 ops, ≥ 7
> calendar days, ≥ 90% rationale-accuracy). The runtime gate is in the
> code; it opens automatically when lived telemetry clears the threshold.
> See § 6 for the per-stage landing markers.
>
> Cross-references: `kernel/REASONING_SURFACE.md` (the gate this proposal
> refines), `kernel/CONSTITUTION.md` § Principle IV (small reversible actions
> beat large irreversible bets — preserved), `AGENTS.md` § "When to stop and
> ask" (unchanged), `core/memory/global/operator_profile.md`
> `asymmetry_posture` (loss-averse — refined, not relaxed).

---

## 1. Friction signal

The outer guard at `core/hooks/reasoning_surface_guard.py:27` is
**strict-blocking by default.** Every Bash command matching
`HIGH_IMPACT_BASH` (lines 170-192) — 22 patterns including
`\bgit\s+push\b`, `\bgh\s+release\s+create\b`, `\bpip\s+install\b`, etc. —
requires a fresh `.episteme/reasoning-surface.json` with **all five Fence
fields** (when the Fence Reconstruction blueprint fires) or the **generic
Consequence-Chain fallback** (when no blueprint fires).

The strict-blocking posture is correct for Tier 2/3 ops (e.g., `git push
origin master`, `terraform apply`, `DROP TABLE`). It is **over-tax** for
Tier 1 ops — provably-bounded irreversible operations whose blast radius
is local-feature-branch or prerelease-only, and whose reversibility cost
is a single `git revert` or `gh release delete` away. Forcing the
full-fill on Tier 1 ops produces ceremony-shaped Reasoning Surfaces ("what
unknowns does `git push origin event-N-coherence` carry?"), which is
exactly the failure-mode `kernel/REASONING_SURFACE.md` § *The surface as
ceremony* warns against. **Ceremony-shaped surfaces train the agent to
treat the discipline as friction, not as cognition.**

The operator's elicited `asymmetry_posture: loss-averse` (re-confirmed
2026-04-27 via Events 65-67 lived behavior) is **load-bearing on
high-blast-radius irreversibles** — that is what it is protecting against.
It is **not** load-bearing on Tier 1 ops, because the failure mode
loss-averse is countering (confidently-wrong on an irreversible bet) does
not apply when the action's blast radius is bounded and the rollback path
is one-command.

---

## 2. Principle preserved

Principle IV is **not** relaxed by this proposal:

> A large irreversible bet collapses many loops into one and removes the
> correction that feedback would have provided.

Tier 1 is not a large irreversible bet. It is a **bounded** irreversible
move whose feedback-correction is preserved by the (a) named rollback
path and (b) operator confirmation. Principle IV protects against
*confidently-wrong-because-the-loop-collapsed*; Tier 1 does not collapse
the loop.

What this proposal **does** relax is the Reasoning Surface depth required
to demonstrate that an op was reasoned about. The discipline scales to
match the blast radius rather than applying a uniform 5-field tax.

---

## 3. Rule-shape decision (positive + negative dual system)

Per `core/memory/global/agent_feedback.md` § *Rule shape — positive vs.
negative system must be a conscious choice*, this proposal names its
rule-shape choices explicitly:

| Tier | Rule shape | Default if ambiguous |
|------|------------|----------------------|
| **Tier 1** (rationale + operator confirm) | **Positive system** — enumerate allowlist of clearly-bounded irreversible ops | Falls to Tier 2 |
| **Tier 2** (full Reasoning Surface — current behavior) | **Default** — everything not matched by Tier 1 or Tier 3 | n/a |
| **Tier 3** (hard reject — denylist) | **Negative system** — enumerate the truly-destructive ops that require operator-out-of-loop authorization | Falls to Tier 2 |

Rationale for the dual-system shape:

- **Tier 1 must be positive-system.** Each new op qualifying for Tier 1 is
  a fresh contextual decision: does this op's blast radius genuinely meet
  the bounded-irreversible criterion, or are we relaxing the gate because
  it feels noisy? Default-allow with an exception list would silently
  recreate the hidden-constraint problem — every new tool/command added to
  the harness would earn Tier 1 by default. **The agent must demonstrate
  why each op qualifies; the kernel does not extend trust by default.**
- **Tier 3 must be negative-system.** The space of "clearly destructive"
  ops is enumerable in a sitting (force-push-to-protected, hard-reset on
  shared-history, history rewrite, schema drop). A positive-system "safe"
  list against the chaotic space of all-possible-Bash would be longer than
  enumerating the dangerous subset.
- **Default Tier 2.** The operator profile's loss-averse posture says:
  when in doubt, more friction. Default-Tier-2 honors that without
  reverting the Tier 1 relaxation.

---

## 4. Tier 1 — micro-surface specification

Tier 1 ops require a **two-field surface** written to
`.episteme/reasoning-surface.json`:

```jsonc
{
  "tier": 1,
  "rationale_one_line": "Pushing event-N-coherence — feature branch, no
    protected-branch impact; revertible by gh pr close + git push origin
    --delete event-N-coherence.",
  "disconfirmation_one_line": "If pytest CI on the PR fails, close the PR
    without merging.",
  "timestamp": "2026-05-23T14:30:00Z"
}
```

Schema (revised Event 134.1 — `branch` field added per operator's
context-bleed counter):

```jsonc
{
  "tier": 1,
  "branch": "event-N-coherence",
  "rationale_one_line": "Pushing event-N-coherence — feature branch, no
    protected-branch impact; revertible by gh pr close + git push origin
    --delete event-N-coherence.",
  "disconfirmation_one_line": "If pytest CI on the PR fails, close the PR
    without merging.",
  "timestamp": "2026-05-23T14:30:00Z"
}
```

| Field | Required | Constraint |
|-------|----------|------------|
| `tier` | yes | Must equal `1` (rejects misuse against Tier 2/3 ops) |
| `branch` | yes | **Event 134.1 — context-bleed counter.** Must equal `git rev-parse --abbrev-ref HEAD` at op-execute time. A surface authored on branch X cannot authorize an op executed on branch Y, even within the TTL window |
| `rationale_one_line` | yes | ≥ 40 chars, must name (a) why blast radius is bounded AND (b) the concrete rollback path |
| `disconfirmation_one_line` | yes | ≥ 20 chars, must name a specific observable outcome that would prove the op was a mistake |
| `timestamp` | yes | ISO-8601 (`Z` or `+00:00` accepted); TTL = 5 minutes |

**Why branch-binding** (operator quote, 2026-05-23): *"a pure 5-minute
temporal window introduces a context-bleeding vulnerability: if the
operator writes a micro-surface for feature branch fix-coherence, an
agent could theoretically execute a different irreversible operation
within that 5-minute window under the same token. The validator must
assert that the current Git branch explicitly matches the branch target
declared inside the micro-surface JSON."*

The two short fields (`rationale_one_line` + `disconfirmation_one_line`)
are **strict subsets** of the four Reasoning-Surface fallback fields
(`knowns` / `unknowns` / `assumptions` / `disconfirmation`). Tier 1's
`rationale_one_line` collapses Knowns+Assumptions; Tier 1's
`disconfirmation_one_line` is the standard Disconfirmation field at
reduced length. **If a Tier 1 op cannot fit its rationale in 40 chars
naming both blast bound and rollback path, the op is not actually Tier 1
— escalate to Tier 2.**

Tier 1 micro-surface is **valid even when the corresponding full
Reasoning Surface is missing or stale.** This is the relaxation. It is
controlled by the classifier's decision that the op qualifies for Tier 1;
it is not a free path the agent can self-elect into.

Validator implementation: `core.practice.irreversible_tier.validate_micro_surface(
surface, git_context, now=None) -> tuple[bool, str]`. Returns
`(True, "ok")` only when every gate passes (tier=1, branch present + matches
current branch, rationale ≥ 40, disconfirmation ≥ 20, timestamp parses +
within TTL + not in future). Any False routes the op to Tier 2
strict-block — no advisory in-between.

---

## 5. Tier classifier specification

A pure function:

```python
def classify(
    tool_name: str,                                  # "Bash" | "Write" | "Edit"
    tool_args: dict,                                 # tool-specific argument bag
    git_context: GitContext,                         # current branch, protected branches
    config: TierConfig | None = None,                # static feature toggles
    operator_profile: OperatorProfile | None = None, # incident-response override (134.1)
) -> ClassifierVerdict:                              # tier + reason + pattern
```

Inputs the classifier inspects:

1. **Normalized command text** (re-uses the existing `_NORMALIZE_SEPARATORS`
   transform from `reasoning_surface_guard.py:208` so bypass shapes like
   `subprocess.run(['git','push'])` trip the same classification as bare
   shell).
2. **Current Git context** — `git rev-parse --abbrev-ref HEAD`, plus the
   protected-branches list from `.episteme/protected_branches.json`
   (defaults to `["main", "master"]`).
3. **Dangerous-flag presence** — `--force`, `-f`, `--force-with-lease`,
   `--hard`, `--no-verify` are flags whose presence escalates a Tier 2 to
   Tier 3 (denylist hit).
4. **Operator-profile override** (Event 134.1) — when
   `operator_profile.risk_tolerance == 0` (incident-response posture),
   every Tier 1 hit is force-escalated to Tier 2 (`pattern` field still
   carries the original Tier-1 label for telemetry). Tier 3 is unchanged
   — the override only tightens, never relaxes.

Initial Tier 1 allowlist (Event 134.1 — shrunk per operator decision;
operator can grow the list as Tier 1 patterns prove safe in lived
behavior):

| Op pattern | Tier 1 condition | Rationale |
|------------|------------------|-----------|
| `git push origin <branch>` | `<branch>` not in protected_branches; no `--force` / `-f` / `--force-with-lease` / `--no-verify` | Feature-branch push is reversible by closing PR + branch delete |
| `gh release create` | `--prerelease` flag present | Prerelease can be deleted; not on PyPI per release-please policy |
| `gh issue create`, `gh issue comment`, `gh issue edit`, `gh pr create`, `gh pr comment`, `gh pr edit` | always | Reversible by edit/delete; no destructive effect on shared state |

**`pip install` was removed from the Tier 1 allowlist** at Event 134.1
per operator's supply-chain rationale: *"In May 2026, supply-chain
attacks (typosquatting, malicious `setup.py` / macro execution during
the installation phase) are highly sophisticated. Running a raw `pip
install` allows arbitrary code execution on the local host before any
code is run. While it is technically revertible via `pip uninstall`,
its immediate execution blast radius is not strictly bounded if the
malicious package attempts to exfiltrate environment variables or keys
from disk."* `pip install` remains in the Tier 2 fallback set (full
Reasoning Surface required); it is not silently allowed.

Tier 3 denylist (additive — these always reject regardless of surface):

| Op pattern | Why Tier 3 |
|------------|-----------|
| `git push --force <remote> <protected-branch>` or `-f` variant | History rewrite on shared branch |
| `git push --force-with-lease <remote> <protected-branch>` | Lease only narrows the race window; rewrite intent is still Tier 3 |
| `git reset --hard <ref>` on a protected branch | History rewrite on shared branch |
| `git branch -D <protected-branch>` or `-d` variant | Branch deletion on shared history |
| `git filter-branch`, `git filter-repo`, `git rebase --root` | History rewrite |
| `DROP DATABASE`, `DROP SCHEMA`, `TRUNCATE TABLE` against non-test schema | Destructive data op |
| Any of the above wrapped in `eval` / `python -c` / `bash -c` indirection | Same op, evasion shape |

Everything not matching Tier 1 or Tier 3 → Tier 2 (current strict-block
behavior preserved).

---

## 6. Integration plan (operator-gated)

This proposal ships a classifier + tests but **does not modify
`core/hooks/reasoning_surface_guard.py`.** The integration is staged:

1. **Stage 0 — landed Event 134 (2026-05-23).** Standalone classifier at
   `core/practice/irreversible_tier.py` (no underscore prefix — public
   module until promoted). Tests at `tests/test_irreversible_tier.py`.
   Existing 1066-test suite preserved + 49 new tests landed → 1115 passed.
2. **Stage 1 — operator review (Event 134.1, 2026-05-23). DONE — APPROVED
   WITH 4 SCOPE SHRINKAGES.** Operator approved the architectural
   blueprint and resolved all four open questions from § 9. Shrinkages
   applied: (a) `pip install` removed from Tier 1 allowlist (supply-chain
   attack class), (b) 5-min TTL retained but now branch-bound (closes
   context-bleed), (c) static classifier retained + `OperatorProfile`
   interface hook added with `risk_tolerance==0` force-Tier-2 override
   implemented (disk loader deferred to Stage 2), (d) Tier 1 telemetry
   isolated to `~/.episteme/telemetry/tier1.jsonl` (separate from EU AI
   Act primary audit trail). Code + tests + this doc updated; 1137
   passed after Event 134.1. **Stage 2 wire-up remains operator-gated.**
3. **Stage 2 — wire as advisory in the live hook. DONE Event 135.** Hook
   gained `_try_tier1_dispatch()` (pre-Layer-1) consulting the classifier
   + `validate_micro_surface()` + `soak_gate_open()`; on all-True emits
   stderr advisory and exits 0, on any False falls through to existing
   strict-block. `load_operator_profile()` reads
   `~/.episteme/derived_knobs.json` with a fallback parse of
   `core/memory/global/operator_profile.md`. Repo root added to sys.path
   so the classifier import resolves under the standalone hook runtime.
   Tests: `tests/test_hook_tier1_dispatch.py` (8 tests).
4. **Stage 3 — soak gate at runtime. CODE LANDED Event 135; lived-behavior
   gate fires automatically.** `soak_gate_open()` reads
   `~/.episteme/telemetry/tier1.jsonl` and returns `(False, reason)`
   until all three thresholds clear: N ≥ 20 records, ≥ 7 calendar days
   span, ≥ 90% rationale-accuracy rate. New installations start with the
   gate CLOSED. Audit surface: `episteme tier1 audit` (human + `--json`
   + `--require-open` for CI gating). Tests:
   `tests/test_irreversible_tier.py::TestSoakGate` (7 tests) +
   `tests/test_tier1_audit_cli.py` (6 tests).
5. **Stage 4 — promote to default. DONE Event 135.** Kernel doc edit:
   `kernel/REASONING_SURFACE.md` gained a § *Tier 1 micro-surface (v1.4.x+)*
   section after the existing four-blueprint enumeration. Manifest
   regenerated: sha256 for REASONING_SURFACE.md updated in
   `kernel/MANIFEST.sha256`. Changelog entry: minor-version Event 135
   line in `kernel/CHANGELOG.md`. Operator's /goal explicitly authorized
   the kernel doc edit per AGENTS.md § "When to stop and ask".
   **Deferred to Stage 4b** (cosmetic, opportunistic): the physical
   file move from `core/practice/irreversible_tier.py` to
   `core/hooks/_irreversible_tier.py` to match the existing
   underscore-prefixed hook-private convention. Behavior is unchanged
   by the move; current import path works in both runtime and test.
6. **Stage 5 — lived-behavior soak clearance.** No agent action.
   Operator uses episteme normally; Tier 1 telemetry accumulates;
   `soak_gate_open()` flips True automatically when thresholds clear;
   live hook begins dispatching Tier 1 ops through the advisory path
   from that point forward. The kernel governs its own promotion timing.

Each stage is reversible: revert the staging commit, the gate returns to
strict-block. The promotion to default in Stage 4 is itself a Tier 2
decision (kernel doc edit requires full Reasoning Surface).

---

## 7. Calibration & failure-mode counter

Three failure modes this proposal must counter:

**FM-A — Tier 1 allowlist creep.** The agent learns that adding an op to
Tier 1 reduces friction, so over time the allowlist grows past the
bounded-blast-radius criterion. *Counter:* every Tier 1 allowlist
extension is itself a Tier 2 decision (full Reasoning Surface required to
edit `core/practice/irreversible_tier.py`'s allowlist). The kernel
governs its own classifier.

**FM-B — Rationale rot.** Agent emits a generic rationale ("safe op,
revertible") that passes the 40-char minimum but says nothing the gate
could not have inferred without the surface. *Counter:* rationale must
name (a) a specific reason blast radius is bounded for *this* op AND (b)
the *concrete* rollback command. The validator (`_layer3_ground_blueprint_fields`-style
grounding, scaled to the micro-surface) checks for evidence markers —
branch name, command name, target — and rejects rationales that are
context-free templates.

**FM-C — Tier mis-classification.** Classifier returns Tier 1 for an op
that turns out to be Tier 2 in lived behavior. *Counter:* every Tier 1
proceed is logged with `correlation_id` to
`~/.episteme/telemetry/tier1.jsonl` (Event 134.1 — isolated from the
primary calibration trail at `~/.episteme/telemetry/YYYY-MM-DD-audit.jsonl`
per operator decision to keep FM-B rationale-rot tracking + error-rate
analysis decontaminated from the EU AI Act primary audit log). PostToolUse
hook captures outcome (exit_code, follow-up reverts within 24h). Audit
threshold: any Tier 1 op that triggers a subsequent rollback within 24h
promotes the op pattern to Tier 2 in the next classifier release.

---

## 8. What this proposal explicitly does NOT do

- **Does not modify `kernel/REASONING_SURFACE.md`.** Kernel docs are own
  Event per `AGENTS.md` § "When to stop and ask". Stage 4 will edit the
  kernel doc; until then, the kernel doc is the source of truth and this
  proposal is staged-but-not-promoted.
- **Does not bypass Claude Code's permission popup.** Tier 1 lowers the
  Reasoning Surface fill cost; the operator's per-tool confirmation
  remains the human-in-loop gate.
- **Does not auto-allow any pattern across sessions.** Each Tier 1
  proceed requires a fresh micro-surface (5-min TTL) and an operator
  confirm.
- **Does not extend to Tool calls other than Bash/Write/Edit.** Future
  agents may run other tools (cloud-API MCPs, etc.); those need their
  own tier analysis before being added.
- **Does not relax `loss-averse` posture as a global default.** The
  posture remains; this proposal refines the *implementation* of the
  posture from "uniform 5-field tax" to "tax proportional to blast
  radius."

---

## 9. Open questions — RESOLVED Event 134.1 (2026-05-23)

All four resolved by operator. Resolutions in place in code + tests +
proposal as of this revision. Decisions and operator-stated reasoning
recorded below for audit.

1. **Is the initial Tier 1 allowlist tight enough? Should `pip install`
   qualify?** **RESOLVED — SHRINK. `pip install` removed from Tier 1.**
   Operator: *"In May 2026, supply-chain attacks (typosquatting,
   malicious setup.py/macro execution during the installation phase)
   are highly sophisticated. Running a raw pip install allows arbitrary
   code execution on the local host before any code is run. While it
   is technically revertible via pip uninstall, its immediate execution
   blast radius is not strictly bounded if the malicious package
   attempts to exfiltrate environment variables or keys from disk.
   Let's keep the initial Tier 1 testing restricted to pure Git/GitHub
   metadata operations (git push on feature branches, gh
   issue/comment)."*
2. **Should the Tier 1 TTL be 5 min, or per-op (one-shot)?** **RESOLVED
   — 5-min TTL with branch-binding extension.** Operator: *"One-shot
   execution is too punishing for standard loops (e.g., pushing a feature
   branch, hitting an upstream reject, rebasing, and pushing again).
   However, a pure 5-minute temporal window introduces a context-bleeding
   vulnerability: if the operator writes a micro-surface for feature
   branch fix-coherence, an agent could theoretically execute a different
   irreversible operation within that 5-minute window under the same
   token. The validator must assert that the current Git branch
   explicitly matches the branch target declared inside the micro-surface
   JSON."* See § 4 for the revised schema with the `branch` field.
3. **Should classifier respect operator-profile knobs?** **RESOLVED —
   YES, with static Stage 0 implementation + Stage 2 disk-loader
   deferral.** Operator: *"If `risk_tolerance == 0` (e.g., during a
   production incident response window), the system should automatically
   bypass Tier 1 logic and force-escalate all operations to Tier 2
   strict-blocking. For this event, we will write the static classifier
   structure but leave an explicit interface hook for OperatorProfile
   injection in Stage 2."* `OperatorProfile` dataclass + `classify()`
   parameter + force-Tier-2 override landed in Event 134.1; the
   disk-loader (reading `~/.episteme/derived_knobs.json` or
   `core/memory/global/operator_profile.md`) is Stage 2 work.
4. **Where should the Tier 1 audit live? Same file as existing
   telemetry, or separate?** **RESOLVED — ISOLATE to a separate file.**
   Operator: *"During the Stage 3 soak period, our primary objective is
   tracking Rationale Rot (FM-B) and calculating the true error
   propagation rate. Keeping this data isolated makes parsing the
   experimental telemetry clean and straightforward, without
   contaminating the high-fidelity primary audit trail used for EU AI
   Act compliance."* Tier 1 outcomes write to
   `~/.episteme/telemetry/tier1.jsonl` (constant
   `TIER1_TELEMETRY_PATH` exported from the classifier module). The
   existing `~/.episteme/telemetry/YYYY-MM-DD-audit.jsonl` remains the
   primary audit trail for Tier 2/3 ops, untouched by Event 134.1.

---

## 10. Verification

`pytest -q` after Event 134.1 lands:
- Existing 1066 tests preserved (no changes to live code paths).
- 71 tests at `tests/test_irreversible_tier.py` covering: Tier 3
  denylist (13 tests), Tier 1 allowlist (14 tests after the pip-install
  demotion), Tier 2 default (8 tests), normalization bypass shapes
  (4 tests), protected-branches config loader (6 tests), tier
  precedence (2 tests), micro-surface validator with branch-binding +
  TTL + length minimums + clock-skew (16 tests, including the
  context-bleed branch-mismatch counter), profile-aware classifier
  (7 tests, including the risk_tolerance==0 force-escalation across
  every Tier 1 pattern + verification that Tier 3 is unchanged by the
  override).
- Total: **1170 passed, 54 subtests** (= 1066 baseline + 71 Event-134/134.1 + 33 Event-135 new).

The proposal is reversible: `rm docs/PROPOSAL_TIERED_IRREVERSIBLE_GATE.md
core/practice/irreversible_tier.py tests/test_irreversible_tier.py`
returns the repo to its pre-Event-134 state. The live hook is untouched
throughout Events 134 + 134.1.

---

## Attribution

- **Tiered-discipline-by-blast-radius** is Boyd's OODA tempo applied to
  governance overhead: the loop's speed should match the action's
  reversibility, not be uniform across all actions.
- **Positive + negative dual system** is the operator-authored rule from
  `core/memory/global/agent_feedback.md` § *Rule shape — positive vs.
  negative system must be a conscious choice* (2026-04-23, established
  across Events 27/29/31).
- **Asymmetric loss-aversion preserved on high-blast-radius** follows
  Munger's margin-of-safety: the buffer is where it costs the most to be
  wrong, not uniformly across decisions.
- **Calibration soak before promotion** follows Tetlock's calibration-as-coverage
  discipline operationalized in `kernel/CALIBRATION_TELEMETRY.md`.
