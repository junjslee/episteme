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
import os
import sys
from dataclasses import dataclass, field
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

# ---------------------------------------------------------------------------
# Event 148 · LOG-GC — data-growth sinks (siblings of the marker sweep)
# ---------------------------------------------------------------------------
#
# The E146 data-growth audit named four machine-local sinks that grow without
# bound and have no reaper: the per-session advisory dedup markers, the
# hooks.log invocation log, the home audit.jsonl gate-activity log, and the
# per-day telemetry ``*-audit.jsonl`` files. This module already owns the
# proven GC idiom (single shared sweep, silent-on-zero, FileNotFoundError-
# tolerant at every step, age keyed on the same field the readers use,
# imported by ``session_context.py`` at SessionStart). Event 148 EXTENDS that
# idiom with sibling sweeps rather than standing up a second GC mechanism.
#
# Rotation safety (VERIFIED, Event 148): every writer of hooks.log
# (``state_tracker``, ``fence_synthesis``, ``calibration_telemetry``,
# ``episodic_writer``, ``_arm_a_pre``, ``_arm_a_post``) and the sole writer of
# ``audit.jsonl`` (``reasoning_surface_guard._write_audit``) opens the file per
# append with ``open(path, "a")`` — no long-lived handle is held across the
# SessionStart sweep, so ``os.replace`` (atomic rename) cannot corrupt an
# in-flight write. A writer racing the rename simply recreates the file on its
# next append; ``.touch(exist_ok=True)`` after the rename never truncates it.
#
# audit.jsonl is NOT hash-chained (``src/episteme/_report.py`` reader:
# "Raw line reads (no chain verification), consistent with _status.py"), so
# rotating it cannot break any whole-file integrity check — rotation is safe.
# Had the readers verified a hash chain spanning the whole file, rotation would
# have severed it and this sweep would have skipped audit.jsonl and reported the
# coupling instead; the reader evidence is what licenses rotating it here.

# Age boundary for the per-session advisory dedup markers
# (``state/advisory_shown/<id>.marker``): 7 days. Env-overridable.
ADVISORY_SHOWN_TTL_SECONDS = int(
    os.environ.get("EPISTEME_ADVISORY_SHOWN_TTL_SECONDS") or 7 * 24 * 3600
)
# Size caps for the append-only logs. Env-overridable. A file is rotated only
# when it strictly EXCEEDS its cap (``> cap``), so a file sitting exactly at the
# cap is left in place.
HOOKS_LOG_CAP_BYTES = int(
    os.environ.get("EPISTEME_HOOKS_LOG_CAP_BYTES") or 5 * 1024 * 1024
)
AUDIT_LOG_CAP_BYTES = int(
    os.environ.get("EPISTEME_AUDIT_LOG_CAP_BYTES") or 10 * 1024 * 1024
)
# Telemetry ``*-audit.jsonl`` retention: reap files whose mtime is older than
# 30 days, but ALWAYS keep the newest N regardless of age (so a long-idle
# framework never loses its most recent calibration window). Both env-overridable.
TELEMETRY_TTL_SECONDS = int(
    os.environ.get("EPISTEME_TELEMETRY_TTL_SECONDS") or 30 * 24 * 3600
)
TELEMETRY_KEEP_NEWEST = int(
    os.environ.get("EPISTEME_TELEMETRY_KEEP_NEWEST") or 20
)


def _episteme_home() -> Path:
    """Resolve the episteme state root, honoring ``EPISTEME_HOME`` — mirrors
    the resolver the guard / spot-check / pending-marker modules use, so a
    relocated ``EPISTEME_HOME`` keeps ALL sweep targets under one root and
    tests that set ``EPISTEME_HOME`` (or patch ``Path.home``) stay isolated
    from live ``~/.episteme`` state."""
    return Path(os.environ.get("EPISTEME_HOME") or (Path.home() / ".episteme"))


