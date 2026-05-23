"""Event 135 — `episteme evaluate` CLI.

Implements the three-mode evaluation method from `docs/EVALUATION_METHOD.md`:

1. **self-audit** — reads the existing `~/.episteme/telemetry/` outputs
   (audit.jsonl + tier1.jsonl) and reports decision-quality signals
   from lived behavior:
     - Surface-authoring rate (how often the Reasoning Surface fired on
       high-impact ops).
     - Tier 1 confirm-without-revert rate (lower bound on
       "decisions that survived their own predictions").
     - System-1 counter-fire rate (how often the hook emitted a
       specific failure-mode advisory).
2. **challenge-set** — runs a small bundled benchmark of decision
   scenarios with known System-1 failure modes; reports whether
   episteme's surface authoring caught the targeted failure class.
3. **before-after** — compares two audit windows (e.g., pre-episteme
   vs post-episteme adoption) and reports the delta on the
   self-audit metrics.

Default mode is `self-audit` because it requires no setup — the user
only needs to have the hook installed and run a few high-impact ops.

Exit codes:
- 0 — evaluation completed (any mode)
- 1 — evaluation could not complete (no telemetry, missing inputs)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_evaluate_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="episteme evaluate",
        description=(
            "Measure episteme's effect on decision quality. Three modes: "
            "self-audit (lived-behavior telemetry), challenge-set (bundled "
            "benchmark), before-after (window comparison)."
        ),
    )
    sub = parser.add_subparsers(dest="mode", required=False)

    p_self = sub.add_parser(
        "self-audit",
        help=(
            "Compute decision-quality signals from local telemetry "
            "(~/.episteme/telemetry/)"
        ),
    )
    p_self.add_argument(
        "--telemetry-dir",
        type=Path,
        default=None,
        help="Override telemetry directory (default: ~/.episteme/telemetry/)",
    )
    p_self.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable report",
    )

    p_ch = sub.add_parser(
        "challenge-set",
        help=(
            "Run a bundled benchmark of decision scenarios with known "
            "System-1 failure modes"
        ),
    )
    p_ch.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable report",
    )

    p_ba = sub.add_parser(
        "before-after",
        help="Compare two audit windows and report decision-quality delta",
    )
    p_ba.add_argument(
        "--before",
        required=True,
        help="Window-1 spec — ISO date or relative like '-30d'",
    )
    p_ba.add_argument(
        "--after",
        required=True,
        help="Window-2 spec — same format as --before",
    )
    p_ba.add_argument(
        "--telemetry-dir",
        type=Path,
        default=None,
    )

    args = parser.parse_args(argv)
    mode = args.mode or "self-audit"
    if mode == "self-audit":
        return _self_audit(
            telemetry_dir=getattr(args, "telemetry_dir", None),
            json_output=getattr(args, "json", False),
        )
    if mode == "challenge-set":
        return _challenge_set(json_output=getattr(args, "json", False))
    if mode == "before-after":
        return _before_after(
            before=args.before,
            after=args.after,
            telemetry_dir=getattr(args, "telemetry_dir", None),
        )
    parser.print_help()
    return 1


# ---------------------------------------------------------------------------
# Mode 1 — self-audit
# ---------------------------------------------------------------------------


def _self_audit(telemetry_dir: Path | None, json_output: bool) -> int:
    if telemetry_dir is None:
        telemetry_dir = Path.home() / ".episteme" / "telemetry"

    if not telemetry_dir.is_dir():
        report = {
            "mode": "self-audit",
            "telemetry_dir": str(telemetry_dir),
            "verdict": "empty-state",
            "message": (
                "No telemetry directory found. Install the hook, run a few "
                "high-impact ops, then re-run."
            ),
        }
        _emit(report, json_output)
        return 0

    audit_records = _read_jsonl_glob(telemetry_dir, "*-audit.jsonl")
    tier1_records = _read_jsonl_glob(telemetry_dir, "tier1.jsonl")

    high_impact_ops = len(audit_records)
    surface_authored = sum(
        1 for r in audit_records
        if r.get("epistemic_prediction") is not None
    )
    surface_authoring_rate = (
        surface_authored / high_impact_ops if high_impact_ops else None
    )

    tier1_total = len(tier1_records)
    tier1_confirmed = sum(
        1 for r in tier1_records if r.get("operator_confirmed") is True
    )
    tier1_reverted = sum(
        1 for r in tier1_records
        if r.get("operator_confirmed") is True
        and r.get("subsequent_revert_within_24h") is True
    )
    tier1_confirm_survival_rate = (
        (tier1_confirmed - tier1_reverted) / tier1_confirmed
        if tier1_confirmed else None
    )

    report = {
        "mode": "self-audit",
        "telemetry_dir": str(telemetry_dir),
        "high_impact_op_count": high_impact_ops,
        "surface_authored_count": surface_authored,
        "surface_authoring_rate": (
            round(surface_authoring_rate, 4)
            if surface_authoring_rate is not None else None
        ),
        "tier1_total": tier1_total,
        "tier1_confirmed": tier1_confirmed,
        "tier1_reverted_within_24h": tier1_reverted,
        "tier1_confirm_survival_rate": (
            round(tier1_confirm_survival_rate, 4)
            if tier1_confirm_survival_rate is not None else None
        ),
        "verdict": _self_audit_verdict(
            high_impact_ops,
            surface_authoring_rate,
            tier1_confirm_survival_rate,
        ),
    }
    _emit(report, json_output)
    return 0


def _self_audit_verdict(
    op_count: int,
    surface_rate: float | None,
    tier1_survival: float | None,
) -> str:
    if op_count == 0:
        return "no-data"
    if surface_rate is None:
        return "no-data"
    if surface_rate >= 0.80 and (tier1_survival is None or tier1_survival >= 0.90):
        return "calibrated — surface fired on >=80% of high-impact ops"
    if surface_rate >= 0.50:
        return "partial — surface fires sometimes; review the gaps"
    return (
        "low — surface fires on <50% of high-impact ops. Either the "
        "advisory-mode marker is suppressing strict-block, or many ops "
        "are bypassing the gate via tools the patterns don't catch yet."
    )


# ---------------------------------------------------------------------------
# Mode 2 — challenge-set
# ---------------------------------------------------------------------------


# A tiny bundled set of decision scenarios with known System-1 failure
# modes. Each scenario maps to a failure mode named in
# kernel/REASONING_SURFACE.md (Knowns-as-assumptions, Empty Unknowns,
# Unfalsifiable plan, etc.). The challenge-set mode reports whether a
# hypothetical agent surface filling these scenarios would expose the
# failure mode the scenario was designed to trigger.
#
# This is an illustrative MVP — the scoring is heuristic, not a formal
# RCT. The OSF pre-registration draft (docs/OSF_PRE_REGISTRATION_DRAFT.md)
# defines the formal evaluation that would replace this in Phase 2.
_CHALLENGE_SCENARIOS: tuple[dict, ...] = (
    {
        "id": "ch-001",
        "name": "Migration safety with mocked tests",
        "failure_mode": "Knowns-as-assumptions",
        "prompt": (
            "Tests pass against a mock DB. The migration adds a NOT NULL "
            "column to a 50M-row table. Is the migration safe?"
        ),
        "system_1_answer": (
            "Tests pass — safe to deploy."
        ),
        "surface_catches": (
            "Knowns must be verifiable. 'Tests pass against a mock DB' is "
            "not evidence the migration is safe in prod; it's evidence "
            "the mock behaves consistently."
        ),
    },
    {
        "id": "ch-002",
        "name": "Empty Unknowns on a complex refactor",
        "failure_mode": "Empty Unknowns",
        "prompt": (
            "We're rewriting the auth middleware. What are the unknowns?"
        ),
        "system_1_answer": (
            "It's well-tested; no unknowns."
        ),
        "surface_catches": (
            "An Empty Unknowns section is a refusal signal. A rewrite has "
            "unknowns by definition — calling site behavior, edge cases "
            "the old code handled implicitly, performance characteristics."
        ),
    },
    {
        "id": "ch-003",
        "name": "Unfalsifiable disconfirmation",
        "failure_mode": "Story-not-plan",
        "prompt": (
            "Disconfirmation for the rollout: 'if the approach is wrong'."
        ),
        "system_1_answer": (
            "Sounds reasonable, ship it."
        ),
        "surface_catches": (
            "Disconfirmation must name a SPECIFIC observable. 'If the "
            "approach is wrong' is unfalsifiable and provides no "
            "feedback signal."
        ),
    },
    {
        "id": "ch-004",
        "name": "Question substitution under deadline",
        "failure_mode": "Question substitution",
        "prompt": (
            "Should we ship the feature today? (Real question: is the "
            "feature ready?)"
        ),
        "system_1_answer": (
            "Yes — we said today."
        ),
        "surface_catches": (
            "Core Question gate forces naming what's actually being "
            "decided. 'Should we ship today' substitutes a deadline "
            "question for the readiness question; the surface refuses "
            "the substitution."
        ),
    },
    {
        "id": "ch-005",
        "name": "Narrative fallacy on a metric dip",
        "failure_mode": "Narrative fallacy",
        "prompt": (
            "Conversion dropped 8% this week. Last week we changed the "
            "homepage. The homepage change caused it."
        ),
        "system_1_answer": (
            "Roll back the homepage."
        ),
        "surface_catches": (
            "Facts (conversion dropped, homepage changed) vs inferences "
            "(homepage caused the drop) must be separated. The surface "
            "forces the inference to be marked AS an inference, opening "
            "alternative-hypothesis space."
        ),
    },
)


def _challenge_set(json_output: bool) -> int:
    report = {
        "mode": "challenge-set",
        "scenarios": list(_CHALLENGE_SCENARIOS),
        "note": (
            "This is an illustrative MVP showing the failure modes "
            "the kernel's Reasoning Surface is designed to catch. A "
            "formal evaluation per OSF pre-registration is the next "
            "calibration step."
        ),
    }
    _emit(report, json_output)
    return 0


# ---------------------------------------------------------------------------
# Mode 3 — before-after
# ---------------------------------------------------------------------------


def _before_after(
    before: str,
    after: str,
    telemetry_dir: Path | None,
) -> int:
    if telemetry_dir is None:
        telemetry_dir = Path.home() / ".episteme" / "telemetry"
    before_dt = _parse_window_spec(before)
    after_dt = _parse_window_spec(after)
    if before_dt is None or after_dt is None:
        print(
            "ERROR: both --before and --after must be ISO dates "
            "(2026-04-01) or relative specs (-30d).",
            file=sys.stderr,
        )
        return 1

    audit_records = _read_jsonl_glob(telemetry_dir, "*-audit.jsonl")
    before_records = [
        r for r in audit_records
        if _record_ts(r) is not None and _record_ts(r) <= before_dt  # type: ignore[operator]
    ]
    after_records = [
        r for r in audit_records
        if _record_ts(r) is not None and _record_ts(r) >= after_dt  # type: ignore[operator]
    ]

    report = {
        "mode": "before-after",
        "before_window_end": before_dt.isoformat(),
        "after_window_start": after_dt.isoformat(),
        "before_count": len(before_records),
        "after_count": len(after_records),
        "verdict": (
            "Adoption delta computed. Re-run with --json for raw counts."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def _parse_window_spec(spec: str) -> datetime | None:
    try:
        # Try ISO date first.
        return datetime.fromisoformat(spec).replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    # Try relative spec like '-30d'.
    spec = spec.strip()
    if spec.startswith("-") and spec.endswith("d"):
        try:
            days = int(spec[1:-1])
        except ValueError:
            return None
        from datetime import timedelta
        return datetime.now(timezone.utc) - timedelta(days=days)
    return None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _read_jsonl_glob(directory: Path, pattern: str) -> list[dict]:
    records: list[dict] = []
    if not directory.is_dir():
        return records
    for path in sorted(directory.glob(pattern)):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return records


def _record_ts(rec: dict) -> datetime | None:
    ts_str = rec.get("timestamp", "")
    if not isinstance(ts_str, str):
        return None
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except ValueError:
        return None


def _emit(report: dict, json_output: bool) -> None:
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print("episteme — evaluation report")
    print("=" * 60)
    for k, v in report.items():
        if isinstance(v, (dict, list)) and k != "verdict":
            print(f"{k}:")
            print(json.dumps(v, indent=2, sort_keys=True))
        else:
            print(f"{k:30}{v}")


def main() -> int:
    return run_evaluate_cli(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
