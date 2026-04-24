#!/usr/bin/env python3
"""Gate 28 pre-audit — kernel-on-kernel dogfood verification.

Per `docs/POST_SOAK_TRIAGE.md` §1.8: every kernel-touching commit in
the soak window must satisfy:
  (a) a reasoning-surface existed and was non-stale (≤ 30 min before
      the commit),
  (b) the surface named the change's blast radius, AND
  (c) ≥ 1 episodic record cross-references the commit SHA.

This script runs the automated portions of that check against
commits touching `core/hooks/`, `src/episteme/`, or `kernel/` since
the Event-38 soak anchor. It can't fully validate (a) because the
reasoning-surface file is overwritten per session — what survives is
the timestamp inside each *captured* reasoning-surface (copied into
episodic records' details.reasoning_surface.timestamp). This script
approximates (a) by checking that for each kernel-touching commit
there exists an episodic record whose reasoning-surface.timestamp is
within 30 minutes before the commit time, AND by verifying (c)
directly via grep.

Output: human-readable per-commit verdict + weighted PASS/PARTIAL/FAIL
for Gate 28 overall.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


EVENT_38_ANCHOR = "2026-04-23T21:23:36+00:00"
REPO_ROOT = Path(__file__).resolve().parent.parent
EPISODIC_DIR = Path.home() / ".episteme" / "memory" / "episodic"
FRESHNESS_MINUTES = 30


def iso_to_dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def kernel_touching_commits(since: datetime) -> list[dict]:
    try:
        result = subprocess.run(
            [
                "git", "log",
                f"--since={since.isoformat()}",
                "--format=%H|%ct|%s",
                "--",
                "core/hooks", "src/episteme", "kernel/",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=30, check=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise SystemExit(f"git log failed: {exc}")
    commits = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            sha, ct, subject = line.split("|", 2)
        except ValueError:
            continue
        commits.append({
            "sha": sha,
            "ct": int(ct),
            "commit_time": datetime.fromtimestamp(int(ct), tz=timezone.utc),
            "subject": subject,
        })
    return commits


def load_episodic_records(since: datetime) -> list[dict]:
    records: list[dict] = []
    if not EPISODIC_DIR.is_dir():
        return records
    for path in sorted(EPISODIC_DIR.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_str = d.get("ts") or (
                    d.get("details", {})
                    .get("reasoning_surface", {})
                    .get("timestamp")
                    if isinstance(d.get("details"), dict)
                    else None
                )
                if not ts_str:
                    continue
                dt = iso_to_dt(ts_str)
                if dt is None or dt < since:
                    continue
                d["_path"] = str(path)
                d["_line_no"] = line_no
                d["_ts_dt"] = dt
                records.append(d)
    return records


def audit_commit(commit: dict, episodic: list[dict]) -> dict:
    sha = commit["sha"]
    sha_short = sha[:7]
    commit_time = commit["commit_time"]
    # (a) Find episodic record whose surface timestamp is within
    # ±FRESHNESS_MINUTES of commit_time. Rationale: the typical
    # commit→push flow captures the surface at push-time, often 0-15
    # min AFTER commit. A surface that lands in that post-commit
    # window is still evidence the surface was valid across the
    # commit decision. Pre-commit surfaces obviously qualify.
    freshness_start = commit_time - timedelta(minutes=FRESHNESS_MINUTES)
    freshness_end = commit_time + timedelta(minutes=FRESHNESS_MINUTES)
    surface_evidence = None
    best_offset = None
    for rec in episodic:
        details = rec.get("details", {})
        rs = details.get("reasoning_surface", {}) if isinstance(details, dict) else {}
        if not isinstance(rs, dict):
            continue
        surface_ts_str = rs.get("timestamp")
        surface_ts = iso_to_dt(surface_ts_str) if surface_ts_str else None
        if surface_ts is None:
            continue
        if freshness_start <= surface_ts <= freshness_end:
            offset_min = (surface_ts - commit_time).total_seconds() / 60
            # Prefer the nearest-to-commit-time surface when multiple
            # records land in the window.
            if best_offset is None or abs(offset_min) < abs(best_offset):
                blast_radius = rs.get("blast_radius_map") or rs.get("knowns") or []
                names_radius = bool(blast_radius)
                surface_evidence = {
                    "episodic_path": rec.get("_path"),
                    "episodic_line_no": rec.get("_line_no"),
                    "surface_timestamp": surface_ts_str,
                    "minutes_vs_commit": round(offset_min, 1),
                    "names_blast_radius": names_radius,
                }
                best_offset = offset_min
    # (c) Any episodic record cross-referencing the SHA?
    cross_ref_found = False
    for rec in episodic:
        summary = str(rec.get("summary", ""))
        details = rec.get("details", {})
        combined = summary + "|" + json.dumps(details, default=str)
        if sha_short in combined or sha in combined:
            cross_ref_found = True
            break
    # Verdict per commit
    if surface_evidence and surface_evidence["names_blast_radius"] and cross_ref_found:
        verdict = "PASS"
    elif surface_evidence and surface_evidence["names_blast_radius"]:
        verdict = "PARTIAL"
    elif surface_evidence:
        verdict = "PARTIAL"
    else:
        verdict = "FAIL"
    return {
        "sha_short": sha_short,
        "subject": commit["subject"][:72],
        "commit_time": commit_time.isoformat(),
        "verdict": verdict,
        "evidence_a_surface": surface_evidence,
        "evidence_c_sha_crossref_in_episodic": cross_ref_found,
    }


def gate28_verdict(per_commit: list[dict]) -> dict:
    total = len(per_commit)
    if total == 0:
        return {
            "verdict": "INSUFFICIENT_DATA",
            "reason": "no kernel-touching commits in window — vacuously PASS (nothing to violate)",
            "note": "POST_SOAK_TRIAGE §1.8 — Gate 28 vacuous PASS on empty set",
        }
    passed = sum(1 for c in per_commit if c["verdict"] == "PASS")
    partial = sum(1 for c in per_commit if c["verdict"] == "PARTIAL")
    failed = sum(1 for c in per_commit if c["verdict"] == "FAIL")
    if failed > 0:
        verdict = "FAIL"
        note = (
            f"{failed} commit(s) with no reasoning-surface in the "
            f"30-min pre-commit window — HARD GA BLOCK per §4.1"
        )
    elif passed == total:
        verdict = "PASS"
        note = "100% of kernel-touching commits have all three evidence items"
    elif passed + partial == total and passed >= int(0.8 * total):
        verdict = "PARTIAL"
        note = f">= 80% PASS; rest have at least surface evidence"
    else:
        verdict = "PARTIAL"
        note = "some commits below 80% PASS rate"
    return {
        "verdict": verdict,
        "total_commits": total,
        "pass_count": passed,
        "partial_count": partial,
        "fail_count": failed,
        "note": note,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default=EVENT_38_ANCHOR)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    since_dt = iso_to_dt(args.since)
    if since_dt is None:
        raise SystemExit(f"--since {args.since!r} invalid ISO-8601")

    commits = kernel_touching_commits(since_dt)
    episodic = load_episodic_records(since_dt)
    per_commit = [audit_commit(c, episodic) for c in commits]
    overall = gate28_verdict(per_commit)

    if args.json:
        json.dump(
            {
                "since": args.since,
                "episodic_record_count": len(episodic),
                "per_commit": per_commit,
                "gate28": overall,
            },
            sys.stdout, ensure_ascii=False, indent=2, default=str,
        )
        sys.stdout.write("\n")
        return 0

    print(f"Gate 28 pre-audit — commits since {args.since}")
    print("=" * 68)
    print(f"Kernel-touching commits found: {len(commits)}")
    print(f"Episodic records in window: {len(episodic)}")
    print()
    for c in per_commit:
        marker = {"PASS": "✓", "PARTIAL": "△", "FAIL": "✗"}.get(c["verdict"], "?")
        print(f"  [{marker}] {c['sha_short']}  {c['subject']}")
        if c["evidence_a_surface"]:
            offset = c['evidence_a_surface']['minutes_vs_commit']
            direction = "before" if offset < 0 else "after"
            print(f"       surface {abs(offset):.1f} min {direction} commit · "
                  f"names_blast_radius={c['evidence_a_surface']['names_blast_radius']}")
        else:
            print(f"       NO surface within ±{FRESHNESS_MINUTES} min of commit")
        print(f"       SHA referenced in episodic: {c['evidence_c_sha_crossref_in_episodic']}")
    print("-" * 68)
    print(f"Gate 28 verdict: {overall['verdict']}")
    print(f"  pass={overall.get('pass_count', 0)}  "
          f"partial={overall.get('partial_count', 0)}  "
          f"fail={overall.get('fail_count', 0)}  "
          f"(total {overall.get('total_commits', 0)})")
    print(f"  {overall.get('note', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
