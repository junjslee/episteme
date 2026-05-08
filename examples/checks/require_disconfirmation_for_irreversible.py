#!/usr/bin/env python3
"""Refuse irreversible Bash ops if the Reasoning Surface lacks disconfirmation.

Demonstrates the surface-aware check pattern: a check can read
.episteme/reasoning-surface.json from cwd, inspect operator-declared fields,
and decide based on epistemic state rather than just command shape.

This is the connecting tissue between user-authored checks and episteme's
core enforcement model: feedforward control requires the agent to declare
"what would prove this plan wrong" before an irreversible action lands.
This check enforces that for a curated set of named irreversible commands —
extend the pattern set as you discover new shapes that matter for your repo.

Wire into ~/.claude/settings.json (matcher: "Bash"):

  {"type": "command", "command": "python3 /abs/path/to/require_disconfirmation_for_irreversible.py"}

See examples/checks/README.md for the full check contract.
"""
import json
import re
import sys
from pathlib import Path

# Commands that materially change shared state and are hard to reverse.
# Add to this list rather than reaching into the kernel; this is YOUR list.
IRREVERSIBLE_PATTERNS = [
    re.compile(r"\bterraform\s+apply\b"),
    re.compile(r"\bkubectl\s+apply\b"),
    re.compile(r"\bgh\s+release\s+create\b"),
    re.compile(r"\bnpm\s+publish\b"),
    re.compile(r"\bcargo\s+publish\b"),
    re.compile(r"\bgit\s+push\s+(?:.*\s+)?--force(?:-with-lease)?\b"),
    re.compile(r"\bgit\s+tag\s+(?:.*\s+)?-[as]\b"),
    re.compile(r"\bdocker\s+push\b"),
    re.compile(r"\baws\s+s3\s+rm\s+--recursive\b"),
]

SURFACE_PATH = Path.cwd() / ".episteme" / "reasoning-surface.json"
LAZY_VALUES = {"", "n/a", "none", "tbd", "todo", "해당 없음", "없음"}
MIN_DISCONFIRMATION_LEN = 15  # mirrors kernel/REASONING_SURFACE.md guidance


def _surface_disconfirmation_status() -> tuple[bool, str]:
    """Return (ok, reason) — ok means disconfirmation is present and substantive."""
    if not SURFACE_PATH.exists():
        return False, f"no surface at {SURFACE_PATH}"
    try:
        surface = json.loads(SURFACE_PATH.read_text())
    except json.JSONDecodeError as e:
        return False, f"surface unparseable: {e}"
    raw = surface.get("disconfirmation")
    value = (raw or "").strip()
    if value.lower() in LAZY_VALUES:
        return False, f"disconfirmation is empty or lazy ({value!r})"
    if len(value) < MIN_DISCONFIRMATION_LEN:
        return False, f"disconfirmation too short ({len(value)} chars; need >= {MIN_DISCONFIRMATION_LEN})"
    return True, ""


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    if not any(p.search(command) for p in IRREVERSIBLE_PATTERNS):
        return 0
    ok, reason = _surface_disconfirmation_status()
    if ok:
        return 0
    sys.stderr.write(
        "[require_disconfirmation] Refused: irreversible op without disconfirmation.\n"
        f"  command: {command}\n"
        f"  reason:  {reason}\n"
        f"  to proceed: declare a falsifiable disconfirmation in {SURFACE_PATH}\n"
        f"             (one specific observable outcome, >= {MIN_DISCONFIRMATION_LEN} chars,\n"
        f"              that would prove this plan wrong if observed).\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
