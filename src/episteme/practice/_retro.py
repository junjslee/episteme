"""`episteme practice retro` — practice retrospective over time window.

Loads signed surfaces from `.episteme/surfaces/`, runs each through the
practice-quality observer (`core.practice.quality.observe_surface`),
aggregates gap observations across the window, and renders the result.

The retrospective is *qualitative*: it lists the most frequent cognitive
moves that were repeatedly shallow or skipped, with severity counts. It
deliberately does NOT produce a single 0-10 "practice score" — that
would induce gaming the score rather than living the practice.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import json
from typing import Dict, List, Optional, cast

# Event 172 — the installed entry point could not import `core.*`
# (repo-root package outside the installed tree), so this command
# CRASHED from the shipped CLI while the docs called it the operator's
# practice UX. Resolve the repo root from this file and put it on
# sys.path before the core imports; a no-op when already importable.
import sys as _sys
from pathlib import Path as _Path
_REPO_ROOT = _Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from core.practice.cognitive_moves import get_move
from core.practice.quality import observe_surfaces, PracticeRetrospective
from episteme import _ui
from episteme._ui import Color
from episteme.evidence._index import iter_index, filter_entries


SEVERITY_ORDER = {"critical": 0, "warn": 1, "advisory": 2, "info": 3}

_SEVERITY_COLORS: Dict[str, Color] = {
    "critical": "red",
    "warn": "yellow",
    "advisory": "yellow",
    "info": "grey",
}


def _format_severity(severity: str) -> str:
    """Color a severity tag."""
    return _ui.colored(severity.upper(), _SEVERITY_COLORS.get(severity, cast(Color, "grey")))


def _render_retrospective(retro: PracticeRetrospective) -> str:
    """Render a PracticeRetrospective as a human-readable terminal report."""
    lines: List[str] = []

    title = "Practice Retrospective"
    if retro.period_from or retro.period_to:
        title += f"  ·  {retro.period_from or 'beginning'} → {retro.period_to or 'now'}"
    lines.append(_ui.header(title, level=1, color="cyan"))
    lines.append("")
    lines.append(f"Surfaces examined:  {retro.surfaces_examined}")
    lines.append(f"Observations:       {len(retro.observations)}")
    lines.append("")

    if retro.surfaces_examined == 0:
        lines.append("(no surfaces in window — nothing to retrospect)")
        return "\n".join(lines)

    # ── Most frequent cognitive-move gaps ──
    lines.append(_ui.header("Most frequent cognitive-move gaps", level=2, color="yellow"))
    lines.append("")
    if not retro.most_frequent_gaps:
        lines.append(_ui.colored("  (no gap patterns — practice is on target)", "green"))
    else:
        for move_id in retro.most_frequent_gaps:
            count = retro.move_gap_counts.get(move_id, 0)
            try:
                move = get_move(move_id)
                lines.append(f"  • {_ui.colored(move.name, 'bold')}  ({count} surface(s))")
                lines.append(_ui.colored(f"      {move.description}", "grey"))
                lines.append(_ui.colored(f"      Counters: {move.system_1_failure_counter}", "grey"))
                lines.append(_ui.colored(f"      Doc:      {move.doc_anchor}", "grey"))
            except KeyError:
                lines.append(f"  • {move_id} ({count})  [unknown move]")
            lines.append("")

    # ── Severity breakdown ──
    severity_counts: Dict[str, int] = {}
    for o in retro.observations:
        severity_counts[o.severity] = severity_counts.get(o.severity, 0) + 1

    lines.append(_ui.header("Observations by severity", level=2, color="grey"))
    lines.append("")
    for sev in ("critical", "warn", "advisory", "info"):
        count = severity_counts.get(sev, 0)
        if count > 0:
            lines.append(f"  {_format_severity(sev):<25} {count}")
    lines.append("")

    # ── Detail (capped) ──
    if retro.observations:
        lines.append(_ui.header("Detail (first 15)", level=2, color="grey"))
        lines.append("")
        sorted_obs = sorted(
            retro.observations,
            key=lambda o: (SEVERITY_ORDER.get(o.severity, 99), o.move_id),
        )[:15]
        for o in sorted_obs:
            lines.append(f"  [{_format_severity(o.severity)}] {o.summary}")
            lines.append(_ui.colored(f"        surface: {o.surface_id or '(unknown)'}", "grey"))
            lines.append(_ui.colored(f"        move:    {o.move_id}", "grey"))
            # Wrap detail to ~80 cols
            for line in _wrap_text(o.detail, 76):
                lines.append(_ui.colored(f"        {line}", "grey"))
            lines.append("")

    return "\n".join(lines)


def _wrap_text(text: str, width: int) -> List[str]:
    """Simple greedy word-wrap."""
    words = text.split()
    lines: List[str] = []
    current: List[str] = []
    current_len = 0
    for w in words:
        if current_len + len(w) + 1 > width:
            if current:
                lines.append(" ".join(current))
            current = [w]
            current_len = len(w)
        else:
            current.append(w)
            current_len += len(w) + 1
    if current:
        lines.append(" ".join(current))
    return lines or [""]


def run_retro(
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    format_: str = "human",
) -> int:
    """Run a practice retrospective over the surface store. Returns exit code."""
    entries = list(filter_entries(iter_index(), since=since, until=until))
    raw_surfaces = [e.raw for e in entries]
    retro = observe_surfaces(raw_surfaces, period_from=since, period_to=until)

    if format_ == "json":
        print(json.dumps(retro.to_dict(), indent=2, sort_keys=True))
    else:
        print(_render_retrospective(retro))
    return 0
