"""`episteme report` — tangible, quantified value-visibility for the kernel.

Today `episteme evaluate` emits JSON and the Tier 1 soak gate is a 7-day
black box. This module renders a single human-facing report that makes the
kernel's effect on decision quality *visible* and *quantified*, drawing from
the same local telemetry stores the runtime already writes:

Sections
--------
1. **Surface Authoring** — from ``~/.episteme/audit.jsonl``: how often the
   Reasoning Surface was authored (``action == 'passed'``) out of all
   high-impact ops the gate saw.
2. **Failure Modes Countered** — bucket the audit ``op`` labels into the
   named System-1 failure mode each one counters (cascade-theater /
   Fence-Check / WYSIATI-empty-Unknowns), counting records the gate
   actually acted on (``action in {passed, advisory}``).
3. **Tier-1 Soak** — reuse the live soak-gate logic
   (``core.hooks._irreversible_tier.soak_gate_open`` +
   ``episteme._tier1_audit._compute_metrics``) to render ops X/20,
   days Y/7, accuracy Z% vs the 90% floor as a progress bar.
4. **Calibration Trend** — from ``~/.episteme/telemetry/*-audit.jsonl``,
   pair prediction+outcome records by ``correlation_id`` and draw a
   per-UTC-day sparkline of the fraction of ops that exited 0.
5. **Verdict** — a one-line synthesis.

Empty-state contract (load-bearing)
-----------------------------------
On a fresh install with no telemetry we NEVER show an empty box. With
``--demo`` *or* (no ``--demo`` and all three stores empty) the report renders
a fully-populated *worked example* (``_demo_metrics()``) inside a box titled
``WORKED EXAMPLE — not your data``, a ``(worked example)`` verdict prefix, and
a one-line "No telemetry yet" notice — so the very first run still demonstrates
the tangible value the report will surface once real data accrues.

The command is read-only and ALWAYS returns 0.

CRITICAL telemetry-key note
---------------------------
The runtime writes the timestamp key as ``ts`` (see
``core/hooks/reasoning_surface_guard.py`` ``_write_prediction`` /
``calibration_telemetry.py``). ``episteme/_evaluate.py`` reads ``timestamp``,
which is empty against real data. This module reads ``rec.get('ts')`` first
with a ``timestamp`` fallback so every calibration metric is computed against
the data the runtime actually produces.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from episteme import _ui

# Editable-install + repo-checkout discoverability: the soak-gate logic lives
# at core/hooks/_irreversible_tier.py, outside the installed package tree.
# When invoked from an editable install (`pip install -e .`),
# Path(__file__).parents[2] is the repo root that holds both src/ and core/.
# Add it to sys.path so `from core.hooks...` resolves at CLI runtime. Guard
# keys on `core/` being a directory — the stable package-root invariant the
# sibling _tier1_audit.py uses (Event 136 fence-discipline call) — rather than
# a specific subpackage that may move.
_REPO_ROOT_CANDIDATE = Path(__file__).resolve().parents[2]
if (_REPO_ROOT_CANDIDATE / "core").is_dir():
    if str(_REPO_ROOT_CANDIDATE) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT_CANDIDATE))


# ---------------------------------------------------------------------------
# Failure-mode bucketing
# ---------------------------------------------------------------------------

# Stable display labels for the three System-1 failure-mode buckets. The keys
# are the short bucket ids used in metrics dicts; the values are the full
# kernel-named labels rendered in the section.
_FM_WYSIATI = "WYSIATI / empty-Unknowns (Reasoning Surface)"
_FM_CASCADE = "Narrative fallacy / cascade-theater (Blueprint D)"
_FM_FENCE = "Fence-Check (unexplained-constraint removal)"

# bucket id -> display label, in stable render order.
_FM_LABELS: tuple[tuple[str, str], ...] = (
    ("WYSIATI", _FM_WYSIATI),
    ("cascade", _FM_CASCADE),
    ("fence", _FM_FENCE),
)


def _bucket_op(op: str) -> str:
    """Map an audit `op` label to its failure-mode bucket id.

    Prefix-based per the kernel's op-label conventions:
      - ``cascade:*``  -> narrative-fallacy / cascade-theater (Blueprint D)
      - ``fence:*``    -> Fence-Check (unexplained-constraint removal)
      - everything else (git push / npm publish / terraform / gh pr merge /
        SQL DROP / pip install ...) -> WYSIATI / empty-Unknowns, which the
        Reasoning Surface is the primary counter for.
    """
    label = (op or "").strip()
    if label.startswith("cascade:"):
        return "cascade"
    if label.startswith("fence:"):
        return "fence"
    return "WYSIATI"


# ---------------------------------------------------------------------------
# ReportData — the frozen view model the renderer consumes.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportData:
    """Frozen, render-ready snapshot of every metric the report shows.

    `_collect_metrics` produces this from the live stores; `_demo_metrics`
    produces a hand-authored populated example for the empty-state. The
    renderer (`_render`) and verdict (`_verdict`) consume only this struct —
    they never touch disk — so the demo path and the real path render through
    exactly the same code.
    """

    is_demo: bool

    # (1) Surface Authoring
    surface_total: int
    surface_authored: int

    # (2) Failure Modes Countered — bucket id -> count
    failure_modes: dict = field(default_factory=dict)

    # (3) Tier-1 Soak
    tier1_ops: int = 0
    tier1_ops_floor: int = 20
    tier1_days: float = 0.0
    tier1_days_floor: int = 7
    tier1_accuracy: Optional[float] = None  # fraction 0..1, or None if undefined
    tier1_accuracy_floor: float = 0.90
    tier1_gate_open: bool = False
    tier1_gate_reason: str = ""

    # (4) Calibration Trend — series of per-day fractions exit_code==0
    calibration_series: tuple = ()
    calibration_paired_ops: int = 0

    # (5) Protocol Synthesis — Pillar 3 store + E1 falsifiability
    # self-check (Event 137). `framework_age_days` is days since the
    # oldest framework record (protocols OR deferred discoveries);
    # None when the framework has never been written to.
    protocols_total: int = 0
    framework_age_days: Optional[int] = None
    e1_protocol_floor: int = 3
    e1_window_days: int = 30

    @property
    def surface_rate(self) -> Optional[float]:
        if self.surface_total <= 0:
            return None
        return self.surface_authored / self.surface_total

    @property
    def failure_modes_total(self) -> int:
        return sum(self.failure_modes.values())

    @property
    def e1_fired(self) -> bool:
        """kernel/FALSIFIABILITY_CONDITIONS.md § E1, evaluated against
        live state: < floor protocols after the 30-day window of
        framework activity falsifies the active-guidance claim."""
        return (
            self.framework_age_days is not None
            and self.framework_age_days >= self.e1_window_days
            and self.protocols_total < self.e1_protocol_floor
        )


# ---------------------------------------------------------------------------
# Demo (worked-example) metrics — the empty-state payload.
# ---------------------------------------------------------------------------


def _demo_metrics() -> ReportData:
    """A fully-populated worked example for the empty-state / --demo path.

    Realistic numbers chosen so every section renders something meaningful:
      - surface authoring 47/52 = 90.4%
      - failure modes {WYSIATI:31, cascade:12, fence:6}
      - tier1 14/20 ops, 5.2/7 days, 92.9% accuracy, gate CLOSED
      - calibration 12 ascending points 0.71 .. 0.93
    """
    return ReportData(
        is_demo=True,
        surface_total=52,
        surface_authored=47,
        failure_modes={"WYSIATI": 31, "cascade": 12, "fence": 6},
        tier1_ops=14,
        tier1_days=5.2,
        tier1_accuracy=0.929,
        tier1_gate_open=False,
        tier1_gate_reason=(
            "soak gate CLOSED: 14 records < 20 required (worked example)"
        ),
        calibration_series=(
            0.71, 0.73, 0.76, 0.78, 0.80, 0.83,
            0.85, 0.87, 0.89, 0.91, 0.92, 0.93,
        ),
        calibration_paired_ops=96,
        protocols_total=4,
        framework_age_days=21,
    )


# ---------------------------------------------------------------------------
# Metric collection from the live stores.
# ---------------------------------------------------------------------------


def _collect_metrics(
    telemetry_dir: Path,
    audit_path: Path,
    tier1_path: Path,
    framework_dir: Path,
) -> ReportData:
    """Read the live stores and build a real `ReportData`.

    - `audit_path`     : ~/.episteme/audit.jsonl (sections 1 + 2)
    - `tier1_path`     : ~/.episteme/telemetry/tier1.jsonl (section 3)
    - `telemetry_dir`  : ~/.episteme/telemetry/ (section 4, *-audit.jsonl)
    - `framework_dir`  : ~/.episteme/framework/ (section 5, protocols.jsonl
                         + deferred_discoveries.jsonl)

    None of these need to exist — missing stores yield zero-valued metrics,
    which the caller uses to decide whether to fall through to the demo.
    """
    audit_records = _read_jsonl(audit_path)

    # (1) Surface authoring — total records seen by the gate; authored = the
    # subset where a valid Reasoning Surface let the op pass.
    surface_total = len(audit_records)
    surface_authored = sum(
        1 for r in audit_records if r.get("action") == "passed"
    )

    # (2) Failure modes — count records the gate acted on (passed OR advisory),
    # bucketed by op label.
    failure_modes: dict = {}
    for r in audit_records:
        if r.get("action") not in ("passed", "advisory"):
            continue
        bucket = _bucket_op(str(r.get("op", "")))
        failure_modes[bucket] = failure_modes.get(bucket, 0) + 1

    # (3) Tier-1 soak — reuse the live audit + gate logic.
    tier1_ops, tier1_days, tier1_accuracy, gate_open, gate_reason = (
        _collect_tier1(tier1_path)
    )

    # (4) Calibration trend.
    calibration_series, paired_ops = _collect_calibration(telemetry_dir)

    # (5) Protocol synthesis + E1 self-check.
    protocols_total, framework_age_days = _collect_framework(framework_dir)

    return ReportData(
        is_demo=False,
        surface_total=surface_total,
        surface_authored=surface_authored,
        failure_modes=failure_modes,
        tier1_ops=tier1_ops,
        tier1_days=tier1_days,
        tier1_accuracy=tier1_accuracy,
        tier1_gate_open=gate_open,
        tier1_gate_reason=gate_reason,
        protocols_total=protocols_total,
        framework_age_days=framework_age_days,
        calibration_series=tuple(calibration_series),
        calibration_paired_ops=paired_ops,
    )


def _collect_tier1(tier1_path: Path):
    """Return (ops, span_days, accuracy, gate_open, gate_reason).

    Reuses `episteme._tier1_audit._compute_metrics` for the numbers and
    `core.hooks._irreversible_tier.soak_gate_open` for the gate verdict, so
    the report can never drift from the live soak-gate semantics.
    """
    from episteme._tier1_audit import _compute_metrics

    metrics = _compute_metrics(tier1_path)
    ops = int(metrics.get("record_count", 0))
    span_days = float(metrics.get("span_days", 0.0) or 0.0)
    accuracy = metrics.get("rationale_accuracy")  # float | None

    gate_open = False
    gate_reason = ""
    try:
        from core.hooks._irreversible_tier import soak_gate_open
        gate_open, gate_reason = soak_gate_open(path=tier1_path)
    except Exception as exc:  # pragma: no cover - import-environment guard
        gate_reason = f"soak gate unavailable: {exc.__class__.__name__}"

    return ops, span_days, accuracy, gate_open, gate_reason


def _collect_calibration(telemetry_dir: Path):
    """Pair prediction+outcome records by correlation_id, group by UTC day,
    and return (per-day fraction-exit-0 series, paired_op_count).

    A correlation_id contributes a data point only when BOTH a prediction
    record and an outcome record (with a non-None exit_code) exist for it.
    The day bucket is taken from the outcome record's timestamp.

    Reads the timestamp under the `ts` key the runtime actually writes,
    falling back to `timestamp` for forward-compat / hand-seeded data.
    """
    records: list[dict] = []
    if telemetry_dir.is_dir():
        for path in sorted(telemetry_dir.glob("*-audit.jsonl")):
            records.extend(_read_jsonl(path))

    # Index outcomes by correlation_id (last write wins per id).
    predictions: set = set()
    outcomes: dict = {}
    for r in records:
        cid = r.get("correlation_id")
        if not cid:
            continue
        event = r.get("event")
        if event == "prediction":
            predictions.add(cid)
        elif event == "outcome":
            outcomes[cid] = r

    # Per-day accumulation: day -> [total_paired, exited_zero].
    day_total: dict = defaultdict(int)
    day_zero: dict = defaultdict(int)
    paired = 0
    for cid, outcome in outcomes.items():
        if cid not in predictions:
            continue
        exit_code = outcome.get("exit_code")
        if exit_code is None:
            continue
        day = _record_day(outcome)
        if day is None:
            continue
        paired += 1
        day_total[day] += 1
        if exit_code == 0:
            day_zero[day] += 1

    series = [
        day_zero[day] / day_total[day]
        for day in sorted(day_total)
        if day_total[day] > 0
    ]
    return series, paired


def _record_day(rec: dict) -> Optional[str]:
    """Return the YYYY-MM-DD UTC day for a telemetry record, or None.

    CRITICAL: reads `ts` first (the key the runtime writes), then falls back
    to `timestamp`. Reading only `timestamp` produces an empty series against
    real data — the bug this module exists to avoid.
    """
    ts_str = rec.get("ts") or rec.get("timestamp")
    if not isinstance(ts_str, str) or not ts_str.strip():
        return None
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of dicts. Missing file -> []. Corrupt
    lines are skipped. Never raises."""
    records: list[dict] = []
    if not path.is_file():
        return records
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    records.append(obj)
    except OSError:
        return records
    return records


