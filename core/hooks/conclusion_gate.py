#!/usr/bin/env python3
"""Stop hook — one-shot conclusion nudge (Event 139 · v2.0).

Companion to `conclusion_guard.py`. When the prompt that started this
turn asked for a load-bearing conclusion (marker present), the turn is
ending, and no fresh interrogation verdict exists, this hook blocks the
stop ONCE with a factual reason naming the interrogation path. The
nudge flag is written BEFORE the block is emitted, so a second Stop in
the same prompt cycle always passes — livelock-proof by construction;
the harness's 8-consecutive-block cap is the backstop, not the
mechanism.

A fresh verdict — `ok` OR `stop` — clears the marker silently: a stop
verdict means the interrogation ran and the honest answer was "don't
proceed," which is the protocol working, not a gap.

Alarm-fatigue discipline: at most one nudge per prompt cycle, zero
output in every other case, `stop_hook_active` short-circuits
unconditionally.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


MARKER_FILENAME = "conclusion-pending.json"
MARKER_TTL_SECONDS = 2 * 60 * 60


def _canonical_project_root(cwd: Path) -> Path | None:
    probe = cwd.resolve() if cwd.exists() else cwd
    for _ in range(8):
        if (probe / ".episteme").is_dir():
            return probe
        if probe.parent == probe:
            return None
        probe = probe.parent
    return None


def _marker_path(root: Path) -> Path:
    return root / ".episteme" / MARKER_FILENAME


def _read_marker(root: Path) -> dict | None:
    p = _marker_path(root)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _clear_marker(root: Path) -> None:
    try:
        _marker_path(root).unlink(missing_ok=True)
    except OSError:
        pass


def _marker_age_seconds(marker: dict) -> float | None:
    ts = marker.get("ts")
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return time.time() - dt.timestamp()
    except ValueError:
        return None


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0

    # Already inside a stop-hook continuation — never compound.
    if payload.get("stop_hook_active"):
        return 0

    cwd = Path(payload.get("cwd") or os.getcwd())
    root = _canonical_project_root(cwd)
    if root is None:
        return 0

    marker = _read_marker(root)
    if marker is None:
        return 0

    session_id = str(payload.get("session_id") or "")
    if str(marker.get("session_id") or "") != session_id:
        return 0

    age = _marker_age_seconds(marker)
    if age is None or age > MARKER_TTL_SECONDS:
        _clear_marker(root)
        return 0

    if marker.get("nudged"):
        # The one nudge for this prompt cycle already happened.
        _clear_marker(root)
        return 0

    # A fresh verdict in either direction means the interrogation ran.
    try:
        import _interrogation  # type: ignore  # pyright: ignore[reportMissingImports]
        i_status, _ = _interrogation.artifact_status(root)
    except Exception:
        i_status = "missing"
    if i_status in ("ok", "stop"):
        _clear_marker(root)
        return 0

    # Nudge once. Flag first, block second — order is the livelock proof.
    marker["nudged"] = True
    try:
        _marker_path(root).write_text(
            json.dumps(marker, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        # If the flag cannot persist, do not block at all — a repeating
        # nudge is worse than a missed one.
        return 0

    head = str(marker.get("prompt_head") or "")[:120]
    reason = (
        f"The prompt for this turn asked for a load-bearing conclusion "
        f"({head!r}). No fresh interrogation verdict exists at "
        f".episteme/interrogation.json. If the answer just delivered "
        f"contains a recommendation the operator will act on, the "
        f"epistemic-interrogation skill produces the verdict artifact "
        f"(tiered claims, factored external verification, argued "
        f"opposition, weakest link, pre-committed disconfirmation) — "
        f"then deliver the conclusion with its verdict. If this turn "
        f"did not deliver a conclusion, end the turn again; this check "
        f"fires once per prompt and is now satisfied."
    )
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
