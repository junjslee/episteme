"""Tier 2.2 — `episteme status [--watch] [--json] [--interval=N]`.

Read-only runtime-state TUI. One-shot or watch-mode visibility into the
kernel's internal state:

- Reasoning Surface freshness (path + age + TTL + structural validity).
- Active branch (today: 'default'; future: per docs/SPEC_REASONING_SURFACE_BRANCHING.md).
- Operator profile drift (from the most recent profile audit, if available).
- Framework stream counts (pending deferred discoveries, protocols synthesized).
- Active rigor level (today: read .episteme/rigor or ~/.episteme/rigor; default 'medium').

Read-only — never mutates kernel state. Designed for the operator to
glance at while working ("is the surface fresh? what's pending?")
without disrupting the gate's hot path. Each tick of `--watch` runs in
the operator's own process; the PreToolUse latency budget is unaffected.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_INTERVAL_SECONDS = 2.0
DEFAULT_SURFACE_TTL_MIN = 30
RIGOR_LEVELS = ("low", "medium", "high")


def _safe_read_json(path: Path) -> dict | None:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return None


def _surface_path(cwd: Path) -> Path:
    """Resolve the active surface path. Today: always default surface;
    future: read .episteme/reasoning-surface.active per the branching spec."""
    return cwd / ".episteme" / "reasoning-surface.json"


def _active_branch(cwd: Path) -> str:
    active_marker = cwd / ".episteme" / "reasoning-surface.active"
    if active_marker.exists():
        try:
            branch = active_marker.read_text().strip()
            if branch:
                return branch
        except OSError:
            pass
    return "default"


def _rigor_level(cwd: Path) -> tuple[str, str]:
    """Return (level, scope) where level ∈ {low, medium, high} and scope
    ∈ {'project', 'global', 'default'}."""
    project_path = cwd / ".episteme" / "rigor"
    if project_path.exists():
        try:
            level = project_path.read_text().strip().lower()
            if level in RIGOR_LEVELS:
                return level, "project"
        except OSError:
            pass
    home_path = Path.home() / ".episteme" / "rigor"
    if home_path.exists():
        try:
            level = home_path.read_text().strip().lower()
            if level in RIGOR_LEVELS:
                return level, "global"
        except OSError:
            pass
    return "medium", "default"


def _validate_surface(surface: dict) -> str:
    """Cheap structural check — does the surface have the fallback
    fields? Returns 'pass' / 'incomplete'."""
    required = (
        "core_question", "knowns", "unknowns",
        "assumptions", "disconfirmation",
    )
    if all(field in surface for field in required):
        return "pass"
    return "incomplete"


def _surface_status(cwd: Path) -> dict[str, Any]:
    path = _surface_path(cwd)
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "age_minutes": None,
            "ttl_minutes": DEFAULT_SURFACE_TTL_MIN,
            "fresh": False,
            "validation": "absent",
            "core_question": "",
            "domain": "",
            "posture_selected": "",
        }
    surface = _safe_read_json(path)
    if surface is None:
        return {
            "path": str(path),
            "exists": True,
            "age_minutes": None,
            "ttl_minutes": DEFAULT_SURFACE_TTL_MIN,
            "fresh": False,
            "validation": "unparseable",
            "core_question": "",
            "domain": "",
            "posture_selected": "",
        }
    ts_str = (surface.get("timestamp") or "").replace("Z", "+00:00")
    try:
        ts = datetime.fromisoformat(ts_str)
        age = (datetime.now(timezone.utc) - ts).total_seconds() / 60.0
    except (ValueError, TypeError):
        age = None
    fresh = (age is not None and age < DEFAULT_SURFACE_TTL_MIN)
    return {
        "path": str(path),
        "exists": True,
        "age_minutes": round(age, 1) if age is not None else None,
        "ttl_minutes": DEFAULT_SURFACE_TTL_MIN,
        "fresh": fresh,
        "validation": _validate_surface(surface),
        "core_question": surface.get("core_question", ""),
        "domain": surface.get("domain", ""),
        "posture_selected": surface.get("posture_selected", ""),
    }


def _framework_counts() -> dict[str, int | None]:
    """Read framework streams (~/.episteme/framework/*.jsonl). Returns
    None per stream when absent or unreadable. Reads from operator-home,
    not cwd-relative — framework streams are operator-scoped, not project-scoped."""
    home = Path.home() / ".episteme" / "framework"
    counts: dict[str, int | None] = {}
    for stream in ("protocols", "deferred_discoveries"):
        path = home / f"{stream}.jsonl"
        if not path.exists():
            counts[stream] = None
            continue
        try:
            with path.open() as f:
                counts[stream] = sum(1 for _ in f)
        except OSError:
            counts[stream] = None
    return counts


def _profile_drift() -> dict[str, Any]:
    """Best-effort profile-drift snapshot. Reads from ~/.episteme/state/
    (operator-scoped). Returns dict with 'available' flag + drift_axes
    (list or None) + last_audit (str or None)."""
    audit_path = Path.home() / ".episteme" / "state" / "last_profile_audit.json"
    audit = _safe_read_json(audit_path)
    if not audit:
        return {"available": False, "drift_axes": None, "last_audit": None}
    return {
        "available": True,
        "drift_axes": audit.get("drift_axes") or [],
        "last_audit": audit.get("timestamp"),
    }


def gather_status(cwd: Path | None = None) -> dict[str, Any]:
    """Single source of truth for the status payload. Tested in isolation."""
    cwd = cwd or Path.cwd()
    rigor_level, rigor_scope = _rigor_level(cwd)
    return {
        "cwd": str(cwd),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "surface": _surface_status(cwd),
        "branch": _active_branch(cwd),
        "rigor": {"level": rigor_level, "scope": rigor_scope},
        "framework": _framework_counts(),
        "profile_drift": _profile_drift(),
    }


def format_status_text(status: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"episteme status — {status['cwd']}")
    lines.append("")

    s = status["surface"]
    lines.append("Reasoning Surface")
    lines.append(f"  path:       {s['path']}")
    if not s["exists"]:
        lines.append("  status:     ABSENT — no surface declared")
    elif s["age_minutes"] is None:
        lines.append("  status:     PRESENT but unparseable timestamp")
    else:
        fresh_marker = "fresh" if s["fresh"] else "STALE"
        lines.append(
            f"  age:        {s['age_minutes']} min "
            f"(TTL {s['ttl_minutes']} min — {fresh_marker})"
        )
        lines.append(f"  validation: {s['validation']}")
        if s.get("core_question"):
            cq = s["core_question"]
            if len(cq) > 100:
                cq = cq[:97] + "..."
            lines.append(f"  question:   {cq}")
        if s.get("posture_selected"):
            lines.append(f"  posture:    {s['posture_selected']}")
    lines.append("")

    lines.append(f"Branch:    {status['branch']}")
    lines.append(f"Rigor:     {status['rigor']['level']} ({status['rigor']['scope']})")
    lines.append("")

    fw = status["framework"]
    lines.append("Framework")
    proto = fw.get("protocols")
    deferred = fw.get("deferred_discoveries")
    lines.append(
        f"  protocols synthesized:  "
        f"{proto if proto is not None else '(stream absent)'}"
    )
    lines.append(
        f"  deferred discoveries:   "
        f"{deferred if deferred is not None else '(stream absent)'}"
    )
    lines.append("")

    pd = status["profile_drift"]
    lines.append("Operator Profile")
    if not pd["available"]:
        lines.append("  audit:      not yet run (try: episteme profile audit --write)")
    else:
        drift = pd["drift_axes"] or []
        if drift:
            lines.append(f"  drift:      {len(drift)} axes — {', '.join(drift)}")
        else:
            lines.append("  drift:      none")
        if pd["last_audit"]:
            lines.append(f"  last audit: {pd['last_audit']}")
    lines.append("")

    lines.append(f"snapshot at {status['timestamp']}")
    return "\n".join(lines)


def format_status_json(status: dict[str, Any]) -> str:
    return json.dumps(status, indent=2, sort_keys=True, default=str)


def run_status(
    *,
    watch: bool = False,
    json_out: bool = False,
    interval: float = DEFAULT_INTERVAL_SECONDS,
    cwd: Path | None = None,
    sleep_fn=time.sleep,
    out=None,
    max_ticks: int | None = None,
) -> int:
    """Status command entry point.

    ``max_ticks`` is a test hook — when set, the watch loop runs at most
    that many ticks before returning. Production callers leave it None
    so the loop runs until KeyboardInterrupt.
    """
    if out is None:
        out = sys.stdout
    if not watch:
        status = gather_status(cwd)
        rendered = (
            format_status_json(status) if json_out else format_status_text(status)
        )
        out.write(rendered + "\n")
        out.flush()
        return 0
    ticks = 0
    try:
        while True:
            status = gather_status(cwd)
            if json_out:
                out.write(format_status_json(status) + "\n")
            else:
                out.write("\033[2J\033[H")  # ANSI clear screen + cursor home
                out.write(format_status_text(status) + "\n")
            out.flush()
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                return 0
            sleep_fn(interval)
    except KeyboardInterrupt:
        return 0
