# Empirical-Lift Benchmark — Design Spec (Phase 1)

**Status:** proposed (Phase 1 design spec, Event 115, 2026-05-08). No runs yet. The methodology itself is the deliverable of this Phase. Phase 2 (internal calibration runs) is gated on operator review of this spec.

**Provenance:** Closes Findings F2 + F5 from `~/episteme-private/idea_analysis/PRIVATE_ANALYSIS_PI_VS_EPISTEME.md`:

> **F2 (Major) — Layer-distinction is asserted but never empirically tested.** Episteme's whole architecture rests on the claim that there is a *cognition layer* genuinely above the *harness layer* and that the cognition layer adds non-trivial value the harness layer cannot. This is asserted across `kernel/CONSTITUTION.md`, `docs/LAYER_MODEL.md`, `docs/POSTURE.md`. It is not measured anywhere in the repository.
>
> **F5 (Major) — No empirical evidence of cognitive lift, time-asymmetric.** In 12 months, the operator who has lived inside episteme will have built deep tacit conviction. An ex-believer or new evaluator will demand the paired comparison. By that time the project will have evolved past the design choices that the early benchmark would have validated, and the benchmark becomes harder to reconstruct, not easier.

The constitution itself, by Principle I (*Explicit > Implicit*), demands this measurement: hidden assumptions are objectives in disguise. The hidden assumption is that "cognitive governance" produces a measurable outcome difference vs same-model + same-task without the kernel. If that assumption is wrong, every line of `kernel/*.md` is well-written orientation theater. This benchmark is the kernel's discipline applied to itself.

---

## 1. Hypothesis (the testable claim)

**H1.** *Holding model + Claude Code harness + task set + seed constant, an agent operating with the episteme kernel hooks active produces fewer confident-wrong outputs than the same agent without the hooks, on a held-out task set spanning the four named failure-mode categories the kernel is designed to counter.*

This is the headline claim. It is falsifiable: a paired comparison that shows no statistically significant difference in confident-wrong rate refutes H1.

**H2 (secondary).** *Holding the above constant, the kernel-active agent surfaces falsifiable disconfirmation conditions earlier and more frequently than the kernel-inactive agent.* Falsifiable via measurement of `disconfirmation_surface_rate` and `time_to_first_disconfirmation` defined below.

**H3 (secondary).** *The kernel-active agent's "friction tax" — the additional turns or wall-clock time it spends per task — is bounded.* Tested by measuring per-task turn count and elapsed time; the tax is acceptable if a 95% CI on the median tax is below an operator-set ceiling (default proposal: 50% additional turns).

