"""Live runtime-state readers for the viewer dashboard (Event 174).

Pure functions over the two state roots — the operator home
(``$EPISTEME_HOME``, default ``~/.episteme``) and the governed project's
``<root>/.episteme`` — so every reader is unit-testable with an injected
path and the HTTP layer stays a thin route table. All reads are bounded
(tail-limited JSONL, byte-capped text) because the dashboard polls every few
seconds while hooks append per tool call; a reader must never scale with
history length. Every failure degrades to an empty/partial payload — a
dashboard that renders less is correct, one that 500s is not.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

#: Maximum bytes read from the end of a JSONL stream per request.
_TAIL_BYTES = 262_144
#: Reasoning-surface freshness TTL, matching the gate (minutes).
_SURFACE_TTL_MIN = 30
#: Doc-staleness event lag, matching the SessionStart banner.
_DOC_STALENESS_EVENT_LAG = 15


def episteme_home() -> Path:
    return Path(os.environ.get("EPISTEME_HOME") or (Path.home() / ".episteme"))


def tail_jsonl(path: Path, max_lines: int) -> List[dict]:
    """Last ``max_lines`` parseable JSON objects of a JSONL file, oldest first.

    Reads at most :data:`_TAIL_BYTES` from the end of the file, so cost is
    constant regardless of history length; a line straddling the byte
    boundary is dropped (it is the oldest in the window, never the newest).
    """
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > _TAIL_BYTES:
                fh.seek(size - _TAIL_BYTES)
                fh.readline()  # discard the partial first line
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    out: List[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out[-max_lines:]


def _count_lines(path: Path) -> int:
    try:
        with open(path, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def _parse_ts(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def global_status(home: Optional[Path] = None) -> dict:
    """Operator-home panel: gate activity, queues, framework, knobs."""
    home = home or episteme_home()
    now = datetime.now(timezone.utc)

    audit = tail_jsonl(home / "audit.jsonl", 200)
    day_ago_ops = 0
    verdicts: dict = {}
    for rec in audit:
        ts = _parse_ts(rec.get("timestamp") or rec.get("ts"))
        if ts is not None and (now - ts).total_seconds() <= 86_400:
            day_ago_ops += 1
            verdict = str(rec.get("decision") or rec.get("verdict") or "unknown")
            verdicts[verdict] = verdicts.get(verdict, 0) + 1

    knobs: dict = {}
    try:
        knobs = json.loads((home / "derived_knobs.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        knobs = {}

    last_session = None
    try:
        payload = json.loads(
            (home / "state" / "last_session.json").read_text(encoding="utf-8")
        )
        last_session = payload.get("timestamp") or payload.get("ts")
    except (OSError, ValueError):
        last_session = None

    return {
        "generated_at": now.isoformat(),
        "home": str(home),
        "gate_ops_24h": day_ago_ops,
        "gate_verdicts_24h": verdicts,
        "spot_check_pending": _spot_check_pending(home),
        "spot_check_queue": _count_lines(home / "state" / "spot_check_queue.jsonl"),
        "framework": {
            "protocols": _count_lines(home / "framework" / "protocols.jsonl"),
            "deferred_discoveries": _count_lines(
                home / "framework" / "deferred_discoveries.jsonl"
            ),
        },
        "noise_watch": knobs.get("noise_watch_set") or knobs.get("noise_watch") or [],
        "last_session": last_session,
    }


def _spot_check_pending(home: Path) -> Optional[int]:
    """Pending spot-check entries via the queue's OWN semantics.

    The SessionStart banner counts entries still awaiting review
    (``_spot_check.count_pending``), not raw queue lines — replicating that
    filter here would be a second divergent notion of "pending", so the hook
    lib is imported with the repo-root self-resolve pattern instead. ``None``
    when unavailable (installed package without the repo tree); the caller
    also reports the raw line count under its own honestly-named key.
    """
    try:
        repo_root = Path(__file__).resolve().parents[3]
        if (repo_root / "core" / "hooks").is_dir():
            p = str(repo_root)
            if p not in sys.path:
                sys.path.insert(0, p)
        from core.hooks import _spot_check  # noqa: PLC0415

        return _spot_check.count_pending(
            path=home / "state" / "spot_check_queue.jsonl"
        )
    except Exception:
        return None


def _git_branch(root: Path) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return proc.stdout.strip() or None if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _surface_status(root: Path, now: datetime) -> dict:
    path = root / ".episteme" / "reasoning-surface.json"
    out: dict = {"exists": False, "fresh": None, "age_minutes": None,
                 "core_question": None, "posture": None}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    out["exists"] = True
    out["core_question"] = payload.get("core_question")
    out["posture"] = payload.get("posture_selected")
    ts = _parse_ts(payload.get("timestamp"))
    if ts is not None:
        age = (now - ts).total_seconds() / 60.0
        out["age_minutes"] = round(age, 1)
        out["fresh"] = age <= _SURFACE_TTL_MIN
    return out


def _latest_event_number(root: Path) -> Optional[int]:
    try:
        text = (root / "docs" / "EVENTS.md").read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return None
    nums = [int(m) for m in re.findall(r"\bE(\d+)\b", text)]
    return max(nums) if nums else None


def _doc_staleness(root: Path) -> dict:
    """Living-doc lag summary, same rules as the SessionStart banner."""
    docs_dir = root / "docs"
    latest = _latest_event_number(root)
    total_living = 0
    stale = 0
    worst_lag = 0
    if docs_dir.is_dir():
        for path in docs_dir.glob("*.md"):
            if path.is_symlink():
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    first = fh.readline()
            except OSError:
                continue
            if "episteme-lifecycle:" not in first:
                continue
            sm = re.search(r"status=([^;\s]+)", first)
            if sm is None or sm.group(1) != "living":
                continue
            total_living += 1
            rm = re.search(r"reviewed_as_of=E(\d+)", first)
            if rm is None or latest is None:
                continue
            lag = latest - int(rm.group(1))
            worst_lag = max(worst_lag, lag)
            if lag > _DOC_STALENESS_EVENT_LAG:
                stale += 1
    return {
        "latest_event": latest,
        "living_docs": total_living,
        "stale_docs": stale,
        "worst_lag_events": worst_lag,
    }


def _doc_map_stats(root: Path) -> dict:
    """Reverse-index shape for the project (E173), degrade-to-empty."""
    try:
        from episteme import doc_references

        index = doc_references.cached_reverse_index(root)
        return {
            "targets": len(index),
            "edges": sum(len(v) for v in index.values()),
        }
    except Exception:
        return {"targets": None, "edges": None}


def advisories(root: Path, limit: int = 50) -> List[dict]:
    """Recent DOC ADVISORY records for the project, newest last."""
    return tail_jsonl(
        root / ".episteme" / "state" / "doc_advisories.jsonl", limit
    )


def project_status(root: Optional[Path] = None) -> dict:
    """Project panel: git, surface freshness, doc map, doc staleness."""
    root = Path(root) if root is not None else Path.cwd()
    now = datetime.now(timezone.utc)
    recent = advisories(root, limit=50)
    return {
        "generated_at": now.isoformat(),
        "root": str(root),
        "name": root.name,
        "branch": _git_branch(root),
        "surface": _surface_status(root, now),
        "doc_map": _doc_map_stats(root),
        "doc_staleness": _doc_staleness(root),
        "advisories_recent": len(recent),
    }
