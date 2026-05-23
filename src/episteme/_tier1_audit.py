"""Event 135 — Stage 3 — `episteme tier1 audit` CLI.

Reads `~/.episteme/telemetry/tier1.jsonl` and reports the calibration
metrics that govern the Stage 3 soak gate:

- **Volume:** count of records.
- **Calendar span:** distance from earliest to current time in days.
- **Rationale-accuracy rate:** of operator-confirmed records, the
  fraction where `subsequent_revert_within_24h` is False.
- **Soak gate verdict:** OPEN iff all three thresholds in
  `core.practice.irreversible_tier.soak_gate_open` are met.

Exit codes:
- 0 — audit succeeded (gate OPEN or CLOSED, both are normal states)
- 1 — telemetry read error or unexpected exception
- 2 — `--require-open` flag was set and the gate is CLOSED

The CLI is invoked as `episteme tier1 audit` via the pre-argparse
dispatch in `src/episteme/cli.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_tier1_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="episteme tier1",
        description=(
            "Inspect the Tier 1 advisory soak gate. Reads "
            "~/.episteme/telemetry/tier1.jsonl and reports calibration "
            "thresholds + gate verdict."
        ),
    )
    sub = parser.add_subparsers(dest="action", required=True)

    audit = sub.add_parser(
        "audit",
        help="Compute calibration metrics + report soak-gate verdict",
    )
    audit.add_argument(
        "--telemetry-path",
        type=Path,
        default=None,
        help="Override telemetry path (default: ~/.episteme/telemetry/tier1.jsonl)",
    )
    audit.add_argument(
        "--require-open",
        action="store_true",
        help="Exit 2 if the soak gate is CLOSED (useful for CI gating)",
    )
    audit.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable report",
    )

    args = parser.parse_args(argv)
    if args.action == "audit":
        return _audit(
            telemetry_path=args.telemetry_path,
            require_open=args.require_open,
            json_output=args.json,
        )
    parser.print_help()
    return 1


def _audit(
    telemetry_path: Path | None,
    require_open: bool,
    json_output: bool,
) -> int:
    # Import lazily so the CLI module imports cheaply.
    from core.practice.irreversible_tier import (
        SOAK_GATE_MIN_DAYS,
        SOAK_GATE_MIN_OPS,
        SOAK_GATE_MIN_RATIONALE_ACCURACY,
        TIER1_TELEMETRY_PATH,
        soak_gate_open,
    )

    target = telemetry_path or TIER1_TELEMETRY_PATH
    metrics = _compute_metrics(target)
    gate_open, gate_reason = soak_gate_open(path=target)

    metrics["soak_gate_open"] = gate_open
    metrics["soak_gate_reason"] = gate_reason
    metrics["thresholds"] = {
        "min_ops": SOAK_GATE_MIN_OPS,
        "min_days": SOAK_GATE_MIN_DAYS,
        "min_rationale_accuracy": SOAK_GATE_MIN_RATIONALE_ACCURACY,
    }
    metrics["telemetry_path"] = str(target)

    if json_output:
        print(json.dumps(metrics, indent=2, sort_keys=True))
    else:
        _print_human_report(metrics)

    if require_open and not gate_open:
        return 2
    return 0


def _compute_metrics(target: Path) -> dict:
    metrics: dict = {
        "record_count": 0,
        "earliest_timestamp": None,
        "latest_timestamp": None,
        "span_days": 0.0,
        "operator_confirmed_count": 0,
        "reverted_within_24h_count": 0,
        "rationale_accuracy": None,
        "pattern_distribution": {},
        "parse_errors": 0,
    }
    if not target.is_file():
        return metrics

    earliest: datetime | None = None
    latest: datetime | None = None

    try:
        with open(target, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    metrics["parse_errors"] += 1
                    continue
                metrics["record_count"] += 1
                ts_str = rec.get("timestamp", "")
                if isinstance(ts_str, str):
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        if earliest is None or ts < earliest:
                            earliest = ts
                        if latest is None or ts > latest:
                            latest = ts
                    except ValueError:
                        pass
                if rec.get("operator_confirmed") is True:
                    metrics["operator_confirmed_count"] += 1
                    if rec.get("subsequent_revert_within_24h") is True:
                        metrics["reverted_within_24h_count"] += 1
                pattern = rec.get("pattern", "<unknown>")
                metrics["pattern_distribution"][pattern] = (
                    metrics["pattern_distribution"].get(pattern, 0) + 1
                )
    except OSError as exc:
        metrics["read_error"] = f"{exc.__class__.__name__}: {exc}"
        return metrics

    if earliest is not None:
        metrics["earliest_timestamp"] = earliest.isoformat()
    if latest is not None:
        metrics["latest_timestamp"] = latest.isoformat()
    if earliest is not None:
        now = datetime.now(timezone.utc)
        metrics["span_days"] = round((now - earliest).total_seconds() / 86400.0, 2)

    confirmed = metrics["operator_confirmed_count"]
    reverted = metrics["reverted_within_24h_count"]
    if confirmed > 0:
        metrics["rationale_accuracy"] = round((confirmed - reverted) / confirmed, 4)

    return metrics


def _print_human_report(metrics: dict) -> None:
    print("episteme — Tier 1 advisory soak audit")
    print("=" * 60)
    print(f"Telemetry path:     {metrics['telemetry_path']}")
    print(f"Records:            {metrics['record_count']}")
    if metrics.get("parse_errors"):
        print(f"Parse errors:       {metrics['parse_errors']}")
    if metrics["earliest_timestamp"]:
        print(f"Earliest timestamp: {metrics['earliest_timestamp']}")
        print(f"Latest timestamp:   {metrics['latest_timestamp']}")
        print(f"Calendar span:      {metrics['span_days']:.2f} days")
    print(f"Operator-confirmed: {metrics['operator_confirmed_count']}")
    print(f"Reverted within 24h:{metrics['reverted_within_24h_count']}")
    if metrics["rationale_accuracy"] is not None:
        print(
            f"Rationale-accuracy: {metrics['rationale_accuracy']:.2%}"
        )
    else:
        print("Rationale-accuracy: <undefined — zero operator-confirmed records>")

    print()
    print("Thresholds (proposal § 7):")
    t = metrics["thresholds"]
    print(
        f"  min_ops:               {t['min_ops']}"
    )
    print(
        f"  min_days:              {t['min_days']}"
    )
    print(
        f"  min_rationale_accuracy: {t['min_rationale_accuracy']:.0%}"
    )

    print()
    if metrics["soak_gate_open"]:
        print(f"SOAK GATE: OPEN — {metrics['soak_gate_reason']}")
        print(
            "Tier 1 advisory dispatch is active in the live hook for ops "
            "with valid micro-surfaces."
        )
    else:
        print(f"SOAK GATE: CLOSED — {metrics['soak_gate_reason']}")
        print(
            "Tier 1 advisory dispatch is INACTIVE; the hook applies the "
            "strict-block default for every irreversible op until the gate "
            "opens."
        )

    if metrics["pattern_distribution"]:
        print()
        print("Pattern distribution:")
        for pattern, count in sorted(
            metrics["pattern_distribution"].items(),
            key=lambda kv: -kv[1],
        ):
            print(f"  {count:>4}  {pattern}")


def main() -> int:
    return run_tier1_cli(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
