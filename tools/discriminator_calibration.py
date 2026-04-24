#!/usr/bin/env python3
"""CP-DISC-01 — Form-filling discriminator calibration.

Implements the three sub-metrics from docs/POST_SOAK_TRIAGE.md §1.9 and
runs them against every episodic record in the post-Event-38 soak corpus
(timestamp >= 2026-04-23T21:23:36Z). Produces a per-record JSON report
and a threshold-tuning summary.

Run:
    python3 tools/discriminator_calibration.py
    python3 tools/discriminator_calibration.py --corpus /path/to/records
    python3 tools/discriminator_calibration.py --since 2026-04-23T21:23:36Z

Exit codes:
    0 = ran successfully (reports to stdout)
    1 = no corpus found or empty corpus

The script is deliberately dependency-free (stdlib only) so it runs on
any Python 3.9+ without install. Output is JSON; pipe to `jq` for
analysis.

Thresholds emitted:
    proper_noun_density_chars_per_token     — lower = stricter
    disconfirmation_observable_verb_required — True/False gate
    lazy_token_rejection                     — pattern list
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


EVENT_38_ANCHOR = "2026-04-23T21:23:36+00:00"

LAZY_TOKEN_PATTERN = re.compile(
    r"\b(n/a|tbd|todo|somehow|placeholder|unknown)\b",
    re.IGNORECASE,
)

LAZY_TOKEN_SHORT_FIELD_PATTERN = re.compile(
    r"\b(none|various|misc|generic|maybe|perhaps|later)\b",
    re.IGNORECASE,
)

LAZY_TOKEN_PATTERN_KO = re.compile(
    r"(해당\s*없음|어떻게든)",
)

SHORT_FIELD_THRESHOLD = 50

PROPER_NOUN_PATTERNS = [
    re.compile(r"[A-Za-z_][A-Za-z0-9_/.-]*\.(py|md|ts|tsx|js|jsx|json|yml|yaml|toml|sh|sql|rs|go)\b"),  # file ext
    re.compile(r"\b[a-f0-9]{7,40}\b"),  # SHA-like hex
    re.compile(r"\bGate\s+\d{1,3}\b", re.IGNORECASE),
    re.compile(r"\bG\d{1,3}\b"),
    re.compile(r"\bEvent\s+\d{1,3}\b"),
    re.compile(r"\bCP[-_]?\w{2,}[-_]?\d{2,}\b"),  # CP-TEL-01, CP_FENCE_01
    re.compile(r"\bPR\s*#\d+\b"),
    re.compile(r"(?<![\w/])#\d+(?![\w/])"),
    re.compile(r"\b(git|gh|pnpm|npm|yarn|uv|pip|conda|make|cargo|docker|kubectl|terraform|helm|python|python3|node|bash|zsh)\b"),
    re.compile(r"[./][A-Za-z_][A-Za-z0-9_/.-]{2,}"),  # path-looking tokens
]

OBSERVABLE_VERB_PATTERN = re.compile(
    r"\b(fires?|fails?|returns?|exits?|blocks?|resolves?|matches?|"
    r"emits?|produces?|logs?|writes?|reads?|passes?|hangs?|"
    r"times\s+out|throws?|triggers?|raises?|succeeds?|crashes?|"
    r"exceeds?|contains?|equals?|outputs?|prints?|shows?|"
    r"reports?|stops?|breaks?)\b",
    re.IGNORECASE,
)

OBSERVABLE_VERB_KO = re.compile(
    r"(실패|반환|차단|해결|일치|발생|출력|기록|통과)",
)


def iso_to_dt(s: str) -> datetime | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def coerce_text(v: Any) -> str:
    """Flatten list or object reasoning-surface fields into a scan-ready
    string. Lists are newline-joined, dicts are repr'd — the scan-safe
    conversion matters more than faithfulness here."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        return "\n".join(coerce_text(x) for x in v)
    if isinstance(v, dict):
        return "\n".join(f"{k}: {coerce_text(val)}" for k, val in v.items())
    return str(v)


def count_proper_nouns(text: str) -> int:
    """Sum of proper-noun-like token matches across patterns. Tokens can
    overlap between patterns — this counts hits, not distinct tokens."""
    if not text:
        return 0
    total = 0
    for pat in PROPER_NOUN_PATTERNS:
        total += len(pat.findall(text))
    return total


def has_lazy_tokens(text: str) -> list[str]:
    """Return the list of lazy tokens found (empty = clean).

    Two-tier: hard-lazy patterns always flag (n/a, tbd, todo, somehow,
    placeholder, unknown — these are form-filling even in long content).
    Soft-lazy patterns (none, various, misc, generic, maybe, perhaps,
    later) only flag if the field is short (< SHORT_FIELD_THRESHOLD
    chars) — in long fields these are likely natural-language abbreviations
    not placeholders."""
    found: list[str] = []
    for m in LAZY_TOKEN_PATTERN.finditer(text):
        found.append(m.group(0))
    for m in LAZY_TOKEN_PATTERN_KO.finditer(text):
        found.append(m.group(0))
    stripped = text.strip()
    if len(stripped) < SHORT_FIELD_THRESHOLD:
        for m in LAZY_TOKEN_SHORT_FIELD_PATTERN.finditer(text):
            found.append(m.group(0))
    return found


