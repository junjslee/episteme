"""Marker garbage-collection reaper — Event 146.

TTL-based unlink of orphaned pairing markers in the two pending dirs
(``state/cascade_pending`` + ``state/fence_pending``). Fixes the
unbounded leak the audit named: ``MARKER_TTL_SECONDS`` (defined in
``_fence_synthesis``) previously gated READS only —
``read_pending_marker`` and ``_signature_scan`` skip a stale marker
without unlinking it, so a Pre marker whose Post never pairs is orphaned
forever, and ``_signature_scan`` globs + ``json.loads`` EVERY pending
file on each admitted Post hook, so per-op latency grows with the leak.

## Single-handler (Event 145 B1)

This module is the ONE sweep implementation. Both the SessionStart hook
(``session_context.py``) and the standalone tool
(``tools/fence_marker_cleanup.py``) import ``reap_all`` from here — no
duplicated loop, no duplicated TTL constant. The TTL is reused from
``_fence_synthesis`` so there is a single source of truth for the age
boundary; the two pending-dir paths are reused from the synthesis
modules that own them (``_fence_synthesis._pending_dir`` /
``_cascade_synthesis._pending_dir``).

## Concurrency

Marker files are per-correlation-id JSON written atomically via
``tempfile`` + ``os.replace``; the fence/cascade synthesis docstrings
state the marker dirs are OUTSIDE the rewrite-mutex scope (``fcntl.flock``
is NOT required for them). A parallel session may unlink or pair a marker
mid-sweep, so every ``glob -> stat -> read -> unlink`` step tolerates
``FileNotFoundError`` (skip, never crash). The ledger rewrite mutex
(``_chain.rewrite_lock``) is NOT taken: the lock-order law
(``_chain.py`` § ``rewrite_lock`` docstring) governs chain-file rewrites
under the framework dir, not these marker dirs. Per-file atomic unlink
with exception tolerance is sufficient and cannot deadlock against
appenders, which take only the per-file lock on the chain files.

## Age semantics

A well-formed marker's age is ``now - written_at`` (the payload field) —
byte-identical to the existing TTL read-check (``read_pending_marker`` /
``_signature_scan``), so a marker the reader already treats as
stale/absent is exactly the marker the reaper unlinks. A malformed marker
(unparseable JSON / read error) has no payload age, so the reaper falls
back to file ``mtime``: it is reaped only when it has physically sat on
disk longer than the TTL, which cannot catch a fresh in-flight marker.
The same mtime fallback covers a valid-JSON marker missing or carrying an
unparseable ``written_at`` (schema drift), for the same reason.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _fence_synthesis import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    MARKER_TTL_SECONDS,
    _pending_dir as _fence_pending_dir,
)
from _cascade_synthesis import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    _pending_dir as _cascade_pending_dir,
)


@dataclass
class ReapResult:
    """Per-directory sweep tally.

    - ``reaped``       — markers unlinked because age > TTL.
    - ``kept``         — markers left in place (fresh, or unassessable /
                         unlink-failed and deliberately not force-removed).
    - ``malformed_reaped`` — subset of ``reaped`` whose JSON did not parse
                         (unparseable-JSON count, per requirement 4).
    - ``vanished``     — markers that disappeared mid-sweep (a parallel
                         session unlinked/paired them); skipped, not an error.
    """

    reaped: int = 0
    kept: int = 0
    malformed_reaped: int = 0
    vanished: int = 0


def _marker_age_seconds(path: Path, now: datetime) -> tuple[float | None, bool]:
    """Return ``(age_seconds, malformed)`` for one marker, or
    ``(None, _)`` when the file vanished (``FileNotFoundError`` at stat or
    open) or cannot be assessed. ``malformed`` is True only when the JSON
    itself was unparseable (or unreadable) — matching requirement 4's
    "unparseable JSON" scope.

    Age is ``now - written_at`` when the payload carries a parseable
    ``written_at`` (matches the TTL read-check); otherwise it falls back
    to file ``mtime`` (malformed JSON, non-dict payload, or missing /
    unparseable ``written_at``). Never raises.
    """
    try:
        mtime_ts = path.stat().st_mtime
    except FileNotFoundError:
        return None, False
    except OSError:
        # Unreadable stat (e.g. permissions) — cannot assess; leave it.
        return None, False
    mtime_age = (
        now - datetime.fromtimestamp(mtime_ts, tz=timezone.utc)
    ).total_seconds()

    malformed = False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None, False
    except (OSError, json.JSONDecodeError):
        # Unparseable / unreadable content: age by mtime, flagged malformed.
        return mtime_age, True

    if isinstance(data, dict):
        written = data.get("written_at")
        if isinstance(written, str):
            try:
                wdt = datetime.fromisoformat(written.replace("Z", "+00:00"))
                if wdt.tzinfo is None:
                    wdt = wdt.replace(tzinfo=timezone.utc)
                return (now - wdt).total_seconds(), False
            except ValueError:
                # Unparseable written_at — schema drift, not unparseable
                # JSON. Age by mtime; do NOT flag as malformed.
                return mtime_age, False
    # Non-dict payload or missing written_at: age by mtime, not malformed.
    return mtime_age, False


def reap_dir(
    pending_dir: Path,
    now: datetime | None = None,
    ttl_seconds: int = MARKER_TTL_SECONDS,
) -> ReapResult:
    """Sweep one pending-marker directory, unlinking every marker whose
    age exceeds ``ttl_seconds``. Never raises past its boundary; tolerates
    a missing directory (no-op) and any single file vanishing mid-sweep.
    """
    result = ReapResult()
    if now is None:
        now = datetime.now(timezone.utc)
    if not pending_dir.is_dir():
        return result
    # Materialize the entry list up front so unlinking during iteration
    # cannot perturb the scandir walk, and a directory that vanishes
    # mid-scan degrades to an empty sweep rather than raising.
    try:
        entries = list(pending_dir.glob("*.json"))
    except OSError:
        return result
    for path in entries:
        age, malformed = _marker_age_seconds(path, now)
        if age is None:
            result.vanished += 1
            continue
        if age <= ttl_seconds:
            result.kept += 1
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            # Paired/reaped by a parallel session between read and unlink.
            result.vanished += 1
            continue
        except OSError:
            # Unlink failed for another reason — leave it, do not crash.
            result.kept += 1
            continue
        result.reaped += 1
        if malformed:
            result.malformed_reaped += 1
    return result


def reap_all(
    now: datetime | None = None,
    ttl_seconds: int = MARKER_TTL_SECONDS,
) -> dict[str, ReapResult]:
    """Reap both marker directories. Returns ``{"cascade": ReapResult,
    "fence": ReapResult}``. Never raises."""
    if now is None:
        now = datetime.now(timezone.utc)
    return {
        "cascade": reap_dir(_cascade_pending_dir(), now, ttl_seconds),
        "fence": reap_dir(_fence_pending_dir(), now, ttl_seconds),
    }


def format_summary(results: dict[str, ReapResult]) -> str:
    """One-line human summary shared by the hook banner and the CLI tool
    so the "reaped N cascade + M fence" wording has a single source."""
    cascade = results["cascade"]
    fence = results["fence"]
    malformed = cascade.malformed_reaped + fence.malformed_reaped
    hours = MARKER_TTL_SECONDS // 3600
    line = (
        f"reaped {cascade.reaped} cascade + {fence.reaped} fence markers "
        f"past {hours}h TTL"
    )
    if malformed:
        line += f" ({malformed} malformed)"
    return line


# ---------------------------------------------------------------------------
# Test helpers — expose the reused dir resolvers so tests do not have to
# reach into two private modules.
# ---------------------------------------------------------------------------

def cascade_pending_dir_for_tests() -> Path:
    return _cascade_pending_dir()


def fence_pending_dir_for_tests() -> Path:
    return _fence_pending_dir()
