#!/usr/bin/env python3
"""Phase 2 deferred-discovery triage — sample + extrapolate.

Reads ~/.episteme/framework/deferred_discoveries.jsonl (1,294+ records
as of Event 47), applies structural filters (by flaw_classification,
by Event-38 recency), and emits a 50-record sample for manual
REAL-DEBT / RESOLVED / NOISE classification per POST_SOAK_TRIAGE §2.

Usage:
    python3 tools/sample_deferred.py --summary
    python3 tools/sample_deferred.py --sample 50 > sample.jsonl
    python3 tools/sample_deferred.py --sample 50 --since 2026-04-23T21:23:36Z
    python3 tools/sample_deferred.py --by-class schema-implementation-drift --head 5

The script never modifies the source file.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

DEFAULT_PATH = Path.home() / ".episteme" / "framework" / "deferred_discoveries.jsonl"
EVENT_38_ANCHOR = "2026-04-23T21:23:36+00:00"


def iso_to_dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def load_records(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                print(f"WARN: line {line_no} malformed — skip", file=sys.stderr)
                continue
            if not isinstance(d, dict):
                continue
            payload = d.get("payload") if isinstance(d.get("payload"), dict) else d
            d["_payload"] = payload
            d["_line_no"] = line_no
            out.append(d)
    return out


def filter_since(records: list[dict], since: datetime | None) -> list[dict]:
    if since is None:
        return list(records)
    out = []
    for r in records:
        ts_str = r.get("ts") or r["_payload"].get("logged_at")
        dt = iso_to_dt(ts_str or "") if ts_str else None
        if dt and dt >= since:
            out.append(r)
    return out


def summarize(records: list[dict]) -> dict:
    total = len(records)
    if not total:
        return {"total": 0}
    classes: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    ops: Counter[str] = Counter()
    for r in records:
        p = r["_payload"]
        classes[p.get("flaw_classification", "unknown")] += 1
        statuses[p.get("status", "unknown")] += 1
        op = (p.get("source_op") or {}).get("op_label", "unknown")
        ops[op] += 1
    return {
        "total": total,
        "by_flaw_classification": dict(classes.most_common()),
        "by_status": dict(statuses.most_common()),
        "by_source_op": dict(ops.most_common(10)),
    }


def mention_scan(text: str) -> dict:
    """Lightweight signal extraction on description + observable."""
    lower = text.lower()
    return {
        "mentions_kernel": "kernel/" in lower,
        "mentions_core_hooks": "core/hooks" in lower or "core/hook" in lower,
        "mentions_src": "src/episteme" in lower,
        "mentions_docs": "docs/" in lower,
        "mentions_tests": "tests/" in lower,
        "mentions_event": any(f"event {n}" in lower for n in range(30, 50)),
        "mentions_cp": "cp-" in lower or "cp_" in lower,
        "length_chars": len(text),
    }


def sample_records(records: list[dict], n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    if len(records) <= n:
        return list(records)
    return rng.sample(records, n)


def render_sample(sample: list[dict]) -> list[dict]:
    out = []
    for r in sample:
        p = r["_payload"]
        description = str(p.get("description", ""))
        observable = str(p.get("observable", ""))
        combined = description + "\n" + observable
        out.append({
            "ts": r.get("ts"),
            "logged_at": p.get("logged_at"),
            "flaw_classification": p.get("flaw_classification"),
            "status": p.get("status"),
            "description_snippet": description[:240],
            "observable_snippet": observable[:240],
            "source_op": (p.get("source_op") or {}).get("op_label"),
            "correlation_id": (p.get("source_op") or {}).get("correlation_id"),
            "signals": mention_scan(combined),
            "classification_hint": _classification_hint(combined, p),
            "manual_verdict": "<FILL_ME: REAL-DEBT | RESOLVED | NOISE>",
        })
    return out


def deduplicate(records: list[dict], desc_prefix_chars: int = 120) -> list[dict]:
    """Collapse records by (flaw_classification, description-prefix).
    Returns one representative record per unique key with a
    `_dup_count` field. Sort by dup_count descending."""
    buckets: dict[tuple[str, str], list[dict]] = {}
    for r in records:
        p = r["_payload"]
        key = (
            str(p.get("flaw_classification", "")),
            (str(p.get("description") or ""))[:desc_prefix_chars],
        )
        buckets.setdefault(key, []).append(r)
    out = []
    for bucket in buckets.values():
        rep = bucket[0]
        rep = dict(rep)
        rep["_dup_count"] = len(bucket)
        rep["_earliest_ts"] = min(
            (b.get("ts", "") for b in bucket if b.get("ts")),
            default="",
        )
        rep["_latest_ts"] = max(
            (b.get("ts", "") for b in bucket if b.get("ts")),
            default="",
        )
        out.append(rep)
    out.sort(key=lambda r: r["_dup_count"], reverse=True)
    return out


def render_unique(unique_records: list[dict]) -> list[dict]:
    out = []
    for r in unique_records:
        p = r["_payload"]
        description = str(p.get("description", ""))
        observable = str(p.get("observable", ""))
        combined = description + "\n" + observable
        out.append({
            "dup_count": r.get("_dup_count", 1),
            "earliest_ts": r.get("_earliest_ts"),
            "latest_ts": r.get("_latest_ts"),
            "flaw_classification": p.get("flaw_classification"),
            "description": description,
            "observable": observable,
            "log_only_rationale": p.get("log_only_rationale", ""),
            "source_op": (p.get("source_op") or {}).get("op_label"),
            "signals": mention_scan(combined),
            "classification_hint": _classification_hint(combined, p),
            "manual_verdict": "<FILL_ME: REAL-DEBT | RESOLVED | NOISE>",
        })
    return out


def _classification_hint(text: str, payload: dict) -> str:
    """Heuristic hint — operator makes the final call."""
    lower = text.lower()
    class_ = str(payload.get("flaw_classification", ""))
    # Strong signals that the record describes REAL-DEBT:
    if any(sig in lower for sig in (
        "core/hooks", "core/hook", "src/episteme",
        "reasoning_surface_guard", "episodic_writer",
        "fence_synthesis", "calibration_telemetry",
    )):
        return "likely REAL-DEBT (names current hook code)"
    # Possible RESOLVED via Path A:
    if any(sig in lower for sig in (
        "silent exception", "except exception", "hook never fires",
        "writer never invoked", "posttooluse not registered",
    )):
        return "likely RESOLVED (matches Event 38 Path A scope)"
    if class_ == "schema-implementation-drift":
        return "likely structural (check: schema change may retire batch)"
    if class_ in ("config-gap", "doc-code-drift"):
        return "inspect — often small fix, may be RESOLVED already"
    if "kernel edits" in lower and "ce" in lower:  # cascade-exempt noise
        return "possible NOISE (circular kernel-edit cascade artifact)"
    return "inspect manually"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", default=str(DEFAULT_PATH))
    ap.add_argument("--since", default=None,
                    help=f"ISO-8601 cutoff (e.g. {EVENT_38_ANCHOR})")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=4701)
    ap.add_argument("--by-class", default=None,
                    help="Filter by flaw_classification before sampling")
    ap.add_argument("--head", type=int, default=0,
                    help="Print first N records instead of random sample")
    ap.add_argument("--unique", action="store_true",
                    help="Dedup by (class, desc-prefix) + render all unique findings")
    ap.add_argument("--dedup-prefix", type=int, default=120,
                    help="Char prefix of description used for dedup key")
    args = ap.parse_args()

    records = load_records(Path(args.path))
    since_dt = iso_to_dt(args.since) if args.since else None
    if since_dt:
        records = filter_since(records, since_dt)
    if args.by_class:
        records = [r for r in records
                   if r["_payload"].get("flaw_classification") == args.by_class]

    if args.unique:
        unique = deduplicate(records, desc_prefix_chars=args.dedup_prefix)
        report = {
            "params": {
                "since": args.since,
                "by_class": args.by_class,
                "source_total": len(records),
                "unique_count": len(unique),
                "dedup_ratio": round(len(records) / max(len(unique), 1), 1),
            },
            "unique_findings": render_unique(unique),
        }
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2, default=str)
        sys.stdout.write("\n")
        return 0

    if args.summary or (not args.sample and not args.head):
        summary = summarize(records)
        summary["params"] = {"since": args.since, "by_class": args.by_class}
        json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.head:
        selected = records[: args.head]
    else:
        selected = sample_records(records, args.sample, args.seed)

    report = {
        "params": {
            "path": args.path,
            "since": args.since,
            "by_class": args.by_class,
            "sample_size": len(selected),
            "source_size": len(records),
            "seed": args.seed,
        },
        "sample": render_sample(selected),
    }
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