def _collect_framework(framework_dir: Path) -> tuple[int, Optional[int]]:
    """Protocol count + framework activity age in days (section 5).

    Raw line reads (no chain verification), consistent with _status.py —
    the report is read-only telemetry, not an integrity audit. Age is
    days since the OLDEST envelope ts across protocols and deferred
    discoveries; None when the framework holds no records at all.
    """
    protocols = _read_jsonl(framework_dir / "protocols.jsonl")
    deferred = _read_jsonl(framework_dir / "deferred_discoveries.jsonl")
    earliest: Optional[datetime] = None
    for env in protocols + deferred:
        ts = env.get("ts")
        if not isinstance(ts, str) or not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if earliest is None or dt < earliest:
            earliest = dt
    age_days: Optional[int] = None
    if earliest is not None:
        age_days = max(
            0, (datetime.now(timezone.utc) - earliest).days
        )
    return len(protocols), age_days


# ---------------------------------------------------------------------------
# Verdict.
# ---------------------------------------------------------------------------


def _verdict(data: ReportData) -> str:
    """One-line synthesis across the four sections.

    On the demo path the line is prefixed with `(worked example)` so it can
    never be mistaken for a real verdict.
    """
    rate = data.surface_rate
    if rate is None:
        body = (
            "No high-impact ops recorded yet — author a Reasoning Surface on "
            "your next git push / publish / migration to start the record."
        )
    elif rate >= 0.80:
        body = (
            f"Calibrated — the Reasoning Surface was authored on "
            f"{rate:.0%} of {data.surface_total} high-impact ops; "
            f"{data.failure_modes_total} ops routed through a named "
            f"System-1 counter."
        )
    elif rate >= 0.50:
        body = (
            f"Partial — surface authored on {rate:.0%} of "
            f"{data.surface_total} high-impact ops; review the gaps where "
            f"the gate fired advisory-only."
        )
    else:
        body = (
            f"Low — surface authored on only {rate:.0%} of "
            f"{data.surface_total} high-impact ops; ops may be bypassing "
            f"the gate or running advisory-only."
        )

    gate = "OPEN" if data.tier1_gate_open else "CLOSED"
    body += f" Tier-1 soak gate: {gate}."

    if data.e1_fired:
        body += (
            f" Falsifiability: E1 FIRED — {data.protocols_total} "
            f"protocols after {data.framework_age_days} days of "
            f"framework activity (floor: {data.e1_protocol_floor} per "
            f"{data.e1_window_days}d); active guidance is currently "
            f"aspirational — see kernel/FALSIFIABILITY_CONDITIONS.md "
            f"§ E1."
        )

    if data.is_demo:
        return f"(worked example) {body}"
    return body