def _advisory_shown_dir() -> Path:
    return _episteme_home() / "state" / "advisory_shown"


def _hooks_log_path() -> Path:
    return _episteme_home() / "state" / "hooks.log"


def _audit_log_path() -> Path:
    return _episteme_home() / "audit.jsonl"


def _telemetry_dir() -> Path:
    return _episteme_home() / "telemetry"


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
# Event 148 · advisory_shown dedup markers — TTL reap
# ---------------------------------------------------------------------------


def _advisory_age_seconds(path: Path, now: datetime) -> float | None:
    """Age of one ``advisory_shown`` marker, or ``None`` when it vanished /
    cannot be assessed. The marker's whole content is the ISO timestamp the
    guard wrote (``reasoning_surface_guard._should_show_full_surface`` writes
    ``datetime.now(timezone.utc).isoformat()``), so age is ``now - <content>``
    — byte-identical semantics to the writer. Falls back to file ``mtime`` when
    the content is empty or not a parseable timestamp. Never raises."""
    try:
        mtime_ts = path.stat().st_mtime
    except FileNotFoundError:
        return None
    except OSError:
        return None
    mtime_age = (now - datetime.fromtimestamp(mtime_ts, tz=timezone.utc)).total_seconds()
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError:
        return mtime_age
    if text:
        try:
            wdt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            if wdt.tzinfo is None:
                wdt = wdt.replace(tzinfo=timezone.utc)
            return (now - wdt).total_seconds()
        except ValueError:
            return mtime_age
    return mtime_age


def reap_advisory_shown(
    now: datetime | None = None,
    ttl_seconds: int = ADVISORY_SHOWN_TTL_SECONDS,
    advisory_dir: Path | None = None,
) -> ReapResult:
    """Unlink every ``advisory_shown/*.marker`` older than ``ttl_seconds``.
    One marker per session accumulates forever (the dedup marker is never
    cleaned by the guard). Missing dir is a no-op; every file step tolerates a
    vanishing file. Never raises."""
    result = ReapResult()
    if now is None:
        now = datetime.now(timezone.utc)
    d = advisory_dir if advisory_dir is not None else _advisory_shown_dir()
    if not d.is_dir():
        return result
    try:
        entries = list(d.glob("*.marker"))
    except OSError:
        return result
    for path in entries:
        age = _advisory_age_seconds(path, now)
        if age is None:
            result.vanished += 1
            continue
        if age <= ttl_seconds:
            result.kept += 1
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            result.vanished += 1
            continue
        except OSError:
            result.kept += 1
            continue
        result.reaped += 1
    return result


# ---------------------------------------------------------------------------
# Event 148 · hooks.log + audit.jsonl — size-capped single-generation rotation
# ---------------------------------------------------------------------------


@dataclass
class RotateResult:
    """Outcome of one size-capped rotation.

    - ``rotated``      — True iff the file exceeded its cap and was rotated to
                         ``<name>.1`` (previous ``.1`` discarded).
    - ``bytes_before`` — size of the file at rotation time (0 when not rotated).
    """

    rotated: bool = False
    bytes_before: int = 0


def rotate_oversized_log(path: Path, cap_bytes: int) -> RotateResult:
    """Rotate ``path`` to ``<path>.1`` when it strictly exceeds ``cap_bytes``,
    keeping exactly ONE archive generation (the prior ``.1`` is atomically
    replaced by ``os.replace``). Never truncates in place: the live file is
    renamed, then recreated empty via ``touch(exist_ok=True)`` — safe because
    every writer opens the log per-append (verified, module docstring), so a
    writer racing the rename recreates the file itself and the touch does not
    clobber it. Missing / sub-cap file is a no-op. Never raises."""
    result = RotateResult()
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return result
    except OSError:
        return result
    if size <= cap_bytes:
        return result
    archive = path.parent / (path.name + ".1")
    try:
        # os.replace atomically overwrites any existing archive, so exactly one
        # generation is kept without a separate unlink step.
        os.replace(path, archive)
    except FileNotFoundError:
        # Rotated/removed by another actor between stat and replace.
        return result
    except OSError:
        return result
    try:
        path.touch(exist_ok=True)
    except OSError:
        pass  # a writer will recreate on next append; recreation is best-effort
    result.rotated = True
    result.bytes_before = size
    return result


