# Calibration Telemetry

**Operational summary:**
- Defines what episteme **measures** from signed Reasoning Surface outputs to produce calibration evidence.
- Three measurement axes: **Brier score** over `surface.decision.confidence` vs. disconfirmation-resolution outcomes; **calibration curve** binning predicted probabilities against observed frequencies; **base-rate-aware** metrics that prevent a trivially-conservative profile from appearing well-calibrated.
- The measurement surface is the bridge between [`FALSIFIABILITY_CONDITIONS.md`](./FALSIFIABILITY_CONDITIONS.md) (which claims the kernel is falsifiable) and the actual empirical record at `~/.episteme/telemetry/*.jsonl` + `~/.episteme/framework/protocols.jsonl` (which lets that claim be tested).
- Operationalizes the **Tetlock** citation in [`REFERENCES.md`](./REFERENCES.md) — *Superforecasting* names calibration measurement as the discipline that distinguishes lucky guesses from skill, but the kernel previously cited it as borrowed concept without specifying what it actually computes.
- Companion to [`MODEL_PROGRESS_RISK_MODEL.md`](./MODEL_PROGRESS_RISK_MODEL.md): if model-strength saturation closes the substrate-gap claim, the kernel's surviving value is *measurable operator-side calibration improvement*. Without this file, that survival claim is unfalsifiable.

---

The kernel claims its outputs are falsifiable. Falsifiability requires a measurement surface — without one, the claim degrades into "we *could* be measured" and the assertion drifts back into doxa over time.

This document specifies the measurement surface. Implementation lives in `src/episteme/_cognitive_budget.py` (approval-time stream, Event 88), `core/hooks/calibration_telemetry.py` (PostToolUse outcome capture), and `episteme evolve friction` (pairing analyzer). The role of *this file* is to declare *what is measured* so the implementation can be audited against intent rather than against itself.

---

## What is measured

Every signed Reasoning Surface that produces an irreversible-or-high-impact action carries:

| Field | Source | Used for |
|---|---|---|
| `correlation_id` | stamped at PreToolUse admission (`reasoning_surface_guard.py`) | Joins prediction record to outcome record |
| `surface.decision.confidence` *(optional)* | Operator/agent declaration if present | Brier score input — numerator over hits, denominator over forecasts |
| `surface.disconfirmation` | Required field; concrete observable | The condition under which the prediction is judged "wrong" |
| `outcome.exit_code` | PostToolUse capture (`calibration_telemetry.py`) | Coarse pass/fail signal |
| `outcome.observable_triggered` | Operator review verdict (Layer 8 spot-check) | Did the named disconfirmation fire? |
| `decision.posture` | `posture_selected` field (patch / refactor / analysis) | Base-rate slice — patch decisions calibrate against patch base rate, not against the global average |

The `correlation_id` is the pairing key. The kernel does not assume the model knows its own confidence; if `surface.decision.confidence` is absent, the prediction is excluded from Brier-score aggregation and contributes only to coverage metrics (what fraction of decisions even *carry* a falsifiable claim).

---

## Three measurement axes

### 1. Brier score (calibration scalar)

The mean squared error between predicted probability and observed outcome (0 if disconfirmation triggered; 1 if not), averaged across all paired records in a window.

Formally: `BS = (1/N) · Σ (p_i − o_i)²` where `p_i` is the declared confidence and `o_i ∈ {0, 1}` is the observed outcome.

A Brier score of 0 = perfect calibration; 0.25 = uniform-random guessing on binary outcomes; >0.25 = systematically worse than chance.

