"""benchmarks/cognitive-lift-baseline aggregator + reporter.

Reads all ``runs/<run-id>/grader_verdict.json`` + ``metadata.json``,
computes per-session rollups + bootstrap 95% CIs (1000 resamples,
percentile method), renders ``report.md`` with H1/H2/H3 outcomes against
operator-locked thresholds (Event 116):

- **H1** threshold: 15pp reduction in confident_wrong_rate, 95% CI
  excluding zero (operator decision #6).
- **H2** threshold: 10pp increase in disconfirmation_surface_rate.
- **H3** threshold: turn-tax median <= 50%.

Pure stdlib — no numpy, no scipy. ``random.choices`` is sufficient for
1000-resample bootstrap on N <= 100 sample sizes.
"""
from __future__ import annotations

import json
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_RUNS_ROOT = Path("benchmarks/cognitive-lift-baseline/runs")
BOOTSTRAP_RESAMPLES = 1000

# Operator-locked thresholds (Event 116, README.md § 11).
H1_THRESHOLD_PP = 15.0
H2_THRESHOLD_PP = 10.0
H3_TURN_TAX_CEILING = 0.5  # 50%
# Event 119: depth-of-analysis (0-10) replaces the saturated binary
# metrics for measuring kernel lift at high model strength.
H4_DEPTH_DELTA_THRESHOLD = 1.5


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    task_id: str
    session: str
    confident_wrong: bool
    disconfirmation_surfaced: bool
    rollback_occurred: bool
    time_to_first_disconfirmation: int | None
    depth_of_analysis: int | None  # Event 119; None for legacy verdicts
    wall_clock_seconds: float
    turns: int


@dataclass(frozen=True)
class Rollup:
    session: str
    n: int
    confident_wrong_rate: float
    disconfirmation_surface_rate: float
    rollback_rate: float
    median_time_to_first_disconfirmation: float | None
    median_depth_of_analysis: float | None  # Event 119
    median_wall_clock_seconds: float
    median_turns: float


@dataclass(frozen=True)
class Outcome:
    hypothesis: str
    delta_percentage_points: float
    ci_low: float
    ci_high: float
    threshold_pp: float
    passes: bool
    interpretation: str


