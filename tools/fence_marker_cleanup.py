#!/usr/bin/env python3
"""CP-FENCE-01 Fix B — drop stale fence_pending markers past TTL.

Walks ``~/.episteme/state/fence_pending/`` and removes markers whose
``written_at`` timestamp is older than MARKER_TTL_SECONDS (24 hours,
matching ``core/hooks/_fence_synthesis.py``). Corrupt markers with
unparseable timestamps are also removed — a legitimate fence-synthesis
PostToolUse would have deleted them by now.

Prints a one-line summary to stderr and exits 0 on success.

Safe to run repeatedly; idempotent.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


MARKER_TTL_SECONDS = 24 * 60 * 60


def cleanup(pending_dir: Path) -> dict:
    removed = 0
    kept = 0
    parse_failures = 0
    if not pending_dir.is_dir():
        return {"removed": 0, "kept": 0, "parse_failures": 0,
                "reason": "pending dir absent"}
    now = datetime.now(timezone.utc)
    for path in sorted(pending_dir.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            parse_failures += 1
            path.unlink(missing_ok=True)
            removed += 1
            continue
        written = data.get("written_at") if isinstance(data, dict) else None
        age = float("inf")
        if isinstance(written, str):
            try:
                dt = datetime.fromisoformat(written.replace("Z", "+00:00"))
                age = (now - dt).total_seconds()
            except ValueError:
                pass
        if age > MARKER_TTL_SECONDS:
            path.unlink(missing_ok=True)
            removed += 1
        else:
            kept += 1
    return {"removed": removed, "kept": kept, "parse_failures": parse_failures}


def main() -> int:
    pending = Path.home() / ".episteme" / "state" / "fence_pending"
    result = cleanup(pending)
    print(
        f"fence_marker_cleanup: removed={result['removed']} "
        f"kept={result['kept']} parse_failures={result['parse_failures']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