# ---------------------------------------------------------------------------
# Event 148 · telemetry *-audit.jsonl — age reap with keep-newest-N floor
# ---------------------------------------------------------------------------


def reap_telemetry(
    now: datetime | None = None,
    ttl_seconds: int = TELEMETRY_TTL_SECONDS,
    keep_newest: int = TELEMETRY_KEEP_NEWEST,
    telemetry_dir: Path | None = None,
) -> ReapResult:
    """Reap ``telemetry/*-audit.jsonl`` files whose ``mtime`` is older than
    ``ttl_seconds``, ALWAYS keeping the newest ``keep_newest`` by mtime
    regardless of age. ``tier1.jsonl`` does not match the glob and is never
    touched. Age keys on ``mtime`` because these are per-day append logs with
    no in-payload age field the readers use. Missing dir is a no-op; every file
    step tolerates a vanishing file. Never raises."""
    result = ReapResult()
    if now is None:
        now = datetime.now(timezone.utc)
    d = telemetry_dir if telemetry_dir is not None else _telemetry_dir()
    if not d.is_dir():
        return result
    try:
        paths = list(d.glob("*-audit.jsonl"))
    except OSError:
        return result
    stamped: list[tuple[float, str, Path]] = []
    for p in paths:
        try:
            mt = p.stat().st_mtime
        except FileNotFoundError:
            result.vanished += 1
            continue
        except OSError:
            result.kept += 1
            continue
        stamped.append((mt, p.name, p))
    # Newest first; name breaks mtime ties deterministically.
    stamped.sort(key=lambda t: (t[0], t[1]), reverse=True)
    floor = max(keep_newest, 0)
    # The newest `floor` files are kept unconditionally (the keep-newest-N floor).
    result.kept += len(stamped[:floor])
    for mt, _name, p in stamped[floor:]:
        age = (now - datetime.fromtimestamp(mt, tz=timezone.utc)).total_seconds()
        if age <= ttl_seconds:
            result.kept += 1
            continue
        try:
            p.unlink()
        except FileNotFoundError:
            result.vanished += 1
            continue
        except OSError:
            result.kept += 1
            continue
        result.reaped += 1
    return result


# ---------------------------------------------------------------------------
# Event 148 · combined sweep + one-line summary (SessionStart carrier)
# ---------------------------------------------------------------------------


@dataclass
class SweepResult:
    """Aggregate of every data-growth sweep run once per session."""

    markers: dict[str, ReapResult] = field(default_factory=dict)
    advisory: ReapResult = field(default_factory=ReapResult)
    hooks_log: RotateResult = field(default_factory=RotateResult)
    audit_log: RotateResult = field(default_factory=RotateResult)
    telemetry: ReapResult = field(default_factory=ReapResult)
    # Resolved boundaries carried for the summary wording.
    advisory_ttl_seconds: int = ADVISORY_SHOWN_TTL_SECONDS
    telemetry_ttl_seconds: int = TELEMETRY_TTL_SECONDS
    telemetry_keep_newest: int = TELEMETRY_KEEP_NEWEST


