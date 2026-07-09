#!/usr/bin/env python3
"""SessionStart hook — prints git status, NEXT_STEPS, and Reasoning Surface state.

Output appears at session open so Claude and the operator share the same
starting context without a manual paste.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


SURFACE_TTL_SECONDS = 30 * 60


def _spot_check_line() -> str | None:
    """Return a one-line digest of pending Layer 8 spot-check entries,
    or None when the queue is empty / unreadable.

    Inlined pattern consistent with ``_profile_audit_line`` — the hook
    is a standalone script with no guaranteed sys.path. Graceful
    degrade on any IO / import failure so SessionStart never blocks
    on a degraded queue."""
    _hooks_dir = Path(__file__).resolve().parent
    if str(_hooks_dir) not in sys.path:
        sys.path.insert(0, str(_hooks_dir))
    try:
        import _spot_check  # type: ignore  # pyright: ignore[reportMissingImports]
        pending = _spot_check.count_pending()
    except Exception:
        return None
    if pending <= 0:
        return None
    noun = "surface" if pending == 1 else "surfaces"
    line = f"{pending} {noun} flagged for review — run `episteme review`"
    # Event 148 verification finding — at/over the enqueue cap the samplers
    # skip silently (audit coverage degrades while only the sidecar counter
    # records it); say so on the SAME line rather than adding a producer.
    # Below cap — the normal state — the line is byte-identical to before.
    try:
        cap = _spot_check._resolve_pending_cap()
        if cap and pending >= cap:
            skipped = _spot_check.read_skip_counter().get("skipped_count", 0)
            line += (
                f" — queue AT CAP ({cap}): sampling paused, "
                f"{skipped} op(s) skipped since last drain"
            )
    except Exception:
        pass
    return line


def _last_session_path() -> Path:
    import os
    home = os.environ.get("EPISTEME_HOME") or str(Path.home() / ".episteme")
    return Path(home) / "state" / "last_session.json"


def _read_last_session_ts() -> str | None:
    """Return the recorded last-session ts, or None on first run."""
    path = _last_session_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ts = data.get("last_session_ts") if isinstance(data, dict) else None
    return ts if isinstance(ts, str) and ts else None


def _write_last_session_ts(ts: str) -> None:
    """Best-effort write. Silent on IO failure — the digest line is
    advisory, not load-bearing."""
    path = _last_session_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"last_session_ts": ts}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass


def _noise_watch_line() -> str | None:
    """Phase A · v1.0.1 — surface `noise_watch_set` derived knob at SessionStart.

    Reads the operator's declared noise susceptibilities (e.g.
    status-pressure / false-urgency / regret / social-scripts) from
    `~/.episteme/derived_knobs.json` so the operator opens the session
    already oriented against the dominant failure modes they have
    previously flagged. Advisory-only — never blocks session open.

    Silent when the knobs file is absent, malformed, or the knob is not
    set. Graceful degrade on any import / IO failure: the SessionStart
    banner remains useful even when one producer returns None.

    Kernel anchor: `kernel/OPERATOR_PROFILE_SCHEMA.md` § 5 names
    `noise_watch_set` as a declared derived knob; Event 25 narrative
    names the consumption gap this producer closes.
    """
    _hooks_dir = Path(__file__).resolve().parent
    if str(_hooks_dir) not in sys.path:
        sys.path.insert(0, str(_hooks_dir))
    try:
        import _derived_knobs  # type: ignore  # pyright: ignore[reportMissingImports]
        watch = _derived_knobs.load_knob("noise_watch_set", None)
    except Exception:
        return None
    if not isinstance(watch, list) or not watch:
        return None
    names = [str(x) for x in watch if isinstance(x, str) and x]
    if not names:
        return None
    return f"noise watch: {', '.join(names)}"


def _framework_digest_line() -> str | None:
    """CP9 · 'N protocols synthesized since last session (T total),
    M deferred discoveries pending'. Silent when both counts are zero.

    'Since last session' reads from ``~/.episteme/state/last_session.json``;
    main() updates that file at the end of this hook."""
    _hooks_dir = Path(__file__).resolve().parent
    if str(_hooks_dir) not in sys.path:
        sys.path.insert(0, str(_hooks_dir))
    try:
        import _framework  # type: ignore  # pyright: ignore[reportMissingImports]
        # Event 84 — pass include_superseded=True so the digest counts
        # ALL synthesis events (including superseded ones). The digest
        # is a "what changed since last session" metric, not a "what's
        # currently active" view; superseded entries still count as
        # synthesis activity worth reporting.
        all_protocols = _framework.list_protocols(include_superseded=True)
        # Resolution layer (2026-07-03): count OPEN (pending AND
        # unverdicted), not raw pending — 233 permanently-pending
        # entries made this banner an unclosable alarm because no
        # resolve path existed. Verdicted findings stop re-firing.
        deferred = _framework.open_deferred_discoveries()
    except Exception:
        return None
    total = len(all_protocols)
    pending_deferred = len(deferred)
    last_ts = _read_last_session_ts()
    if last_ts is None:
        # First session — everything is "new" by definition.
        since_last = total
    else:
        since_last = sum(
            1 for env in all_protocols
            if isinstance(env, dict) and str(env.get("ts") or "") > last_ts
        )
    if total == 0 and pending_deferred == 0:
        return None
    protocol_noun = "protocol" if since_last == 1 else "protocols"
    deferred_noun = "discovery" if pending_deferred == 1 else "discoveries"
    return (
        f"framework: {since_last} {protocol_noun} synthesized since "
        f"last session ({total} total), {pending_deferred} deferred "
        f"{deferred_noun} pending"
    )


_E1_PROTOCOL_FLOOR = 3
_E1_WINDOW_DAYS = 30


def _e1_line() -> str | None:
    """Event 137 — the kernel runs its own falsifiability condition.

    `kernel/FALSIFIABILITY_CONDITIONS.md` § E1 names `< 3 protocols
    after 30 days of normal kernel use` as a falsification condition
    for the active-guidance claim. Until this producer existed, E1 was
    a hand-maintained doc status: the condition fired on live state
    and nothing surfaced it — the kernel enforced disconfirmation on
    the operator's decisions while never evaluating its own. This line
    closes that loop: the framework age comes from the oldest
    framework record, so the check is mechanical, not aspirational.

    Silent when the framework has no records at all (kernel not in
    use), when fewer than 30 days of activity have accrued, or when
    the protocol floor is met."""
    _hooks_dir = Path(__file__).resolve().parent
    if str(_hooks_dir) not in sys.path:
        sys.path.insert(0, str(_hooks_dir))
    try:
        import _framework  # type: ignore  # pyright: ignore[reportMissingImports]
        protocols = _framework.list_protocols(include_superseded=True)
        deferred = _framework.list_deferred_discoveries()
    except Exception:
        return None
    total = len(protocols)
    if total >= _E1_PROTOCOL_FLOOR:
        return None
    earliest: datetime | None = None
    for env in protocols + deferred:
        ts = env.get("ts") if isinstance(env, dict) else None
        if not isinstance(ts, str) or not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if earliest is None or dt < earliest:
            earliest = dt
    if earliest is None:
        return None
    age_days = (datetime.now(timezone.utc) - earliest).days
    if age_days < _E1_WINDOW_DAYS:
        return None
    noun = "protocol" if total == 1 else "protocols"
    return (
        f"falsifiability: E1 FIRED — {total} {noun} synthesized after "
        f"{age_days} days of framework activity (floor: "
        f"{_E1_PROTOCOL_FLOOR} per {_E1_WINDOW_DAYS}d). Active guidance "
        f"is currently aspirational, not operational — see "
        f"kernel/FALSIFIABILITY_CONDITIONS.md § E1."
    )


def _reaper_line() -> str | None:
    """Event 146 · marker GC — TTL-reap orphaned pairing markers once per
    session, off the per-op hot path.

    The live failure this closes: pairing markers leaked unbounded
    (``state/cascade_pending`` ~689 files, ``state/fence_pending`` 235,
    oldest 75x past TTL) because ``MARKER_TTL_SECONDS`` gated marker READS
    only — a Pre marker whose Post never pairs was orphaned forever, and
    ``_signature_scan`` re-globbed + parsed every leaked file on each
    admitted Post hook, so per-op latency grew with the leak. SessionStart
    is the correct home: the sweep runs once per session, never on the hot
    path.

    Performs the sweep as a side effect (the load-bearing work) and
    returns the one-line summary only when at least one marker was reaped,
    so the banner stays silent on the common zero-reap session — matching
    the silent-on-zero convention of the other producers here. Graceful
    degrade to None on any import / IO failure: session open must not
    break on GC bookkeeping.
    """
    _hooks_dir = Path(__file__).resolve().parent
    if str(_hooks_dir) not in sys.path:
        sys.path.insert(0, str(_hooks_dir))
    try:
        import _marker_reaper  # type: ignore  # pyright: ignore[reportMissingImports]
        # Event 148 — the sweep now covers all four unbounded data-growth
        # sinks the E146 audit named (pairing markers + advisory dedup markers
        # + size-capped hooks.log/audit.jsonl rotation + telemetry reap), not
        # just the two pairing-marker dirs. format_sweep_summary returns "" when
        # nothing changed, preserving the silent-on-zero contract.
        summary = _marker_reaper.format_sweep_summary(_marker_reaper.sweep_all())
    except Exception:
        return None
    if not summary:
        return None
    return summary


_DOC_STALENESS_EVENT_LAG = 15
_DOC_STALENESS_DATE_DAYS = 45


def _doc_staleness_line() -> str | None:
    """Event 147 · doc-lifecycle staleness banner.

    Counts tracked ``status=living`` docs whose ``reviewed_as_of`` lags the
    corpus: by more than ``_DOC_STALENESS_EVENT_LAG`` events when the latest
    ``E<n>`` tag is resolvable from ``docs/EVENTS.md``, or (fallback) by more
    than ``_DOC_STALENESS_DATE_DAYS`` days when the marker carries an ISO date
    instead of an event tag. Emits ONE advisory line only when the count is
    positive, so the banner stays silent on the common fresh-corpus session —
    matching the silent-on-zero convention of ``_reaper_line`` and the other
    producers here.

    Read-only and self-contained: globs ``docs/*.md`` and reads line 1 for the
    lifecycle marker rather than importing ``src/episteme`` (the hook runs as a
    standalone script with no guaranteed package path) and never shells out, so
    it adds well under 50ms to SessionStart. Graceful-degrades to None on any
    IO / parse failure — session open must not break on an advisory count. The
    drain is opportunistic: whoever next edits a stale doc bumps its
    ``reviewed_as_of`` (``episteme docs lint`` reminds; it is not a CI failure).
    """
    import re

    try:
        docs_dir = Path("docs")
        if not docs_dir.is_dir():
            return None

        marker_re = re.compile(r"episteme-lifecycle:")
        status_re = re.compile(r"status=([^;\s]+)")
        review_re = re.compile(r"reviewed_as_of=([^;\s]+)")
        event_re = re.compile(r"^E(\d+)$")
        date_re = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")

        # Latest event tag from the EVENTS index, if resolvable. A private
        # symlink whose target is present resolves via is_file(); a broken
        # symlink or absent file leaves latest_event None and the fallback
        # date rule governs.
        latest_event: int | None = None
        events_path = docs_dir / "EVENTS.md"
        try:
            if events_path.is_file():
                text = events_path.read_text(encoding="utf-8", errors="replace")
                nums = [int(m) for m in re.findall(r"\bE(\d+)\b", text)]
                if nums:
                    latest_event = max(nums)
        except OSError:
            latest_event = None

        today = datetime.now(timezone.utc).date()
        # Split the count by which threshold fired so the banner names the
        # actual staleness class. A doc can be stale by event-lag (its marker
        # carries an ``E<n>`` tag and the corpus has advanced past the lag) or
        # by the date fallback (its marker carries an ISO date > the day
        # threshold). Reporting ">15 events" when only the date rule fired is
        # inaccurate (Event 148 · smallfix #1).
        stale_events = 0
        stale_date = 0
        for path in docs_dir.glob("*.md"):
            # Skip symlinks (private planning docs are symlinked, lifecycle-exempt).
            if path.is_symlink():
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    first_line = fh.readline()
            except OSError:
                continue
            if not marker_re.search(first_line):
                continue
            sm = status_re.search(first_line)
            if sm is None or sm.group(1) != "living":
                continue
            rm = review_re.search(first_line)
            if rm is None:
                continue
            reviewed = rm.group(1)

            ev = event_re.match(reviewed)
            if ev is not None:
                if latest_event is None:
                    continue  # event-tagged but no corpus latest to compare
                if latest_event - int(ev.group(1)) > _DOC_STALENESS_EVENT_LAG:
                    stale_events += 1
                continue

            dm = date_re.match(reviewed)
            if dm is not None:
                try:
                    reviewed_date = datetime(
                        int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
                    ).date()
                except ValueError:
                    continue
                if (today - reviewed_date).days > _DOC_STALENESS_DATE_DAYS:
                    stale_date += 1
                continue
            # Unparseable reviewed_as_of: leave for `episteme docs lint`.

        stale = stale_events + stale_date
        if stale <= 0:
            return None
        # Name only the threshold class(es) that actually fired.
        if stale_events and stale_date:
            thresh = (
                f">{_DOC_STALENESS_EVENT_LAG} events or "
                f">{_DOC_STALENESS_DATE_DAYS} days"
            )
        elif stale_date:
            thresh = f">{_DOC_STALENESS_DATE_DAYS} days"
        else:
            thresh = f">{_DOC_STALENESS_EVENT_LAG} events"
        return (
            f"doc-staleness: {stale} living docs unreviewed "
            f"{thresh} — episteme docs lint"
        )
    except Exception:
        return None


_NEXT_STEPS_MAX_CHARS = 8000


def _next_steps_block(path: Path | None = None) -> str | None:
    """Bounded NEXT_STEPS injection (Event 137).

    The file's own contract is 'exact next actions, updated at every
    handoff' with the resume-here block first — so the head of the
    file carries the orientation value and the tail is history.
    Unbounded injection (observed at 240KB, doubled by dual hook
    registration) buries the resume block under stale events: WYSIATI
    applied to the context window itself. Cap at the last newline
    before `_NEXT_STEPS_MAX_CHARS` and say what was omitted."""
    ns = path if path is not None else Path("docs/NEXT_STEPS.md")
    if not ns.exists():
        return None
    try:
        content = ns.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not content:
        return None
    if len(content) > _NEXT_STEPS_MAX_CHARS:
        cut = content.rfind("\n", 0, _NEXT_STEPS_MAX_CHARS)
        if cut <= 0:
            cut = _NEXT_STEPS_MAX_CHARS
        omitted = len(content) - cut
        content = (
            content[:cut]
            + f"\n\n[truncated by session_context: {omitted} more "
            f"chars of history — open docs/NEXT_STEPS.md directly]"
        )
    return f"\n--- docs/NEXT_STEPS.md ---\n{content}"


def run(args: list[str]) -> str:
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def _is_acked_in_store(run_id: str) -> bool:
    """Inline ack-store check (CP-AUDIT-ACK-01 / Event 78). Walks
    ~/.episteme/state/profile_audit_acks.jsonl in order; latest-state-
    per-audit_id wins. Returns True iff the latest entry for ``run_id``
    is a `profile_audit_ack` (and not subsequently revoked).

    Inlined rather than importing src/episteme/_profile_audit_ack.py —
    same pattern as _profile_audit_line below: hooks run as standalone
    scripts with no guaranteed sys.path of src/episteme/.
    """
    path = Path.home() / ".episteme" / "state" / "profile_audit_acks.jsonl"
    if not path.exists():
        return False
    state: str | None = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    rec = json.loads(s)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                payload = rec.get("payload", {})
                if not isinstance(payload, dict):
                    continue
                if payload.get("audit_id") != run_id:
                    continue
                etype = payload.get("type")
                if etype == "profile_audit_ack":
                    state = "ack"
                elif etype == "profile_audit_ack_revoke":
                    state = "revoke"
    except OSError:
        return False
    return state == "ack"


def _profile_audit_line() -> str | None:
    """Return a re-elicitation prompt string from the latest unacknowledged
    profile-audit record, or None when nothing to surface.

    Phase 12 · D3 · re-elicitation not correction. This function only
    reads ~/.episteme/memory/reflective/profile_audit.jsonl; it never
    mutates the operator profile. Operator acks via
    `episteme profile audit ack <run_id>` (lands in a later checkpoint).

    Inlined rather than imported from src/episteme/_profile_audit.py —
    the session_context hook is invoked as a standalone script by the
    host runtime with no guaranteed sys.path setup. Matches the
    "hooks stay self-contained" convention used by reasoning_surface_guard.py
    and calibration_telemetry.py.
    """
    path = Path.home() / ".episteme" / "memory" / "reflective" / "profile_audit.jsonl"
    if not path.exists():
        return None
    last: str | None = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s:
                    last = s
    except OSError:
        return None
    if not last:
        return None
    try:
        record = json.loads(last)
    except json.JSONDecodeError:
        return None
    if not isinstance(record, dict):
        return None
    if record.get("acknowledged", False):
        return None
    drifts = [
        a for a in record.get("axes", [])
        if isinstance(a, dict) and a.get("verdict") == "drift"
    ]
    if not drifts:
        return None
    run_id = record.get("run_id", "unknown")
    # CP-AUDIT-ACK-01 / Event 78: also suppress if the run_id is acked
    # in the ack-store at ~/.episteme/state/profile_audit_acks.jsonl.
    # Inlined per the hooks-stay-self-contained convention — no
    # sys.path setup required.
    if _is_acked_in_store(run_id):
        return None
    if len(drifts) == 1:
        a = drifts[0]
        return (
            f"profile-audit: drift on {a.get('axis_name', '?')} — "
            f"{a.get('reason', 'see audit record')} "
            f"Re-elicit or ack via `episteme profile audit ack {run_id}`."
        )
    if len(drifts) <= 3:
        names = ", ".join(a.get("axis_name", "?") for a in drifts)
        return (
            f"profile-audit: drift on {names} — run "
            f"`episteme profile audit` for details. "
            f"Ack via `episteme profile audit ack {run_id}`."
        )
    return (
        f"profile-audit: drift on {len(drifts)} axes — run "
        f"`episteme profile audit` for details. "
        f"Ack via `episteme profile audit ack {run_id}`."
    )


def _canonical_project_root(cwd: Path) -> Path:
    """Resolve project root via git toplevel with walk fallback. Mirrors
    reasoning_surface_guard._canonical_project_root — duplicated for hook
    isolation. Path-A Event 42 fix."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass
    probe = cwd.resolve() if cwd.exists() else cwd
    for _ in range(8):
        if (probe / ".episteme").is_dir():
            return probe
        if probe.parent == probe:
            break
        probe = probe.parent
    return cwd


def _surface_line() -> str | None:
    path = _canonical_project_root(Path.cwd()) / ".episteme" / "reasoning-surface.json"
    if not path.exists():
        return "surface: none declared — write .episteme/reasoning-surface.json before high-impact ops"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "surface: unreadable .episteme/reasoning-surface.json"

    ts = data.get("timestamp")
    age: int | None = None
    if isinstance(ts, (int, float)):
        age = int(time.time() - float(ts))
    elif isinstance(ts, str) and ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = int(time.time() - dt.timestamp())
        except ValueError:
            age = None

    core_q = str(data.get("core_question") or "").strip() or "(none)"
    if age is None:
        return f"surface: present, no timestamp — core_question: {core_q}"
    if age > SURFACE_TTL_SECONDS:
        mins = age // 60
        return f"surface: STALE ({mins} min old) — refresh before high-impact ops"
    return f"surface: fresh — core_question: {core_q}"


def main() -> int:
    lines: list[str] = []

    # Git context
    if run(["git", "rev-parse", "--is-inside-work-tree"]):
        branch = run(["git", "branch", "--show-current"]) or "detached HEAD"
        status = run(["git", "status", "--short"])
        log = run(["git", "log", "--oneline", "-5"])

        lines.append(f"branch : {branch}")
        if status:
            lines.append(f"changes:\n{status}")
        else:
            lines.append("tree   : clean")
        if log:
            lines.append(f"log    :\n{log}")

    # HARNESS.md if present — tells the agent its operating constraints
    harness = Path("HARNESS.md")
    if harness.exists():
        h_content = harness.read_text().strip()
        if h_content:
            first_line = h_content.split("\n", 1)[0].strip("# ").strip()
            lines.append(f"harness: {first_line}")

    surface_line = _surface_line()
    if surface_line:
        lines.append(surface_line)

    # Phase 12 · profile-audit drift, when present and unacknowledged
    audit_line = _profile_audit_line()
    if audit_line:
        lines.append(audit_line)

    # CP8 · Layer 8 spot-check digest — count of pending entries in
    # ~/.episteme/state/spot_check_queue.jsonl (entries without a
    # verdict and without an active skip).
    spot_line = _spot_check_line()
    if spot_line:
        lines.append(spot_line)

    # CP9 · Pillar 3 framework digest — protocols synthesized since
    # the last session + pending deferred-discovery count. Silent on
    # zero. The "since last" window is maintained via
    # ~/.episteme/state/last_session.json which we update below.
    framework_line = _framework_digest_line()
    if framework_line:
        lines.append(framework_line)

    # Event 137 · E1 self-check — the kernel evaluates its own
    # falsifiability condition against live framework state instead of
    # trusting the hand-maintained doc status.
    e1_line = _e1_line()
    if e1_line:
        lines.append(e1_line)

    # Event 146 · marker GC — TTL-reap orphaned pairing markers once per
    # session, off the per-op hot path. Runs the sweep as a side effect;
    # the line is silent unless at least one marker was reaped.
    reaper_line = _reaper_line()
    if reaper_line:
        lines.append(reaper_line)

    # Event 147 · doc-lifecycle staleness — count living docs whose
    # reviewed_as_of lags the corpus by >15 events (or >45 days when dated).
    # Silent on zero; read-only advisory, drain is opportunistic on next edit.
    doc_staleness_line = _doc_staleness_line()
    if doc_staleness_line:
        lines.append(doc_staleness_line)

    # Phase A · v1.0.1 — noise-watch advisory derived from the operator
    # profile's cognitive.noise_signature axis. Silent when the knob is
    # absent. Ordering: AFTER the framework digest so the cognitive
    # context lands last, closest to the operator's first read.
    noise_line = _noise_watch_line()
    if noise_line:
        lines.append(noise_line)

    # NEXT_STEPS.md if present — bounded read (Event 137).
    ns_block = _next_steps_block()
    if ns_block:
        lines.append(ns_block)

    if lines:
        separator = "─" * 60
        print(f"\n{separator}")
        print("\n".join(lines))
        print(separator)

    # CP9 · update the last-session marker so the NEXT SessionStart's
    # "since last" window starts here.
    _write_last_session_ts(datetime.now(timezone.utc).isoformat())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
