#!/usr/bin/env python3
"""Block rm -rf and related destructive shell patterns.

The minimum-viable check. Mirrors the Pi explainer-video's rmrf-blocker
example at the same conceptual size, ported to Claude Code's PreToolUse
hook protocol.

Wire into ~/.claude/settings.json:

  {
    "hooks": {
      "PreToolUse": [
        {
          "matcher": "Bash",
          "hooks": [
            {"type": "command", "command": "python3 /abs/path/to/block_rmrf.py"}
          ]
        }
      ]
    }
  }

See examples/checks/README.md for the full check contract.
"""
import json
import re
import sys

# rm -rf with at least one positional target. The (?:--\s+)? optional
# end-of-options sentinel catches `rm -rf -- /tmp/foo`. The trailing
# negative class avoids matching just shell metachars after -rf.
PATTERN = re.compile(r"\brm\s+-rf?\s+(?:--\s+)?[^|;&\s]")


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0  # malformed payload: don't block
    command = (payload.get("tool_input") or {}).get("command", "")
    if PATTERN.search(command):
        sys.stderr.write(
            "[block_rmrf] Refused: rm -rf shape detected.\n"
            f"  command: {command}\n"
            "  to override: rewrite the command, or temporarily remove this hook from settings.json.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