def sweep_all(now: datetime | None = None) -> SweepResult:
    """Run every Event 146 + 148 data-growth sweep once. Reads the env-
    overridable boundaries at call time so a test (or operator) override takes
    effect without re-import. Never raises past its boundary — each sub-sweep is
    already fail-tolerant, and this wrapper adds no new IO of its own."""
    if now is None:
        now = datetime.now(timezone.utc)
    advisory_ttl = int(
        os.environ.get("EPISTEME_ADVISORY_SHOWN_TTL_SECONDS")
        or ADVISORY_SHOWN_TTL_SECONDS
    )
    hooks_cap = int(
        os.environ.get("EPISTEME_HOOKS_LOG_CAP_BYTES") or HOOKS_LOG_CAP_BYTES
    )
    audit_cap = int(
        os.environ.get("EPISTEME_AUDIT_LOG_CAP_BYTES") or AUDIT_LOG_CAP_BYTES
    )
    telemetry_ttl = int(
        os.environ.get("EPISTEME_TELEMETRY_TTL_SECONDS") or TELEMETRY_TTL_SECONDS
    )
    telemetry_keep = int(
        os.environ.get("EPISTEME_TELEMETRY_KEEP_NEWEST") or TELEMETRY_KEEP_NEWEST
    )
    return SweepResult(
        markers=reap_all(now),
        advisory=reap_advisory_shown(now, advisory_ttl),
        hooks_log=rotate_oversized_log(_hooks_log_path(), hooks_cap),
        audit_log=rotate_oversized_log(_audit_log_path(), audit_cap),
        telemetry=reap_telemetry(now, telemetry_ttl, telemetry_keep),
        advisory_ttl_seconds=advisory_ttl,
        telemetry_ttl_seconds=telemetry_ttl,
        telemetry_keep_newest=telemetry_keep,
    )


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):.1f}MB"


def format_sweep_summary(sweep: SweepResult) -> str:
    """One-line summary of everything the sweep changed, as ``; ``-joined
    segments. Returns "" when nothing was reaped or rotated, so the caller can
    keep the SessionStart banner silent-on-zero. The marker segment reuses
    ``format_summary`` so the "N cascade + M fence" wording has one source."""
    segments: list[str] = []
    m = sweep.markers
    if m:
        marker_reaped = m.get("cascade", ReapResult()).reaped + m.get(
            "fence", ReapResult()
        ).reaped
        if marker_reaped > 0:
            segments.append(f"marker-gc: {format_summary(m)}")
    if sweep.advisory.reaped > 0:
        days = sweep.advisory_ttl_seconds // 86400
        noun = "marker" if sweep.advisory.reaped == 1 else "markers"
        segments.append(
            f"advisory-gc: reaped {sweep.advisory.reaped} dedup {noun} past {days}d TTL"
        )
    rot: list[str] = []
    if sweep.hooks_log.rotated:
        rot.append(f"hooks.log ({_mb(sweep.hooks_log.bytes_before)})")
    if sweep.audit_log.rotated:
        rot.append(f"audit.jsonl ({_mb(sweep.audit_log.bytes_before)})")
    if rot:
        segments.append("log-rotate: " + ", ".join(rot))
    if sweep.telemetry.reaped > 0:
        days = sweep.telemetry_ttl_seconds // 86400
        noun = "file" if sweep.telemetry.reaped == 1 else "files"
        segments.append(
            f"telemetry-gc: reaped {sweep.telemetry.reaped} audit {noun} past "
            f"{days}d (kept newest {sweep.telemetry_keep_newest})"
        )
    return "; ".join(segments)


# ---------------------------------------------------------------------------
# Test helpers — expose the reused dir resolvers so tests do not have to
# reach into two private modules.
# ---------------------------------------------------------------------------

def cascade_pending_dir_for_tests() -> Path:
    return _cascade_pending_dir()


def fence_pending_dir_for_tests() -> Path:
    return _fence_pending_dir()


def advisory_shown_dir_for_tests() -> Path:
    return _advisory_shown_dir()


def hooks_log_path_for_tests() -> Path:
    return _hooks_log_path()


def audit_log_path_for_tests() -> Path:
    return _audit_log_path()


def telemetry_dir_for_tests() -> Path:
    return _telemetry_dir()