**What it does NOT tell you.** Brier collapses three things into one number: calibration (does P(predicted=0.7) actually fire 70% of the time?), resolution (does the forecaster discriminate at all between high- and low-probability cases?), and uncertainty (what's the base rate of outcomes in this window?). A forecaster who always says 0.5 on 50/50 outcomes scores 0.25 — same as random — without being either skillful or useless. Use Brier as the **headline scalar**; use the calibration curve to diagnose.

### 2. Calibration curve

Bin predicted confidences (typically 10 bins: 0.0–0.1, 0.1–0.2, …, 0.9–1.0). For each bin, plot the *observed* frequency of disconfirmation-triggered outcomes against the *predicted* probability.

A well-calibrated forecaster's curve lies on the diagonal: when they say 0.7, the event fires 70% of the time. Above the diagonal = under-confident; below = over-confident.

The curve is what the **measurement** actually shows. The Brier scalar is the curve compressed into one number.

**Why episteme cares specifically:** the kernel's whole positioning rests on *the operator's confidence at the decision boundary becoming better-calibrated over time as the Reasoning Surface forces disconfirmation declaration*. If the calibration curve does not improve across windows on the same operator, the kernel's central empirical claim is falsified. See [`FALSIFIABILITY_CONDITIONS.md`](./FALSIFIABILITY_CONDITIONS.md).

### 3. Base-rate-aware metrics

A profile that always declares low confidence on a domain where outcomes are rare can score deceptively well on Brier — the low-confidence-low-outcome predictions are mostly correct. This is the Goodhart-drift class of failure (Mode 8 in [`FAILURE_MODES.md`](./FAILURE_MODES.md)) projected onto the calibration measurement.

The counter: **slice by posture class and decision class** before computing Brier. Patch-class decisions have one base rate; refactor-class decisions have another; analysis decisions have a third. Per-slice Brier scores prevent global Brier from being gamed by mix shift.

Slice keys (from the Blueprint D schema):
- `posture_selected` ∈ {patch, refactor, analysis}
- `flaw_classification` ∈ {config-gap, core-logic-misalignment, deprecated-dependency, doc-code-drift, other, schema-implementation-drift, stale-artifact, vulnerability}
- `scenario` ∈ {axiomatic-judgment, fence-reconstruction, consequence-chain, cascade-architectural, generic}
- `operator_profile_axis_snapshot` — the axes (process + cognitive-style) the profile was at when the prediction was recorded; lets per-axis-value calibration analysis run

The kernel does not require every prediction to fill every slice key — coverage is a measured quantity. Predictions missing a slice key contribute to the unsliced rollup but not to the sliced analyses.

---

## Coverage as a first-class metric

Brier score on 5 predictions in a 30-day window is noise. A reported Brier number must come with:

- **Coverage** — what fraction of high-impact ops in the window carried a confidence-bearing prediction at all
- **Sample size** — N paired records
- **Window** — the time bounds the aggregate covers
- **Slice breakdown** — at least one per-posture-class breakdown if N >= 30 per slice

A high-coverage low-N report is a sampling issue (too few high-impact ops in the window). A low-coverage report is a discipline issue (operator skipping confidence declaration). Both are recoverable; conflating them is not.

**Refusal to report.** If coverage is below 0.20 (less than one in five high-impact ops carried a confidence-bearing surface) for a given window, the calibration report MUST refuse to emit a Brier scalar — the number would be meaningless. The report emits a coverage-deficient banner instead. This is a Robust Falsifiability requirement: a measurement claim that the underlying data doesn't support is dishonest, and the kernel's positioning rests on not making dishonest measurement claims.

---

## What this is NOT for

- **Not a leaderboard.** Calibration is a profile-internal signal. Cross-operator comparison is structurally invalid (different domains have different base rates; different operators have different distributions of decision classes); the kernel does not aggregate calibration across operators.
- **Not a gate.** Poor calibration does not block work. It surfaces as a Phase-12 audit finding requiring operator re-elicitation of the relevant profile axes (`uncertainty_tolerance`, `decision_cadence`, the axis whose drift the bad calibration correlates with).
- **Not a substitute for outcome review.** Brier score is the *compressed* signal; the operator still owes attention to specific high-impact decisions that triggered disconfirmation. The calibration measurement augments Layer 8 spot-checks; it does not replace them.

---

## Connection to [`FALSIFIABILITY_CONDITIONS.md`](./FALSIFIABILITY_CONDITIONS.md)

The Reasoning Surface contract claims that *disconfirmation in advance* improves calibration over time. That claim is falsifiable by exactly the measurement defined here: if calibration curves across windows on the same operator do NOT trend toward the diagonal as the operator practices the discipline, the claim is wrong. The empirical record at `~/.episteme/telemetry/*.jsonl` is the data; this file is the measurement specification; FALSIFIABILITY_CONDITIONS.md is the claim under test.

The bidirectional crosswalk (FALSIFIABILITY → CALIBRATION_TELEMETRY for the measurement definition; CALIBRATION_TELEMETRY → FALSIFIABILITY for the claim under test) is deferred to a follow-up Event to keep this Event's blast radius bounded; one-way crosslink into FALSIFIABILITY is sufficient for discoverability.

---

## Attribution

The calibration discipline is borrowed from Tetlock's *Superforecasting* — see [`REFERENCES.md`](./REFERENCES.md) § Primary sources. Operationalizing *what* is computed lives in this file; the *why* lives in Tetlock's empirical work on calibration as the skill that distinguishes forecaster ability from forecaster confidence.

The Brier-score formulation is standard (Brier 1950, *Verification of Forecasts Expressed in Terms of Probability*); the kernel adds the slice-by-decision-class + coverage-required refinements as base-rate-aware extensions appropriate to a per-operator (rather than weather-forecast) measurement target.