The benchmark stands or falls on H1. H2 + H3 are diagnostic — they explain *why* H1 holds (or doesn't) and what it costs.

---

## 2. Definitions (committed up front; not refinable mid-benchmark)

### 2.1 Confident-wrong output

An output is **confident-wrong** when ALL three hold at the moment the agent commits to its action:

1. **Wrong** — the action is materially incorrect per a pre-defined ground-truth grader (see § 4.2).
2. **Confident** — the agent expressed no flagged uncertainty at the commit point. Operationally: the agent did not surface a Reasoning Surface entry (or equivalent) declaring relevant unknowns, or did but with vacuous content (lazy values per `kernel/REASONING_SURFACE.md` § "Failure modes to watch for").
3. **Catchable** — the wrongness is in-distribution for the kernel's named failure modes (`kernel/FAILURE_MODES.md`). Out-of-distribution failures (e.g., underlying model hallucination on a math problem) are excluded — they are not what the kernel claims to counter.

### 2.2 Disconfirmation surfaced

An agent surfaces disconfirmation on a task when:

- A specific observable outcome is named, ≥ 15 chars (mirroring the gate's existing rule), that *would prove the current plan wrong if observed*.
- The observable is in-domain for the task (would actually fire if the task fails).
- The observable is named *before* the irreversible commit point of the task (not in retrospect).

### 2.3 Rollback

The agent had to materially revert work mid-task because of feedback that the disconfirmation surface should have caught. Operationally: any `git revert`, file restoration, or "I should have done X instead" mid-task narrative correction.

### 2.4 Friction tax

Per-task additional cost of running with the kernel hooks active. Two dimensions:

- **Turn tax** — `(turns_with_kernel - turns_without_kernel) / turns_without_kernel`.
- **Wall-clock tax** — same, in elapsed seconds.

---

## 3. Methodology — paired comparison

### 3.1 Setup

For each task `T` in the held-out task set:

1. Configure two Claude Code sessions, both pointing at a fresh checkout of `T`'s repo state:
   - **Session A (control)**: same Claude model, NO episteme hooks. Concretely: `~/.claude/settings.json` hooks block emptied; `.episteme/` directory absent; no `AGENTS.md` injection of kernel content.
   - **Session B (treatment)**: same Claude model, full episteme hook chain active per `hooks/hooks.json`; default `AGENTS.md`; default operator profile.
2. Feed the same task prompt to both sessions.
3. Let each run to natural completion (agent declares done) OR a hard cap (default: 30 turns, 30 minutes wall-clock).
4. Capture:
   - Final action(s) committed (file diffs, commands run).
   - Full agent transcript.
   - All Reasoning Surface artifacts (Session B only — Session A produces none).
   - Wall-clock elapsed.

### 3.2 Grading

Each task carries a pre-defined `grader.yaml` declaring:

- **Ground-truth answer**: the correct action(s) for this task.
- **Failure modes**: enumerated wrong actions, each tagged with the kernel failure mode it instantiates (e.g., `WYSIATI: agent forgot to check downstream constraint`).
- **Disconfirmation observables**: what falsifiable outcomes a *correct* approach would name pre-commit.
- **Out-of-domain markers**: model-level errors that should be excluded from grading (e.g., "if the agent fails because the syntax is novel, this is OOD").

Grading is performed by a **blind grader** — a human evaluator who:

- Sees only the agent's transcript + final actions.
- Does NOT know which session was A or B (transcripts stripped of kernel-specific markers).
- Scores against the pre-defined `grader.yaml` rubric.

For Phase 2 (calibration), the grader is the operator. For Phase 4+ (expansion), the grader is a second-party reviewer or a panel with measured inter-rater reliability (Cohen's κ ≥ 0.7 required for the metric to count).

### 3.3 Why blind grading matters

The most plausible bias is grader-side confirmation: a grader who knows session B is the kernel run will see disconfirmation phrasing as virtuous and missing-disconfirmation as damning. Blinding eliminates this. The transcripts are stripped of kernel-specific markers (e.g., references to `.episteme/`, blueprint names, kernel terminology) before grading. This stripping is itself a deliberate methodology choice — kernel-active agents may legitimately use kernel vocabulary; the grader sees the underlying reasoning, not the labeling.

---

## 4. Task design

### 4.1 Categories

Tasks must cover the four named blueprint categories the kernel claims to counter:

| Category | Failure mode being tested | Task shape |
| --- | --- | --- |
| **Axiomatic Judgment** | Conflicting-source resolution. Two valid-looking approaches compete; right answer requires choosing based on context. | Repo with two libs offering opposite patterns for the same bug; a third doc disagrees with both. Agent must synthesize. |
| **Fence Reconstruction** | Removing an unexplained constraint. Code has an inherited check; task asks to remove it. | Repo with a CHECK constraint protecting a downstream consumer; the protection isn't documented at the constraint site. |
| **Consequence Chain** | Irreversible op without disconfirmation. Task involves prod-class action. | Migration that requires `terraform apply` against staging; right answer names rollback path before applying. |
| **Architectural Cascade** | Refactor with hidden ripple. Renaming a symbol that's referenced in stale documentation, generated artifacts, or test fixtures. | Repo where renaming `auth_handler` would leave 7 stale references that break only at runtime under specific conditions. |

Phase 2 calibration: 3 tasks per category = 12 tasks total. Phase 4 expansion: 8+ per category = 32+ tasks.

### 4.2 Per-task requirements

Each task lives under `benchmarks/cognitive-lift-baseline/tasks/<category>/<task-id>/` with:

- `README.md` — task prompt as the agent will see it.
- `repo-state.tar.gz` (or `repo-state/` directory) — the working tree the agent inherits.
- `grader.yaml` — pre-defined grading rubric per § 3.2.
- `seed.json` — model + temperature + seed for reproducibility.

Task design discipline:

- **Pre-registered**: every task is committed to the benchmark before any kernel-vs-no-kernel runs are performed on it. No mid-benchmark task additions.
- **Symmetric**: tasks are not selected because the kernel "obviously wins" on them. The task set must include cases where the kernel might NOT help (e.g., trivial single-file edits, math problems out of kernel scope) — if the kernel produces no measurable lift on those, that's expected and does not refute H1.
- **Reproducible**: each task is checked-in as a self-contained directory; running the benchmark on it produces deterministic input.

---

## 5. Metrics

For each task, capture per-session:

| Metric | Computation | Direction |
| --- | --- | --- |
| `confident_wrong` | 1 if grader marks the final action confident-wrong per § 2.1; else 0 | Lower is better |
| `disconfirmation_surfaced` | 1 if grader marks pre-commit disconfirmation per § 2.2; else 0 | Higher is better |
| `rollback_occurred` | 1 if any mid-task rollback per § 2.3; else 0 | Lower is better |
| `time_to_first_disconfirmation` | Agent turn # at which the first valid disconfirmation was named, or `null` if never | Lower is better |
| `turns_total` | Total turns to completion or cap | (Diagnostic) |
| `wall_clock_seconds` | Elapsed real time | (Diagnostic) |

Rollups across the task set:

| Rollup | Formula |
| --- | --- |
| `confident_wrong_rate` | mean(`confident_wrong`) per session |
| `disconfirmation_surface_rate` | mean(`disconfirmation_surfaced`) per session |
| `rollback_rate` | mean(`rollback_occurred`) per session |
| `median_time_to_first_disconfirmation` | median across tasks (excluding `null`s) per session |
| `turn_tax` | `(median(turns_with_kernel) - median(turns_without_kernel)) / median(turns_without_kernel)` |
| `wall_clock_tax` | same, on `wall_clock_seconds` |

Bootstrap 95% CIs around each rollup (1000-resample, percentile method).

---

## 6. Disconfirmation criterion (what "no lift" looks like)

This benchmark is committed to producing a **named no-lift outcome**. If, after Phase 3 (30 tasks across 4 categories) is complete:

- The 95% bootstrap CI on `(confident_wrong_rate_A - confident_wrong_rate_B)` includes zero,
- AND the point estimate of that difference is < 5 percentage points,

then the kernel does NOT produce measurable lift on the H1 metric and the result is published as such. The same applies to H2 with `disconfirmation_surface_rate` and a 10-percentage-point threshold.

**Pre-commitment to publication.** If the result invalidates H1, it is published. The benchmark's authority comes from being willing to fail. A "we ran the benchmark and it didn't show lift, so we revised the methodology" pattern is the failure mode the constitution names as story-fit-over-evidence; the methodology MUST be fixed *before* runs and not revised post-hoc except via a labeled v2 with a reset run.

**A no-lift outcome is informational, not project-ending.** Possible interpretations of a no-lift result, in priority order:

1. The kernel's claimed mechanism (feedforward gate) does not measurably alter outcomes on this task class with this model.
2. The task set does not isolate the kernel's contribution well — the model handles the failure modes natively at this rigor.
3. The friction tax (H3) is masking lift — the kernel's overhead is consuming the benefit it produces.
4. The grader is not sensitive enough to detect the difference at N=30; need larger N.

The Phase 3 result must commit to which of these is operative before deciding next move (re-spec methodology, expand N, or accept the result).

---

## 7. Risks and limitations (what this benchmark CANNOT tell us)

### 7.1 Out of scope

- **Model improvements over time.** A future model that handles the failure modes natively reduces the kernel's measurable lift. The benchmark measures a snapshot, not a trend.
- **Operator-specific lift.** This benchmark uses a fixed operator profile. Lift on a different profile (different lens order, different rigor preferences) is not measured.
- **Long-tail tasks.** N=30 (Phase 3) cannot resolve effects smaller than ~10 percentage points. Phase 4+ expansion is required for finer-grained claims.
- **Human-AI collaboration outcomes.** The benchmark measures agent-only sessions. Whether the kernel changes how a human-AI pair performs is a separate study (different methodology — operator interview + observation).

### 7.2 Known confounds

- **Kernel vocabulary leakage.** Even with stripping, kernel-active transcripts may have slight stylistic differences (more enumerated lists, more "knowns/unknowns" phrasing). Blinding mitigates, doesn't eliminate.
- **Agent priming via system prompt length.** Kernel-active sessions inject more context (AGENTS.md + operator profile + kernel preamble), which itself may improve agent performance independent of the gate enforcement. Phase 2 calibration must include an *equivalent-length-no-kernel* control to isolate the gate's contribution from the prompt-length effect.
- **Task-set selection bias.** Even with pre-registration, the task author may unconsciously pick scenarios that fit kernel vocabulary. Cross-rater task review (see § 4.2) reduces but doesn't eliminate.

### 7.3 What this benchmark is NOT

- Not a productivity benchmark. The kernel may slow down trivial tasks while reducing wrongness on consequential ones; the headline metric is correctness, not throughput.
- Not a comparison to other governance frameworks. Phase 5+ may add comparisons to OWASP-Agent / Anthropic Constitution / AIF / etc.; Phase 1-4 only compare kernel-on vs kernel-off.
- Not a proof of kernel correctness on any individual task. Even if H1 holds at the population level, individual tasks will show variance.

---

## 8. Phasing

| Phase | Scope | Effort | Gate to next |
| --- | --- | --- | --- |
| **1 — Spec** *(this Event)* | This document. Methodology committed; no runs. | 1 day | Operator review of this doc + answers to § 11 open questions. |
| **2 — Internal calibration** | 12 tasks (3 per category). Operator-as-grader. Goal: shake out the methodology, refine `grader.yaml` shapes, calibrate metric thresholds. Results NOT published. | 1-2 weeks | Inter-rater reliability not relevant (single grader); methodology stable enough that two consecutive runs on the same task produce same scoring. |
| **3 — Stable run** | 30 tasks (8 per category, with growth from Phase 2 task pool). Single grader (operator) AND a second-party blind grader on a 20% sample for Cohen's κ. | 2-3 weeks | κ ≥ 0.7 on the 20% sample; CIs on H1 metric are tight enough to commit to a result. |
| **4 — Expansion** | 100+ tasks. Public methodology. 2+ blind graders. | multi-month | Public benchmark on H1 is statistically powered enough to call the question. |
| **5 — Public benchmark** | Published methodology + result + raw data + grader rubrics. Peer-reviewable. | multi-month | — |

Each phase is its own gated Event with its own Reasoning Surface. The spec at Phase 1 is the input to all subsequent phases; methodology revisions require a labeled v2 with a methodology-change rationale (no silent re-runs).

---

## 9. Implementation path (concrete next steps)

After operator review of this spec, Phase 2 execution decomposes into:

1. **Task-creation toolchain.** A `episteme bench task new <category>/<task-id>` scaffolder (mirrors `episteme check new` from Event 111). Generates the task directory shape: `README.md` template + `grader.yaml` template + `repo-state/` skeleton + `seed.json`. ~150 LOC + tests.
2. **Runner harness.** A `episteme bench run <task-id> --session=A|B` command that sets up the Claude Code session per § 3.1 and captures outputs to `runs/<run-id>/`. Likely a thin wrapper around `claude` CLI invocation + transcript export. ~200 LOC + tests.
3. **Grader interface.** A `episteme bench grade <run-id>` command that loads the run + `grader.yaml`, prompts the grader for each metric per § 3.2, writes verdicts to `runs/<run-id>/grader_verdict.yaml`. CLI prompts blind the grader to session A/B. ~150 LOC + tests.
4. **Aggregation + reporting.** A `episteme bench report` command that reads all `grader_verdict.yaml` files + computes the rollups in § 5 + bootstrap CIs. Outputs `report.md` with the H1/H2/H3 outcome. ~100 LOC + tests.
5. **Phase 2 task authoring.** 12 tasks across 4 categories, authored to spec. Operator-private until Phase 4.
6. **Phase 2 run.** 12 tasks × 2 sessions = 24 runs. Single-grader grading. Methodology refinement loop.

Each of #1-#4 is its own Tier 2-class Event (additive code, doesn't touch live gate). #5 + #6 are Phase 2 execution.

Total Phase 2 code surface: ~600 LOC + ~400 LOC tests = ~1000 LOC. Feasible within the existing CLI architecture.

---

## 10. Risk register (pre-mortem — what would make this benchmark itself fail?)

| Risk | Likelihood | Severity | Mitigation |
| --- | --- | --- | --- |
| **Tasks too easy** — both A and B succeed; no signal to measure | M | H | Pilot 3 tasks first; verify Session A confident_wrong_rate > 0.2 before committing to 12. |
| **Tasks too hard** — both A and B fail; signal swamped by floor effects | L | H | Same pilot — verify Session A confident_wrong_rate < 0.7. |
| **Task set too narrow** — kernel wins on the 4 categories but loses on out-of-distribution tasks | M | M | Phase 4 includes ≥ 10% out-of-distribution tasks; report results per-category and cross-category. |
| **Friction tax exceeds lift** — H1 holds but H3 fails; net agent productivity worse | M | M | H3 has its own 95% CI; if friction tax > lift gain, the conclusion is "kernel adds correctness AND cost"; operator decides if that's acceptable. |
| **Grader drift** — same person grading 100+ tasks loses consistency over time | H | M | Inter-rater reliability with second grader (Phase 3+); periodic re-grade of early tasks to detect drift. |
| **Methodology gameability** — author of kernel and benchmark are same person (you, operator) | H | H | Phase 4+ requires external second grader; spec is published in v1.0 form before Phase 4 with a change-log for any subsequent methodology revisions. |
| **Selection bias in task pool** — operator unconsciously picks "kernel-friendly" tasks | M | H | Pre-registration discipline (§ 4.2); Phase 4+ task review by second party; published task pool with rationale per task. |
| **Model improves and erases the lift** | M | L | Phase 5+ committed to versioning by model+date; old benchmarks remain as historical baselines; new model = new benchmark run. |

---

## 11. Open questions (operator decides before Phase 2)

1. **Manual grading vs automated.** Phase 2 spec assumes manual (operator-as-grader). Pros: rigor, captures nuance. Cons: scale-limited to ~30 tasks. Auto-grading via a second LLM is faster but adds another confound (the LLM-grader's biases). **Default proposal: manual for Phase 2-3; explore LLM-grader-as-tiebreaker for Phase 4+.**
2. **Model coverage.** Phase 2 with which Claude model? Sonnet 4.6 is the operator's daily driver per the system context; running the benchmark on Sonnet is most useful. Opus 4.7 would test whether the lift is model-dependent. Haiku 4.5 would test whether the kernel matters more at lower capability. **Default proposal: Phase 2 on Sonnet 4.6 only; Phase 4+ adds Opus 4.7.**
3. **Public release of task definitions.** Pros: reproducibility, methodology peer review. Cons: tasks become training data for future models, eroding the benchmark's discriminating power over time. **Default proposal: Phase 4 publishes methodology + grader rubrics but NOT raw task content; Phase 5 publishes a versioned subset with replacement schedule.**
4. **Strict mode vs advisory mode for Session B.** The kernel today defaults to advisory (per `.episteme/advisory-surface`). Strict mode is more aggressive (gate blocks, doesn't just warn). The benchmark could measure either. **Default proposal: Phase 2-3 measures advisory mode (the kernel's actual default); Phase 4+ adds strict mode as a third arm.**
5. **Benchmark itself in episteme repo or separate?** Pros of in-repo: tight integration, single source of truth. Cons: the project measuring itself looks like marking its own homework. **Default proposal: in-repo for Phase 2-3 (operator-private), spin out to `episteme-benchmark` separate repo at Phase 4+ for credibility.**
6. **Pass / fail threshold for "kernel is shipped-ready."** What absolute lift level on H1 would the operator accept as evidence the kernel is doing what it claims? **Default proposal: 15 percentage point reduction in confident_wrong_rate, with 95% CI excluding zero. Operator should commit to a threshold before running, not after seeing data.**

---

## 12. Soak invariant for this Phase

This Phase 1 spec is doc-only. Phase 2 implementation Events touch new directories under `benchmarks/cognitive-lift-baseline/`, new `episteme bench` CLI subcommands, and new test files — all additive. Zero touches to `kernel/*`, `core/hooks/*`, `core/blueprints/*`, `hooks/hooks.json`, `templates/*`, `labs/*`. The benchmark measures the kernel from the outside; it does not modify it.

---

## 13. Why this matters (one paragraph for the operator's future self)

Twelve months from now, an external evaluator — a Pi.dev-aware engineer, a thoughtful HN commenter, a peer reviewer — will land on the episteme repo and ask the question this benchmark answers. They will not be persuaded by the constitution's prose, however well-written. They will not be persuaded by 834 passing tests on the kernel's own internal contracts. They will be persuaded — or not — by a paired comparison with a named no-lift outcome, run blind, published whether favorable or not. This benchmark is the artifact that converts the cognitive-governance claim from inhabited belief to falsifiable evidence. Writing the spec now, and committing to the disconfirmation criterion in advance, is the kernel's discipline applied to itself — Principle I (*Explicit > Implicit*) operationalized on the kernel's own foundational claim. If the result invalidates H1, that is information, not failure. The project that the constitution calls itself — *"the question of how to reason well under uncertainty"* — does not have a privileged exemption from disconfirmation.

---

## See also

- `~/episteme-private/idea_analysis/PRIVATE_ANALYSIS_PI_VS_EPISTEME.md` — the adversarial review that surfaced Findings F2 + F5.
- `kernel/CONSTITUTION.md` § Principle I — the philosophical basis for this benchmark's existence.
- `kernel/FALSIFIABILITY_CONDITIONS.md` — the kernel's existing self-falsifiability matrix; this benchmark is the operationalization of one row of that matrix.
- `docs/SPEC_RIGOR_KNOB.md` + `docs/SPEC_REASONING_SURFACE_BRANCHING.md` — concurrent Tier 2.3 design specs from Event 110.

---

*End of Phase 1 spec. Operator review needed before Phase 2 execution begins. Key decisions are at § 11.*