# ---------------------------------------------------------------------------
# Rendering.
# ---------------------------------------------------------------------------


def _fmt_pct(value: Optional[float]) -> str:
    return f"{value:.1%}" if value is not None else "n/a"


def _health_word(value: float, *, good: float, warn: float) -> str:
    """Plain-text health label paired with the colored glyph so the signal
    survives color-stripping (good / watch / low)."""
    if value >= good:
        return "good"
    if value >= warn:
        return "watch"
    return "low"


def _render(data: ReportData, renderer: _ui.Renderer) -> str:
    """Render `data` into the full multi-section report string.

    The `renderer` carries the rich/color/box/width detection so callers can
    pin deterministic ASCII output in tests (EPISTEME_NO_RICH=1). The renderer
    is passed for symmetry + future width-aware layout; the `_ui` primitives
    re-detect their own escape state internally, which keeps EPISTEME_NO_RICH
    authoritative for both the structure here and the primitives.
    """
    parts: list[str] = []

    parts.append(_ui.header("episteme — value report", level=1))
    parts.append("")

    if data.is_demo:
        parts.append(
            "No telemetry yet — here is what this report will look like "
            "once you run a few high-impact ops."
        )
        parts.append("")

    # ── (1) Surface Authoring ─────────────────────────────────────────────
    parts.append(_ui.header("Surface Authoring", level=2))
    rate = data.surface_rate
    rate_str = _fmt_pct(rate)
    surface_rows = [
        ("High-impact ops seen", str(data.surface_total)),
        ("Reasoning Surface authored", str(data.surface_authored)),
        ("Authoring rate", rate_str),
    ]
    if rate is not None:
        ind = _ui.health_indicator(rate, good_threshold=0.80, warn_threshold=0.50)
        # Append a word so the signal survives color-stripping (PRs, Slack,
        # piped output) — a bare colored dot collapses to an ambiguous glyph.
        surface_rows.append(("Health", f"{ind} {_health_word(rate, good=0.80, warn=0.50)}"))
    parts.append(_ui.kv_table(surface_rows))
    if data.surface_total > 0:
        parts.append(
            _ui.progress(
                data.surface_authored, data.surface_total, label="authored"
            )
        )
    parts.append("")

    # ── (2) Failure Modes Countered ───────────────────────────────────────
    parts.append(_ui.header("Failure Modes Countered", level=2))
    fm_rows = []
    for bucket_id, label in _FM_LABELS:
        count = data.failure_modes.get(bucket_id, 0)
        fm_rows.append((label, str(count)))
    fm_rows.append(("Total ops countered", str(data.failure_modes_total)))
    # Size the key column to the longest label so the counts stay in a
    # single aligned column (the longest failure-mode label is ~49 chars,
    # which overflowed the prior fixed key_width=46 and jammed its count).
    fm_key_width = max((len(label) for label, _ in fm_rows), default=28) + 2
    parts.append(_ui.kv_table(fm_rows, key_width=fm_key_width))
    parts.append("")

    # ── (3) Tier-1 Soak ───────────────────────────────────────────────────
    parts.append(_ui.header("Tier-1 Soak", level=2))
    # The bar already prints current/total, so the label is just the noun
    # (no redundant "(14/20)"). Days passes the float so the decimal shows
    # once in the bar ("5.2/7") rather than as "5/7  days (5.2/7)".
    parts.append(
        _ui.progress(
            min(data.tier1_ops, data.tier1_ops_floor),
            data.tier1_ops_floor,
            label="ops",
        )
    )
    parts.append(
        _ui.progress(
            min(data.tier1_days, data.tier1_days_floor),
            data.tier1_days_floor,
            label="days",
        )
    )
    acc = data.tier1_accuracy
    acc_str = _fmt_pct(acc)
    acc_rows = [
        (
            "Rationale-accuracy",
            f"{acc_str} vs {data.tier1_accuracy_floor:.0%} floor",
        ),
        ("Soak gate", "OPEN" if data.tier1_gate_open else "CLOSED"),
    ]
    if data.tier1_gate_reason:
        acc_rows.append(("Reason", data.tier1_gate_reason))
    parts.append(_ui.kv_table(acc_rows))
    parts.append("")

    # ── (4) Calibration Trend ─────────────────────────────────────────────
    parts.append(_ui.header("Calibration Trend", level=2))
    if data.calibration_series:
        spark = _ui.sparkline(data.calibration_series)
        first = data.calibration_series[0]
        last = data.calibration_series[-1]
        cal_rows = [
            (
                "Per-day exit-0 fraction",
                f"{spark}  ({_fmt_pct(first)} -> {_fmt_pct(last)})",
            ),
            ("Paired prediction+outcome ops", str(data.calibration_paired_ops)),
            ("Days tracked", str(len(data.calibration_series))),
        ]
        parts.append(_ui.kv_table(cal_rows))
    else:
        parts.append(
            _ui.kv_table([
                (
                    "Per-day exit-0 fraction",
                    "no paired prediction+outcome telemetry yet",
                ),
            ])
        )
    parts.append("")

    # ── (5) Protocol Synthesis ────────────────────────────────────────────
    # Pillar 3's compounding loop, with the E1 falsifiability self-check
    # evaluated against live state (Event 137). Omitting this section
    # made the report a gate-side-only view — value claimed while the
    # compounding half sat empty and unmentioned.
    parts.append(_ui.header("Protocol Synthesis", level=2))
    if data.framework_age_days is None:
        e1_str = "n/a — no framework activity yet"
        age_str = "n/a"
    else:
        age_str = f"{data.framework_age_days} days"
        if data.e1_fired:
            e1_str = (
                f"FIRED — {data.protocols_total} < "
                f"{data.e1_protocol_floor} protocols after "
                f"{data.framework_age_days}d "
                f"(kernel/FALSIFIABILITY_CONDITIONS.md § E1)"
            )
        elif data.framework_age_days < data.e1_window_days:
            e1_str = (
                f"window open "
                f"({data.framework_age_days}/{data.e1_window_days}d)"
            )
        else:
            e1_str = "holding"
    syn_rows = [
        ("Protocols synthesized", str(data.protocols_total)),
        ("Framework activity", age_str),
        ("E1 falsifiability", e1_str),
    ]
    parts.append(_ui.kv_table(syn_rows))
    parts.append("")

    # ── (6) Verdict ───────────────────────────────────────────────────────
    parts.append(_ui.header("Verdict", level=2))
    parts.append(_verdict(data))

    body = "\n".join(parts)

    # Empty-state framing: prepend a slim, unmissable banner box, then render
    # the sections UNBOXED below it. Wrapping the whole report in one box
    # clipped section lines at the terminal width (the worked-example verdict
    # / soak reason / sparkline legend lost their tails to an ellipsis); a
    # banner-on-top keeps the demo signal loud while every metric line renders
    # full-width. The banner content is short by design so it never truncates.
    if data.is_demo:
        banner = _ui.box(
            "Illustrative numbers — NOT your data. This is exactly what the\n"
            "report renders once you run a few high-impact ops.",
            title="WORKED EXAMPLE — not your data",
        )
        return banner + "\n\n" + body
    return body