def has_observable_verb(text: str) -> bool:
    if not text.strip():
        return False
    if OBSERVABLE_VERB_PATTERN.search(text):
        return True
    if OBSERVABLE_VERB_KO.search(text):
        return True
    return False


def score_field(
    text: str,
    is_disconfirmation: bool,
    proper_noun_chars_per_token: float,
) -> dict:
    """Apply three sub-metrics to one field. Returns a dict of per-metric
    booleans plus an aggregate pass/fail."""
    stripped = text.strip()
    length = len(stripped)
    proper_nouns = count_proper_nouns(stripped)
    lazy = has_lazy_tokens(stripped)
    density_ok = True
    density_ratio: float | None = None
    if length >= 30 and proper_noun_chars_per_token > 0:
        target_count = length / proper_noun_chars_per_token
        density_ratio = proper_nouns / max(target_count, 0.001)
        density_ok = proper_nouns >= max(1, int(target_count * 0.5))
    observable_ok = True
    if is_disconfirmation and length >= 15:
        observable_ok = has_observable_verb(stripped)
    score_4 = sum(
        1
        for ok in (
            length >= 15,
            not lazy,
            density_ok,
            observable_ok,
        )
        if ok
    )
    return {
        "length": length,
        "proper_nouns": proper_nouns,
        "density_ratio": density_ratio,
        "density_ok": density_ok,
        "lazy_tokens": lazy,
        "lazy_ok": not lazy,
        "observable_verb_ok": observable_ok,
        "score_out_of_4": score_4,
    }


def load_corpus(corpus_dir: Path, since: datetime) -> list[dict]:
    """Load all records from corpus_dir/*.jsonl whose `ts` >= since.

    Assumes each record has either a top-level `ts` or a
    `details.reasoning_surface.timestamp` field. Records without a
    parseable timestamp are skipped with a warning to stderr."""
    records: list[dict] = []
    if not corpus_dir.is_dir():
        return records
    for path in sorted(corpus_dir.glob("*.jsonl")):
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    print(
                        f"WARN: {path}:{line_no} not valid JSON — skipping",
                        file=sys.stderr,
                    )
                    continue
                ts_str = (
                    d.get("ts")
                    or d.get("details", {}).get("reasoning_surface", {}).get("timestamp")
                    if isinstance(d, dict)
                    else None
                )
                if not ts_str:
                    continue
                dt = iso_to_dt(ts_str)
                if dt is None or dt < since:
                    continue
                records.append({"path": str(path), "line_no": line_no, "record": d})
    return records


def score_record(entry: dict, proper_noun_chars_per_token: float) -> dict:
    rec = entry["record"]
    surface = {}
    if isinstance(rec.get("details"), dict):
        rs = rec["details"].get("reasoning_surface")
        if isinstance(rs, dict):
            surface = rs
    knowns = coerce_text(surface.get("knowns"))
    unknowns = coerce_text(surface.get("unknowns"))
    assumptions = coerce_text(surface.get("assumptions"))
    disconf = coerce_text(surface.get("disconfirmation"))
    fields = {
        "knowns": score_field(knowns, False, proper_noun_chars_per_token),
        "unknowns": score_field(unknowns, False, proper_noun_chars_per_token),
        "assumptions": score_field(assumptions, False, proper_noun_chars_per_token),
        "disconfirmation": score_field(disconf, True, proper_noun_chars_per_token),
    }
    avg_score = sum(f["score_out_of_4"] for f in fields.values()) / 4.0
    form_filling_failure_count = sum(
        1 for f in fields.values() if (f["lazy_tokens"] or not f["density_ok"] or not f["observable_verb_ok"])
    )
    return {
        "path": entry["path"],
        "line_no": entry["line_no"],
        "summary": rec.get("summary", ""),
        "core_question_snippet": coerce_text(surface.get("core_question"))[:120],
        "fields": fields,
        "avg_field_score": avg_score,
        "form_filling_failure_count": form_filling_failure_count,
    }


