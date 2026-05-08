#!/usr/bin/env python3
"""Advisory: warn on Edit/Write into soak-protected paths.

Demonstrates the advisory-not-block pattern: write to stderr, exit 0.
The agent sees the message and can act on it; the call proceeds.

Soak-protected paths are surfaces whose load-bearing state shapes per-turn
agent behavior — kernel/ markdown corpus, core/hooks/ runtime gate logic,
core/blueprints/ blueprint specs. Editing these usually means the operator
or agent should be inside a Fence Reconstruction blueprint surface
(constraint origin + removal-consequence prediction + rollback path).
This check surfaces the reminder without blocking, so agent-driven
workflows that DO have a valid Fence Reconstruction in flight are not
short-circuited.

Wire into ~/.claude/settings.json (matcher: "Edit|Write|MultiEdit"):

  {"type": "command", "command": "python3 /abs/path/to/flag_kernel_edits.py"}

See examples/checks/README.md for the full check contract.
"""
import json
import sys

PROTECTED_PREFIXES = (
    "kernel/",
    "core/hooks/",
    "core/blueprints/",
    "templates/",
    "labs/",
)


def _extract_path(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    if isinstance(tool_input, dict):
        return tool_input.get("file_path", "") or ""
    return ""


def _matched_protected_prefix(abspath: str) -> str | None:
    """Return the protected path (relative shape) if abspath is under one of the prefixes."""
    if not abspath:
        return None
    for prefix in PROTECTED_PREFIXES:
        # Match either a relative prefix or an absolute path containing /<prefix>.
        if abspath.startswith(prefix):
            return abspath
        idx = abspath.find("/" + prefix)
        if idx >= 0:
            return abspath[idx + 1 :]
    return None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    rel = _matched_protected_prefix(_extract_path(payload))
    if rel is None:
        return 0
    sys.stderr.write(
        "[flag_kernel_edits] Advisory: editing soak-protected surface.\n"
        f"  path:     {rel}\n"
        "  reminder: kernel/ + core/hooks/ + core/blueprints/ usually require a Fence Reconstruction\n"
        "            surface (constraint origin + removal-consequence prediction + rollback path)\n"
        "            before edit.\n"
        "  this check is advisory only — the edit will proceed. Override silently by removing\n"
        "  this hook from settings.json, or upgrade to a blocking variant if your project requires it.\n"
    )
    return 0  # advisory only — do not block


if __name__ == "__main__":
    raise SystemExit(main())