# ---------------------------------------------------------------------------
# JSON view (for --json).
# ---------------------------------------------------------------------------


def _to_json(data: ReportData) -> dict:
    """Serialize a ReportData to a plain JSON-able dict."""
    return {
        "is_demo": data.is_demo,
        "surface": {
            "total": data.surface_total,
            "authored": data.surface_authored,
            "rate": (
                round(data.surface_rate, 4)
                if data.surface_rate is not None else None
            ),
        },
        "failure_modes": {
            label: data.failure_modes.get(bucket_id, 0)
            for bucket_id, label in _FM_LABELS
        },
        "failure_modes_total": data.failure_modes_total,
        "tier1": {
            "ops": data.tier1_ops,
            "ops_floor": data.tier1_ops_floor,
            "days": round(data.tier1_days, 2),
            "days_floor": data.tier1_days_floor,
            "accuracy": (
                round(data.tier1_accuracy, 4)
                if data.tier1_accuracy is not None else None
            ),
            "accuracy_floor": data.tier1_accuracy_floor,
            "gate_open": data.tier1_gate_open,
            "gate_reason": data.tier1_gate_reason,
        },
        "calibration": {
            "series": [round(x, 4) for x in data.calibration_series],
            "paired_ops": data.calibration_paired_ops,
            "days_tracked": len(data.calibration_series),
        },
        "protocol_synthesis": {
            "protocols_total": data.protocols_total,
            "framework_age_days": data.framework_age_days,
            "e1_floor": data.e1_protocol_floor,
            "e1_window_days": data.e1_window_days,
            "e1_fired": data.e1_fired,
        },
        "verdict": _verdict(data),
    }


