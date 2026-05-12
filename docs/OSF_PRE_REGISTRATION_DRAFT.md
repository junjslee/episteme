# OSF Pre-Registration — DRAFT (Phase 2 Calibration-Lift Trial)

**Status:** DRAFT — not submitted to OSF.
**Purpose:** make the Phase 2 trial design publicly committable before data is collected, so the load-bearing empirical claim ("episteme reduces operator Confident Failure Rate on irreversible decisions") can be pre-registered rather than post-rationalized.
**Operator action required to submit:** decide on OSF (default) vs AsPredicted (alternative); then submit. Submission is the irreversible step — once registered, the trial design is timestamped and immutable to amendments-only.

---

## 1. Title

**Architectural Constraint at the Operator Decision Layer Reduces Confident Failure Rate on Irreversible AI-Assisted Decisions: A Within-Subject Crossover Trial**

## 2. Authors

[Operator name and affiliation]. ORCID: [TBD].

## 3. Hypotheses

### Primary

- **H₀ (null):** $CFR_{treatment} \geq CFR_{control}$ — the operator-authored, cryptographically signed Reasoning Surface (the episteme intervention) does not reduce Confident Failure Rate relative to a no-intervention baseline.
- **H₁ (alternative):** $CFR_{treatment} < CFR_{control}$ — the intervention reduces CFR on irreversible decisions.

### Construct definition

A **Confident Failure** is a decision episode in which all three hold:

1. The operator commits to action $a$ in the irreversible-class action set $A_{irr}$.
2. The operator's elicited subjective probability that $a$ is correct, $c_{op} \geq \tau_{conf}$ (default $\tau_{conf} = 0.70$, calibrated to MIRROR's convention).
3. The panel-adjudicated post-hoc verdict is $g(a) =$ "should have stopped/audited."

$$CFR_k = \frac{|\{e \in \text{Episodes}_k : \text{decision}(e) = \text{proceed} \land c_{op}(e) \geq \tau_{conf} \land g(\text{action}(e)) = \text{should\_have\_stopped}\}|}{|\{e \in \text{Episodes}_k : \text{decision}(e) = \text{proceed} \land c_{op}(e) \geq \tau_{conf}\}|}$$

where $k \in \{\text{control}, \text{treatment}\}$.

### Empirical anchor

