#!/usr/bin/env python3
"""Phase 1 automated gate grader (CP-DISC-01 downstream).

Implements scriptable portions of Gates 21, 23, 24, 26, 28 per
`docs/POST_SOAK_TRIAGE.md`. Gates 22, 25, 27 require human judgment
and/or data sources outside this script's scope — those are reported
as `MANUAL` with the exact counter-example question to prompt the
operator.

Usage:
    python3 tools/grade_gates.py                 # current state
    python3 tools/grade_gates.py --since ISO8601
    python3 tools/grade_gates.py --json          # full JSON report

The script is read-only — never modifies ~/.episteme or repo state.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from discriminator_calibration import (  # type: ignore  # pyright: ignore[reportMissingImports]
    EVENT_38_ANCHOR,
    aggregate,
    iso_to_dt,
    load_corpus,
    score_record,
)

EPISTEME_HOME = Path.home() / ".episteme"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _since_dt(corpus_since: str) -> datetime:
    dt = iso_to_dt(corpus_since)
    if dt is None:
        raise ValueError(f"--since {corpus_since!r} is not valid ISO-8601")
    return dt


def grade_gate_21(corpus_since: str, density_chars_per_token: float) -> dict:
    """Reasoning-Surface snapshot quality — automated via the
    discriminator."""
    records = load_corpus(EPISTEME_HOME / "memory" / "episodic",
                          _since_dt(corpus_since))
    if not records:
        return {
            "gate": 21,
            "verdict": "INSUFFICIENT_DATA",
            "reason": f"no records with ts >= {corpus_since}",
        }
    scored = [score_record(e, density_chars_per_token) for e in records]
    agg = aggregate(scored)
    n = agg["n"]
    avg = agg["avg_of_avg_scores"]
    ff_rate = agg["form_filling_rate_overall"]
    if avg >= 3.2:
        band = "PASS"
    elif avg >= 2.4:
        band = "PARTIAL"
    else:
        band = "FAIL"
    if ff_rate > 0.4:
        band = {"PASS": "PARTIAL", "PARTIAL": "FAIL", "FAIL": "FAIL"}[band]
        downgrade_note = "Downgraded one band due to form-filling rate > 40%"
    else:
        downgrade_note = None
    return {
        "gate": 21,
        "criterion": "reasoning-surface snapshot quality (avg field score >= 3.2/4)",
        "verdict": band,
        "sample_size": n,
        "avg_score": round(avg, 3),
        "form_filling_rate": round(ff_rate, 3),
        "lazy_records": agg["records_with_any_lazy_token"],
        "density_failures": agg["records_failing_density_on_2plus_fields"],
        "downgrade_note": downgrade_note,
        "counter_example_question": (
            "Show me one record where `unknowns` is 15+ chars but "
            "doesn't name a file/command/gate. If such records "
            "dominate → FAIL."
        ),
    }


def grade_gate_22() -> dict:
    """Disconfirmation actually fires — requires manual verification
    against git log. Reports the evidence needed."""
    telemetry_dir = EPISTEME_HOME / "telemetry"
    prediction_count = 0
    outcome_count = 0
    null_exit_count = 0
    if telemetry_dir.is_dir():
        for path in telemetry_dir.glob("*.jsonl"):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    if '"event": "prediction"' in line:
                        prediction_count += 1
                    elif '"event": "outcome"' in line:
                        outcome_count += 1
                        if '"exit_code": null' in line:
                            null_exit_count += 1
    return {
        "gate": 22,
        "criterion": "disconfirmation fires on >= 1 recorded decision with downstream action change",
        "verdict": "MANUAL",
        "telemetry_prediction_count": prediction_count,
        "telemetry_outcome_count": outcome_count,
        "telemetry_null_exit_outcomes": null_exit_count,
        "blocker_if_hooks_broken": (
            f"{null_exit_count}/{outcome_count} outcomes have exit_code=null "
            "(100% ungradeable if this ratio == 1.0) — see CP-TEL-01"
        ) if outcome_count and null_exit_count == outcome_count else None,
        "counter_example_question": (
            "Show me the git commit where we abandoned the original "
            "approach because the disconfirmation fired. If no SHA → FAIL."
        ),
    }


def grade_gate_23(corpus_since: str) -> dict:
    """Facts/inferences/preferences separation — requires human
    classification of `knowns` entries. Reports the record set to
    sample."""
    records = load_corpus(EPISTEME_HOME / "memory" / "episodic",
                          _since_dt(corpus_since))
    return {
        "gate": 23,
        "criterion": "< 10% cross-labeling of facts/inferences/preferences in knowns field",
        "verdict": "MANUAL",
        "candidate_records": len(records),
        "manual_procedure": (
            "For each record's `knowns` field, classify each entry as "
            "(a) fact (grep- or file-verifiable), (b) inference, or (c) "
            "preference. Cross-label rate = (inferences/preferences "
            "mislabeled as knowns) / total knowns."
        ),
        "counter_example_question": (
            "Show me one `knowns` entry that would not survive a `grep` "
            "or `git log` check. If 5+/20 have them → FAIL."
        ),
    }


def grade_gate_24(corpus_since: str) -> dict:
    """Hypothesis -> test -> update — requires manual cross-reference."""
    records = load_corpus(EPISTEME_HOME / "memory" / "episodic",
                          _since_dt(corpus_since))
    hypothesis_present = 0
    for e in records:
        details = e["record"].get("details", {})
        rs = details.get("reasoning_surface", {}) if isinstance(details, dict) else {}
        if isinstance(rs, dict) and rs.get("hypothesis"):
            hypothesis_present += 1
    return {
        "gate": 24,
        "criterion": "hypothesis -> test -> update observable on >= 3 of 5 sampled surfaces",
        "verdict": "MANUAL",
        "records_with_hypothesis": hypothesis_present,
        "total_records": len(records),
        "manual_procedure": (
            "Sample 5 reasoning-surface records with hypothesis field "
            "non-empty. Cross-reference same-session episodic records "
            "for a closing validation / refinement / invalidation note."
        ),
        "counter_example_question": (
            "Which hypothesis this week was honestly invalidated?"
        ),
    }


def grade_gate_25() -> dict:
    """Phase 12 profile-audit — CP-PHASE12-01 resolved Event 47.

    Canonical path: ~/.episteme/memory/reflective/profile_audit.jsonl
    (confirmed via src/episteme/_profile_audit.py docstring D3).
    Produced by `episteme profile audit --write`."""
    audit_path = EPISTEME_HOME / "memory" / "reflective" / "profile_audit.jsonl"
    if not audit_path.is_file():
        return {
            "gate": 25,
            "criterion": ">= 1 real drift detection against operator profile",
            "verdict": "FAIL",
            "reason": (
                f"{audit_path} does not exist — Phase 12 audit has never been "
                "run. Run `episteme profile audit --write` before grading."
            ),
            "counter_example_question": (
                "Name one axis this soak should have flagged based on observed "
                "behavior. If the audit missed it → FAIL (false negative)."
            ),
        }
    audit_records = []
    with open(audit_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                audit_records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    drift_detections = 0
    drifted_axes: list[str] = []
    for rec in audit_records:
        axes = rec.get("axes", []) if isinstance(rec, dict) else []
        for a in axes:
            if not isinstance(a, dict):
                continue
            if a.get("verdict") in ("drift", "promote"):
                drift_detections += 1
                name = a.get("axis_name")
                if name:
                    drifted_axes.append(str(name))
    if drift_detections >= 1:
        verdict = "PASS"
    elif audit_records:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    return {
        "gate": 25,
        "criterion": ">= 1 real drift detection against operator profile",
        "verdict": verdict,
        "audit_records": len(audit_records),
        "drift_detections": drift_detections,
        "drifted_axes": drifted_axes,
        "counter_example_question": (
            "Name one axis this soak should have flagged based on observed "
            "behavior. If the audit missed it → FAIL (false negative)."
        ),
    }


def grade_gate_26() -> dict:
    """Semantic-tier protocol synthesis."""
    protocols_path = EPISTEME_HOME / "framework" / "protocols.jsonl"
    if not protocols_path.is_file():
        return {
            "gate": 26,
            "criterion": ">= 1 reasoning-shape regularity emitted",
            "verdict": "FAIL",
            "reason": f"{protocols_path} does not exist — fence synthesis pipeline is not producing output (see CP-FENCE-01)",
            "counter_example_question": (
                "Which of the emitted protocols would change the agent's "
                "next reasoning-surface if fired? None emitted → FAIL."
            ),
        }
    with open(protocols_path, "r", encoding="utf-8") as f:
        protocols = [json.loads(l) for l in f if l.strip()]
    reasoning_shape_count = 0
    for p in protocols:
        synth_text = str(p.get("payload", {}).get("synthesized_protocol", "")
                         or p.get("synthesized_protocol", ""))
        if any(k in synth_text.lower() for k in
               ("knowns", "unknowns", "assumptions", "disconfirmation",
                "hypothesis", "posture")):
            reasoning_shape_count += 1
    if reasoning_shape_count >= 1:
        verdict = "PASS"
    elif protocols:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    return {
        "gate": 26,
        "criterion": ">= 1 reasoning-shape regularity (protocol references surface fields)",
        "verdict": verdict,
        "total_protocols": len(protocols),
        "reasoning_shape_protocols": reasoning_shape_count,
        "counter_example_question": (
            "Which emitted protocol would change the agent's next "
            "reasoning-surface if fired?"
        ),
    }


def grade_gate_27() -> dict:
    """Failure-mode taxonomy citations in kernel prose (revised Gate 27)."""
    kernel_dir = REPO_ROOT / "kernel"
    docs_design_glob = list((REPO_ROOT / "docs").glob("DESIGN_*.md"))
    failure_mode_ids = [
        "WYSIATI", "question-substitution", "anchoring", "narrative-fallacy",
        "planning-fallacy", "overconfidence", "fence-check", "context-poisoning",
    ]
    citations: dict[str, list[str]] = {fid: [] for fid in failure_mode_ids}
    files_to_check: list[Path] = []
    if kernel_dir.is_dir():
        files_to_check.extend(kernel_dir.glob("*.md"))
    files_to_check.extend(docs_design_glob)
    for path in files_to_check:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for fid in failure_mode_ids:
            if fid.lower() in text.lower():
                citations[fid].append(str(path.relative_to(REPO_ROOT)))
    distinct_ids_cited = sum(1 for files in citations.values() if files)
    multi_file_ids = sum(1 for files in citations.values() if len(set(files)) >= 2)
    if distinct_ids_cited >= 3 and multi_file_ids >= 1:
        verdict = "PASS"
    elif distinct_ids_cited >= 2:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    return {
        "gate": 27,
        "criterion": ">= 3 distinct FAILURE_MODES ids cited load-bearingly in kernel prose",
        "verdict": verdict,
        "distinct_ids_cited": distinct_ids_cited,
        "multi_file_ids": multi_file_ids,
        "citations": {fid: sorted(set(files)) for fid, files in citations.items() if files},
        "manual_check": (
            "If removing FAILURE_MODES.md would leave a 'why does this feature exist' "
            "gap in N files, this is load-bearing. If just footnotes → FAIL."
        ),
    }


def grade_gate_28(corpus_since: str) -> dict:
    """Kernel-on-kernel dogfood. Cross-references soak-window commits
    with reasoning-surface availability at commit time."""
    since = iso_to_dt(corpus_since)
    if since is None:
        return {"gate": 28, "verdict": "INSUFFICIENT_DATA", "reason": "bad --since"}
    try:
        since_iso = since.isoformat()
        result = subprocess.run(
            ["git", "log", f"--since={since_iso}",
             "--format=%H %ct %s", "--",
             "core/hooks", "src/episteme", "kernel/"],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"gate": 28, "verdict": "INSUFFICIENT_DATA",
                "reason": f"git log failed: {exc}"}
    if result.returncode != 0:
        return {"gate": 28, "verdict": "INSUFFICIENT_DATA",
                "reason": result.stderr.strip()}
    kernel_commits = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if not kernel_commits:
        return {
            "gate": 28,
            "criterion": "kernel-touching commits show same discipline as downstream",
            "verdict": "INSUFFICIENT_DATA",
            "reason": "no kernel-touching commits in window — cannot grade dogfood",
            "kernel_commit_count": 0,
            "soft_verdict_if_empty": "PASS (vacuously true — nothing to violate)",
        }
    return {
        "gate": 28,
        "criterion": "kernel-touching commits show same discipline as downstream",
        "verdict": "MANUAL",
        "kernel_commit_count": len(kernel_commits),
        "commits_to_audit": kernel_commits[:10],
        "manual_procedure": (
            "For each commit: verify (a) reasoning-surface existed and "
            "was non-stale within 30 min pre-commit, (b) surface named "
            "the change's blast radius, (c) >= 1 episodic record cross-"
            "references the commit SHA. 100% -> PASS; >= 80% with at "
            "least (a) everywhere -> PARTIAL; any commit with no "
            "surface -> HARD FAIL."
        ),
        "hard_block_note": "Gate 28 FAIL blocks GA regardless of other gates.",
    }


def overall_decision(gate_results: list[dict]) -> dict:
    """Apply POST_SOAK_TRIAGE §4 decision rule."""
    g28 = next((g for g in gate_results if g["gate"] == 28), None)
    if g28 and g28.get("verdict") == "FAIL":
        return {
            "outcome": "HARD_BLOCK",
            "reason": "Gate 28 FAIL = no GA regardless of other gates",
        }
    pass_count = sum(1 for g in gate_results
                     if g["gate"] != 28 and g.get("verdict") == "PASS")
    partial_count = sum(1 for g in gate_results
                        if g["gate"] != 28 and g.get("verdict") == "PARTIAL")
    manual_count = sum(1 for g in gate_results
                       if g["gate"] != 28 and g.get("verdict") == "MANUAL")
    weighted = pass_count + 0.5 * partial_count
    if weighted >= 4:
        outcome = "v1.0.0 GA candidate"
    elif weighted >= 2:
        outcome = "v1.0.1-rc cycle"
    else:
        outcome = "scope retreat candidate"
    return {
        "outcome": outcome,
        "pass_count": pass_count,
        "partial_count": partial_count,
        "manual_count": manual_count,
        "weighted_pass_score": weighted,
        "threshold_to_ga": 4.0,
        "note": (
            f"{manual_count} gates are MANUAL — operator must resolve before "
            f"this decision is final."
        ) if manual_count else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default=EVENT_38_ANCHOR)
    ap.add_argument("--density-chars-per-token", type=float, default=80.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    gates = [
        grade_gate_21(args.since, args.density_chars_per_token),
        grade_gate_22(),
        grade_gate_23(args.since),
        grade_gate_24(args.since),
        grade_gate_25(),
        grade_gate_26(),
        grade_gate_27(),
        grade_gate_28(args.since),
    ]
    decision = overall_decision(gates)

    if args.json:
        report = {
            "params": {
                "since": args.since,
                "density_chars_per_token": args.density_chars_per_token,
                "graded_at": datetime.now(timezone.utc).isoformat(),
            },
            "gates": gates,
            "decision": decision,
        }
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    # Human-friendly summary
    print(f"Phase 1 Gate Grading — since {args.since}")
    print("=" * 68)
    for g in gates:
        v = g.get("verdict", "?")
        marker = {
            "PASS": "✓", "PARTIAL": "△", "FAIL": "✗",
            "MANUAL": "?", "INSUFFICIENT_DATA": "·",
            "HARD_BLOCK": "✗",
        }.get(v, "?")
        print(f"  [{marker}] Gate {g['gate']:>2}: {v:<18} — {g.get('criterion', '')[:50]}")
        for k in ("reason", "blocker", "downgrade_note"):
            if g.get(k):
                print(f"         {k}: {g[k]}")
    print("-" * 68)
    print(f"Decision: {decision['outcome']}")
    print(f"  Weighted pass: {decision.get('weighted_pass_score', 'n/a')} / 4.0 threshold")
    print(f"  Pass: {decision.get('pass_count', 0)}  "
          f"Partial: {decision.get('partial_count', 0)}  "
          f"Manual: {decision.get('manual_count', 0)}")
    if decision.get("note"):
        print(f"  Note: {decision['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