# ---------------------------------------------------------------------------
# CLI entry point.
# ---------------------------------------------------------------------------


def run_report_cli(argv: list[str]) -> int:
    """`episteme report` entry point. Read-only; ALWAYS returns 0."""
    parser = argparse.ArgumentParser(
        prog="episteme report",
        description=(
            "Tangible, quantified value report for episteme — surface "
            "authoring, failure modes countered, Tier-1 soak progress, and "
            "calibration trend, from local telemetry. Read-only."
        ),
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Render a fully-populated worked example instead of your data",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of the rendered report",
    )
    parser.add_argument(
        "--telemetry-dir",
        type=Path,
        default=None,
        help="Override telemetry directory (default: ~/.episteme/telemetry/)",
    )
    parser.add_argument(
        "--audit-path",
        type=Path,
        default=None,
        help="Override audit log path (default: ~/.episteme/audit.jsonl)",
    )
    parser.add_argument(
        "--tier1-path",
        type=Path,
        default=None,
        help=(
            "Override Tier-1 telemetry path "
            "(default: ~/.episteme/telemetry/tier1.jsonl)"
        ),
    )
    parser.add_argument(
        "--framework-dir",
        type=Path,
        default=None,
        help=(
            "Override framework directory "
            "(default: ~/.episteme/framework/)"
        ),
    )

    args = parser.parse_args(argv)

    base = Path.home() / ".episteme"
    telemetry_dir = args.telemetry_dir or (base / "telemetry")
    audit_path = args.audit_path or (base / "audit.jsonl")
    tier1_path = args.tier1_path or (base / "telemetry" / "tier1.jsonl")
    framework_dir = args.framework_dir or (base / "framework")

    if args.demo:
        data = _demo_metrics()
    else:
        data = _collect_metrics(
            telemetry_dir, audit_path, tier1_path, framework_dir
        )
        # Empty-state contract: on a fresh install with no telemetry in ANY
        # of the three stores, render the worked example rather than an
        # empty box. This is the load-bearing first-run behavior.
        if _is_empty(data):
            data = _demo_metrics()

    if args.json:
        print(json.dumps(_to_json(data), indent=2, sort_keys=True))
        return 0

    renderer = _ui.Renderer.detect()
    print(_render(data, renderer))
    return 0


def _is_empty(data: ReportData) -> bool:
    """True iff all three live stores produced nothing worth rendering."""
    return (
        data.surface_total == 0
        and data.failure_modes_total == 0
        and data.tier1_ops == 0
        and not data.calibration_series
    )


def main() -> int:
    return run_report_cli(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