def aggregate(results: list[dict]) -> dict:
    if not results:
        return {"n": 0}
    n = len(results)
    avg_scores = [r["avg_field_score"] for r in results]
    ff_rates = [r["form_filling_failure_count"] / 4 for r in results]
    gate_21_bands = {
        "PASS (avg >= 3.2)": sum(1 for s in avg_scores if s >= 3.2),
        "PARTIAL (2.4 <= avg < 3.2)": sum(1 for s in avg_scores if 2.4 <= s < 3.2),
        "FAIL (avg < 2.4)": sum(1 for s in avg_scores if s < 2.4),
    }
    ff_rate_overall = sum(ff_rates) / n
    ff_rate_records_above_40pct = sum(1 for r in ff_rates if r > 0.4)
    lazy_records = sum(
        1
        for r in results
        if any(r["fields"][f]["lazy_tokens"] for f in r["fields"])
    )
    observable_misses = sum(
        1 for r in results if not r["fields"]["disconfirmation"]["observable_verb_ok"]
    )
    density_misses = sum(
        1
        for r in results
        if sum(0 if r["fields"][f]["density_ok"] else 1 for f in r["fields"]) >= 2
    )
    return {
        "n": n,
        "gate_21_bands": gate_21_bands,
        "avg_of_avg_scores": sum(avg_scores) / n,
        "form_filling_rate_overall": ff_rate_overall,
        "records_above_40pct_failure": ff_rate_records_above_40pct,
        "records_with_any_lazy_token": lazy_records,
        "records_failing_observable_verb": observable_misses,
        "records_failing_density_on_2plus_fields": density_misses,
    }


SYNTHETIC_LAZY_CASES: list[dict] = [
    {
        "name": "all-placeholders",
        "expected": "FAIL",
        "surface": {
            "core_question": "What happens?",
            "knowns": "tbd",
            "unknowns": "n/a",
            "assumptions": "none",
            "disconfirmation": "unknown",
        },
    },
    {
        "name": "fluent-but-empty",
        "expected": "FAIL",
        "surface": {
            "core_question": "How does this work?",
            "knowns": "the codebase has been analyzed carefully",
            "unknowns": "some details may need investigation later",
            "assumptions": "the system generally behaves as expected",
            "disconfirmation": "the approach might not work well",
        },
    },
    {
        "name": "abstract-no-proper-nouns",
        "expected": "FAIL",
        "surface": {
            "core_question": "Can we improve quality?",
            "knowns": "the test suite currently passes all cases and the review process ensures quality through peer validation",
            "unknowns": "whether the recent changes to the authentication flow affect throughput under concurrent load is still an open question",
            "assumptions": "the caching layer correctly invalidates entries when the underlying data mutates",
            "disconfirmation": "if throughput drops or if authentication cache misses exceed baseline",
        },
    },
]


def run_self_test(proper_noun_chars_per_token: float) -> int:
    """Validate the discriminator catches synthetic form-filling cases."""
    failures: list[str] = []
    for case in SYNTHETIC_LAZY_CASES:
        fake_record = {
            "summary": f"self-test::{case['name']}",
            "details": {"reasoning_surface": case["surface"]},
        }
        scored = score_record(
            {"path": "<synthetic>", "line_no": 0, "record": fake_record},
            proper_noun_chars_per_token,
        )
        avg = scored["avg_field_score"]
        if case["expected"] == "FAIL" and avg >= 3.2:
            failures.append(
                f"  {case['name']}: expected FAIL but avg_score={avg:.2f}"
                f" (should be < 3.2)"
            )
        elif case["expected"] == "PASS" and avg < 3.2:
            failures.append(
                f"  {case['name']}: expected PASS but avg_score={avg:.2f}"
            )
        print(
            f"[{case['expected']}] {case['name']}: avg_score={avg:.2f} "
            f"lazy_any={sum(1 for f in scored['fields'].values() if f['lazy_tokens'])} "
            f"observable_verb_ok={scored['fields']['disconfirmation']['observable_verb_ok']} "
            f"density_failures={sum(1 for f in scored['fields'].values() if not f['density_ok'])}",
            file=sys.stderr,
        )
    if failures:
        print("\nSELF-TEST FAILURES:", file=sys.stderr)
        for fline in failures:
            print(fline, file=sys.stderr)
        return 1
    print("\nSELF-TEST: all synthetic cases correctly classified.", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--corpus",
        default=str(Path.home() / ".episteme" / "memory" / "episodic"),
        help="Directory containing *.jsonl episodic records",
    )
    ap.add_argument(
        "--since",
        default=EVENT_38_ANCHOR,
        help="Only include records with ts >= this ISO-8601 timestamp",
    )
    ap.add_argument(
        "--density-chars-per-token",
        type=float,
        default=80.0,
        help="Proper-noun density: target chars per proper-noun token",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Emit full per-record JSON (default: aggregate summary only)",
    )
    ap.add_argument(
        "--self-test",
        action="store_true",
        help="Run synthetic-case validation (no corpus scan)",
    )
    args = ap.parse_args()

    if args.self_test:
        return run_self_test(args.density_chars_per_token)

    since = iso_to_dt(args.since)
    if since is None:
        print(f"ERROR: --since '{args.since}' is not valid ISO-8601", file=sys.stderr)
        return 1

    corpus = load_corpus(Path(args.corpus), since)
    if not corpus:
        print(
            f"ERROR: no records in {args.corpus} with ts >= {args.since}",
            file=sys.stderr,
        )
        return 1

    results = [score_record(e, args.density_chars_per_token) for e in corpus]
    summary = aggregate(results)
    out = {
        "params": {
            "corpus": args.corpus,
            "since": args.since,
            "density_chars_per_token": args.density_chars_per_token,
        },
        "summary": summary,
    }
    if args.json:
        out["records"] = results
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