The intervention is designed to replicate at deployment scale the effect documented by the [MIRROR benchmark (arXiv 2604.19809)](https://arxiv.org/abs/2604.19809): external architectural constraint reduces LLM Confident Failure Rate from 0.600 to 0.143 (76% reduction at temperature 0; mean 70% at temperature 0.7 across 5 frontier models). The MIRROR paper's load-bearing finding: *"Providing models with their own calibration scores produces no significant improvement (p > 0.05); only architectural constraint is effective."*

Whether the deployment-scale effect with humans + episteme matches the benchmark-scale effect with LLMs alone is the empirical question this trial answers.

## 4. Study design

- **Design:** within-subject crossover (each operator experiences both conditions)
- **Counterbalancing:** half of operators start in Control, half in Treatment; switch on Day 3 after a 24-hour washout
- **Blinding:** post-hoc panel adjudication is blinded to condition
- **Cohort:** 12 operators total — Cohort A (n=6) episteme-fluent; Cohort B (n=6) episteme-naive ≥ 5 yr engineering
- **Tasks:** 50 hand-crafted Operator-Irreversible Decision Tasks across 5 trap classes (10 each): hidden-conflict destructive op, context-poisoning, fence-removal trap, self-conditioning cascade, confident-wrongness regex/edge-case. Tasks are frozen at SHA-256 manifest committed pre-registration.
- **Block randomization:** Latin-square within each cohort; 25 tasks per block per condition

### Conditions

| Arm | Description |
|---|---|
| **Control** | Claude Code with default auto-memory enabled; standard system prompt; built-in skills available; pre-tool-use shows standard confirmation dialog but no structured surface required |
| **Treatment** | Same Claude Code + auto-memory baseline; episteme plugin active; HMAC/Ed25519 keypair present; pre-tool-use hooks enforce the signed-surface@1.0 gate; operator must `episteme surface author` before each irreversible-class decision |

The only manipulated variable is the forcing function. Same model, same memory, same skills.

## 5. Power analysis

| Assumption | Value | Source |
|---|---|---|
| Expected $CFR_{control}$ | 0.30 | Conservative downward adjustment from MIRROR's 0.60 — agent-mediated decisions are easier than pure introspection tasks |
| Target detectable effect | 50% relative reduction → $CFR_{treatment} = 0.15$ | Half of MIRROR's 76% effect, defensible against ceiling claims |
| α (one-sided) | 0.05 | |
| Power | 0.80 | |
| Design | Within-subject crossover, paired | |
| **Required N (decision episodes per arm)** | **≈ 120** | Two-proportion test, paired |
| Operators × tasks | 12 × 25 per arm | 300 episodes per arm with 2.5× headroom for attrition |

## 6. Secondary metrics

| Metric | Definition | Pre-registered analysis |
|---|---|---|
| **Stop Rate** $SR_k$ | $|stop \cup audit| / N_k$ | Bonferroni-corrected α=0.0125 |
| **Useful Stop Rate** $USR_k$ | $|stop \cap g = $ should-have-stopped$| / |stop|$ | Bonferroni-corrected α=0.0125 |
| **Expected Calibration Error** $ECE_k$ | ECE over 10 confidence bins on confidence vs ground truth | Bonferroni-corrected α=0.0125 |
| **Time to decision** $t_k$ | Wall-clock from task surface to decision commit | Bonferroni-corrected α=0.0125 |

## 7. Pre-registered analysis (frozen at submission)

1. SPRT stopping boundaries: futility at LLR ≤ -2.94, efficacy at LLR ≥ +2.94, adverse halt at ΔCFR < -10%.
2. Primary analysis: paired two-proportion z-test on $CFR_{control}$ vs $CFR_{treatment}$, one-sided $\alpha = 0.05$.
3. Per-cohort analysis: same test on Cohort A and Cohort B separately. Promotion to commercial outcomes requires both cohorts to pass.
4. Effect-size: Cohen's h with 95% CI.
5. Calibration plots: reliability diagrams for each arm, ECE reported.
6. The analysis script (R or Python) is committed to the trial repo, signed, and SHA-256 manifested at pre-registration time. Any post-hoc deviation requires a written, signed amendment disclosed in publications.

## 8. Promotion / rollback matrix (pre-registered)

| Outcome | $\Delta CFR$ | Statistical | Decision |
|---|---|---|---|
| Strong success | ≥ 50% relative reduction | p < 0.01, 95% CI lower bound > 25% | Proceed to commercial CCO outreach if Probe 1 returns signal; publish methodology paper |
| Moderate success | 25% – 50% reduction | p < 0.05, CI lower bound > 10% | Publish methodology + dataset; keep as OSS with academic positioning |
| Weak signal | 10% – 25% reduction | p < 0.10 | Treat as null; document honestly; no commercial claim |
| Null | < 10% OR CI crosses zero | p ≥ 0.10 | Sunset commercial ambitions; honest post-mortem |
| Negative effect | ΔCFR < 0 at p < 0.10 | — | Immediate rollback; investigate automation-complacency hypothesis |

## 9. Data and code availability

- Analysis script: GitHub `github.com/junjslee/episteme/blob/master/benchmarks/cognitive-lift-baseline/phase2/analysis.R`
- Task corpus SHA-256 manifest: `benchmarks/cognitive-lift-baseline/phase2/TASKS.manifest`
- Anonymized dataset: published to OSF concurrently with results
- Verifier reference: any third party can verify the cryptographic chain-of-custody using `python -m episteme.verify` (see `docs/HOW_TO_VERIFY_EVIDENCE_PACKET.md`)

## 10. Funding / conflict of interest

- Funding: none for the trial (operator self-funded)
- Conflict of interest: trial author is also the episteme project author. The pre-registration discipline + standalone verifier + open dataset are the structural mitigations against this conflict.

---

## A. Registry choice — OSF vs AsPredicted

**Default: OSF.** OSF (osf.io/registries) accepts engineering / software-discipline pre-registrations; the Sigstore project, the Mozilla Localization team, and other software-research efforts have used it. OSF Registries support amendment-disclosure and DOI assignment.

**Alternative: AsPredicted.** Faster, simpler form; primarily psychology + econ; less common for engineering trials. Smaller community.

**Recommendation:** OSF for the structural fit. If operator prefers AsPredicted (faster, lighter), that's also defensible — both produce a timestamped public commitment.

## B. Submission checklist (operator action)

- [ ] Final author name + affiliation + ORCID
- [ ] Task corpus frozen (50 tasks; SHA-256 manifest committed)
- [ ] Analysis script committed and SHA-256 manifest
- [ ] Threshold matrix (§ 8) reviewed and signed
- [ ] Cohort recruitment plan in place (12 operators identified)
- [ ] Submit to OSF Registries
- [ ] Update operator's private GTM notes with the assigned OSF DOI

This document is the **draft** of what the operator can submit. It is not itself the pre-registration until submitted.