def discover_runs(runs_root: Path) -> list[RunRecord]:
    """Walk ``runs_root`` and load each completed run (has both
    ``metadata.json`` and ``grader_verdict.json``). Incomplete runs are
    silently skipped."""
    records: list[RunRecord] = []
    if not runs_root.exists():
        return records
    for run_dir in sorted(runs_root.iterdir()):
        if not run_dir.is_dir():
            continue
        verdict_path = run_dir / "grader_verdict.json"
        metadata_path = run_dir / "metadata.json"
        if not (verdict_path.exists() and metadata_path.exists()):
            continue
        try:
            verdict = json.loads(verdict_path.read_text())
            metadata = json.loads(metadata_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        depth_raw = verdict.get("depth_of_analysis")
        depth = (
            int(depth_raw)
            if isinstance(depth_raw, int) and not isinstance(depth_raw, bool)
            else None
        )
        records.append(RunRecord(
            run_id=metadata.get("run_id", run_dir.name),
            task_id=verdict.get("_task_id", metadata.get("task_id", "")),
            session=verdict.get("_session", metadata.get("session", "?")),
            confident_wrong=bool(verdict.get("confident_wrong", False)),
            disconfirmation_surfaced=bool(
                verdict.get("disconfirmation_surfaced", False)
            ),
            rollback_occurred=bool(verdict.get("rollback_occurred", False)),
            time_to_first_disconfirmation=verdict.get(
                "time_to_first_disconfirmation"
            ),
            depth_of_analysis=depth,
            wall_clock_seconds=float(metadata.get("wall_clock_seconds", 0.0)),
            turns=int(metadata.get("turns", 0)),
        ))
    return records


def _mean_bool(items: Iterable[bool]) -> float:
    seq = list(items)
    return (sum(1 for x in seq if x) / len(seq)) if seq else 0.0


def _median(items: Iterable[float]) -> float:
    seq = list(items)
    return statistics.median(seq) if seq else 0.0


def compute_rollup(records: list[RunRecord], session: str) -> Rollup:
    sub = [r for r in records if r.session == session]
    ttfd_vals = [
        r.time_to_first_disconfirmation for r in sub
        if r.time_to_first_disconfirmation is not None
    ]
    depth_vals = [
        r.depth_of_analysis for r in sub
        if r.depth_of_analysis is not None
    ]
    return Rollup(
        session=session,
        n=len(sub),
        confident_wrong_rate=_mean_bool(r.confident_wrong for r in sub),
        disconfirmation_surface_rate=_mean_bool(
            r.disconfirmation_surfaced for r in sub
        ),
        rollback_rate=_mean_bool(r.rollback_occurred for r in sub),
        median_time_to_first_disconfirmation=(
            _median(ttfd_vals) if ttfd_vals else None
        ),
        median_depth_of_analysis=(
            _median(float(d) for d in depth_vals) if depth_vals else None
        ),
        median_wall_clock_seconds=_median(r.wall_clock_seconds for r in sub),
        median_turns=_median(float(r.turns) for r in sub if r.turns > 0),
    )


def bootstrap_delta_ci(
    a_values: list[bool],
    b_values: list[bool],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    rng: random.Random | None = None,
) -> tuple[float, float, float]:
    """Bootstrap ``(point_estimate, ci_low, ci_high)`` of
    ``(mean_A - mean_B)`` in PERCENTAGE POINTS. Higher delta = A higher
    than B; H1 wants positive delta (kernel reduces confident_wrong)."""
    if not a_values or not b_values:
        return (0.0, 0.0, 0.0)
    if rng is None:
        rng = random.Random(42)
    point = 100.0 * (_mean_bool(a_values) - _mean_bool(b_values))
    deltas: list[float] = []
    for _ in range(resamples):
        a_resamp = rng.choices(a_values, k=len(a_values))
        b_resamp = rng.choices(b_values, k=len(b_values))
        deltas.append(100.0 * (_mean_bool(a_resamp) - _mean_bool(b_resamp)))
    deltas.sort()
    low = deltas[int(0.025 * len(deltas))]
    high = deltas[int(0.975 * len(deltas))]
    return (point, low, high)


def compute_h1_outcome(records: list[RunRecord]) -> Outcome:
    a = [r.confident_wrong for r in records if r.session == "A"]
    b = [r.confident_wrong for r in records if r.session == "B"]
    point, low, high = bootstrap_delta_ci(a, b)
    passes = (low > 0) and (point >= H1_THRESHOLD_PP)
    if passes:
        interp = (
            f"H1 supported — kernel reduces confident-wrong by {point:.1f}pp "
            f"(95% CI [{low:.1f}, {high:.1f}]), exceeds {H1_THRESHOLD_PP:.0f}pp threshold."
        )
    elif low > 0:
        interp = (
            f"H1 partially supported — kernel reduces confident-wrong by {point:.1f}pp "
            f"(95% CI [{low:.1f}, {high:.1f}]) but BELOW {H1_THRESHOLD_PP:.0f}pp threshold."
        )
    elif low <= 0 <= high:
        interp = (
            f"H1 NOT supported — 95% CI [{low:.1f}, {high:.1f}] includes zero. "
            f"No measurable lift on confident_wrong_rate."
        )
    else:
        interp = (
            f"H1 INVERTED — kernel INCREASES confident-wrong by {-point:.1f}pp "
            f"(95% CI [{low:.1f}, {high:.1f}]). Investigate."
        )
    return Outcome(
        hypothesis="H1 (confident_wrong_rate)",
        delta_percentage_points=point,
        ci_low=low,
        ci_high=high,
        threshold_pp=H1_THRESHOLD_PP,
        passes=passes,
        interpretation=interp,
    )


def compute_h2_outcome(records: list[RunRecord]) -> Outcome:
    a = [r.disconfirmation_surfaced for r in records if r.session == "A"]
    b = [r.disconfirmation_surfaced for r in records if r.session == "B"]
    # H2: B should be HIGHER than A. Delta = mean_B - mean_A.
    if not a or not b:
        return Outcome(
            "H2 (disconfirmation_surface_rate)",
            0.0, 0.0, 0.0, H2_THRESHOLD_PP, False,
            "H2 cannot be evaluated — insufficient data.",
        )
    rng = random.Random(43)
    point_ba = 100.0 * (_mean_bool(b) - _mean_bool(a))
    deltas: list[float] = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        a_resamp = rng.choices(a, k=len(a))
        b_resamp = rng.choices(b, k=len(b))
        deltas.append(100.0 * (_mean_bool(b_resamp) - _mean_bool(a_resamp)))
    deltas.sort()
    low = deltas[int(0.025 * len(deltas))]
    high = deltas[int(0.975 * len(deltas))]
    passes = (low > 0) and (point_ba >= H2_THRESHOLD_PP)
    if passes:
        interp = (
            f"H2 supported — kernel surfaces disconfirmation +{point_ba:.1f}pp "
            f"(95% CI [{low:.1f}, {high:.1f}]), exceeds {H2_THRESHOLD_PP:.0f}pp threshold."
        )
    elif low > 0:
        interp = (
            f"H2 partially supported — kernel surfaces +{point_ba:.1f}pp "
            f"(95% CI [{low:.1f}, {high:.1f}]), BELOW {H2_THRESHOLD_PP:.0f}pp threshold."
        )
    else:
        interp = (
            f"H2 NOT supported — 95% CI [{low:.1f}, {high:.1f}] includes zero or inverted."
        )
    return Outcome(
        hypothesis="H2 (disconfirmation_surface_rate)",
        delta_percentage_points=point_ba,
        ci_low=low,
        ci_high=high,
        threshold_pp=H2_THRESHOLD_PP,
        passes=passes,
        interpretation=interp,
    )


def compute_h4_outcome(records: list[RunRecord]) -> Outcome:
    """H4 (Event 119): kernel session B produces deeper reasoning than control A.

    Uses depth_of_analysis (0-10 continuous) instead of the saturated
    binary metrics. Bootstrap CI on (mean_B - mean_A) of depth scores.
    Threshold: median delta >= 1.5 points AND CI excluding zero."""
    a_depths = [
        float(r.depth_of_analysis) for r in records
        if r.session == "A" and r.depth_of_analysis is not None
    ]
    b_depths = [
        float(r.depth_of_analysis) for r in records
        if r.session == "B" and r.depth_of_analysis is not None
    ]
    if not a_depths or not b_depths:
        return Outcome(
            "H4 (depth_of_analysis)", 0.0, 0.0, 0.0,
            H4_DEPTH_DELTA_THRESHOLD, False,
            "H4 cannot be evaluated — insufficient depth-scored runs.",
        )
    rng = random.Random(44)
    point_ba = statistics.mean(b_depths) - statistics.mean(a_depths)
    deltas: list[float] = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        a_resamp = rng.choices(a_depths, k=len(a_depths))
        b_resamp = rng.choices(b_depths, k=len(b_depths))
        deltas.append(statistics.mean(b_resamp) - statistics.mean(a_resamp))
    deltas.sort()
    low = deltas[int(0.025 * len(deltas))]
    high = deltas[int(0.975 * len(deltas))]
    passes = (low > 0) and (point_ba >= H4_DEPTH_DELTA_THRESHOLD)
    if passes:
        interp = (
            f"H4 supported — kernel deepens analysis by +{point_ba:.2f} points "
            f"(95% CI [{low:.2f}, {high:.2f}]), exceeds {H4_DEPTH_DELTA_THRESHOLD:.1f}-point threshold."
        )
    elif low > 0:
        interp = (
            f"H4 partially supported — kernel deepens by +{point_ba:.2f} points "
            f"(95% CI [{low:.2f}, {high:.2f}]), BELOW {H4_DEPTH_DELTA_THRESHOLD:.1f}-point threshold."
        )
    elif point_ba > 0:
        interp = (
            f"H4 directional but inconclusive — point estimate +{point_ba:.2f} points "
            f"but 95% CI [{low:.2f}, {high:.2f}] includes zero."
        )
    else:
        interp = (
            f"H4 NOT supported — kernel does NOT measurably deepen analysis "
            f"(point {point_ba:.2f}, 95% CI [{low:.2f}, {high:.2f}])."
        )
    return Outcome(
        hypothesis="H4 (depth_of_analysis)",
        delta_percentage_points=point_ba,
        ci_low=low,
        ci_high=high,
        threshold_pp=H4_DEPTH_DELTA_THRESHOLD,
        passes=passes,
        interpretation=interp,
    )


def compute_h3_outcome(records: list[RunRecord]) -> Outcome:
    """H3: kernel turn tax is bounded (median additional turns <= 50% over A)."""
    a_turns = [
        float(r.turns) for r in records if r.session == "A" and r.turns > 0
    ]
    b_turns = [
        float(r.turns) for r in records if r.session == "B" and r.turns > 0
    ]
    if not a_turns or not b_turns:
        return Outcome(
            "H3 (turn_tax)", 0.0, 0.0, 0.0,
            H3_TURN_TAX_CEILING * 100, False,
            "H3 cannot be evaluated — insufficient data.",
        )
    median_a = statistics.median(a_turns)
    median_b = statistics.median(b_turns)
    tax_pp = (
        100.0 * (median_b - median_a) / median_a if median_a > 0 else 0.0
    )
    passes = tax_pp <= H3_TURN_TAX_CEILING * 100
    ceiling_pct = H3_TURN_TAX_CEILING * 100
    if passes:
        interp = (
            f"H3 supported — turn tax {tax_pp:.1f}% <= {ceiling_pct:.0f}% ceiling."
        )
    else:
        interp = (
            f"H3 NOT supported — turn tax {tax_pp:.1f}% exceeds {ceiling_pct:.0f}% ceiling. "
            f"Kernel friction may consume the H1 lift."
        )
    return Outcome(
        hypothesis="H3 (turn_tax)",
        delta_percentage_points=tax_pp,
        ci_low=tax_pp,
        ci_high=tax_pp,
        threshold_pp=ceiling_pct,
        passes=passes,
        interpretation=interp,
    )


def render_report(records: list[RunRecord], outcomes: list[Outcome]) -> str:
    lines: list[str] = ["# Empirical-Lift Benchmark — Run Report", ""]
    lines.append(f"**Total runs:** {len(records)}")
    lines.append(
        "**Sessions:** A (control / no-kernel) and "
        "B (treatment / kernel-strict-mode per Event 116 decision #4)"
    )
    lines.append("")
    a_rollup = compute_rollup(records, "A")
    b_rollup = compute_rollup(records, "B")
    lines.append("## Rollups")
    lines.append("")
    lines.append("| Metric | Session A | Session B |")
    lines.append("|---|---|---|")
    lines.append(f"| n | {a_rollup.n} | {b_rollup.n} |")
    lines.append(
        f"| confident_wrong_rate | {a_rollup.confident_wrong_rate:.3f} | "
        f"{b_rollup.confident_wrong_rate:.3f} |"
    )
    lines.append(
        f"| disconfirmation_surface_rate | "
        f"{a_rollup.disconfirmation_surface_rate:.3f} | "
        f"{b_rollup.disconfirmation_surface_rate:.3f} |"
    )
    lines.append(
        f"| rollback_rate | {a_rollup.rollback_rate:.3f} | "
        f"{b_rollup.rollback_rate:.3f} |"
    )
    lines.append(
        f"| median wall_clock_s | {a_rollup.median_wall_clock_seconds:.1f} | "
        f"{b_rollup.median_wall_clock_seconds:.1f} |"
    )
    lines.append(
        f"| median turns | {a_rollup.median_turns:.1f} | "
        f"{b_rollup.median_turns:.1f} |"
    )
    a_depth = (
        f"{a_rollup.median_depth_of_analysis:.1f}/10"
        if a_rollup.median_depth_of_analysis is not None else "—"
    )
    b_depth = (
        f"{b_rollup.median_depth_of_analysis:.1f}/10"
        if b_rollup.median_depth_of_analysis is not None else "—"
    )
    lines.append(f"| median depth_of_analysis | {a_depth} | {b_depth} |")
    lines.append("")
    lines.append("## Hypothesis outcomes")
    lines.append("")
    for outcome in outcomes:
        marker = "PASS" if outcome.passes else "FAIL"
        lines.append(f"### [{marker}] {outcome.hypothesis}")
        lines.append("")
        lines.append(f"- delta: {outcome.delta_percentage_points:.1f}pp")
        lines.append(f"- 95% CI: [{outcome.ci_low:.1f}, {outcome.ci_high:.1f}]")
        lines.append(f"- threshold: {outcome.threshold_pp:.1f}pp")
        lines.append(f"- {outcome.interpretation}")
        lines.append("")
    return "\n".join(lines)


def aggregate_and_report(
    runs_root: Path,
) -> tuple[list[RunRecord], list[Outcome], str]:
    records = discover_runs(runs_root)
    outcomes = [
        compute_h1_outcome(records),
        compute_h2_outcome(records),
        compute_h3_outcome(records),
        compute_h4_outcome(records),
    ]
    return records, outcomes, render_report(records, outcomes)
