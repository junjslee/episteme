#!/usr/bin/env python3
"""SessionStart hook — prints git status and NEXT_STEPS to the terminal.

Output appears at session open so Claude and the operator share the same
starting context without a manual paste.
"""
import subprocess
from pathlib import Path


def run(args: list[str]) -> str:
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


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

    # NEXT_STEPS.md if present
    ns = Path("docs/NEXT_STEPS.md")
    if ns.exists():
        content = ns.read_text().strip()
        if content:
            lines.append(f"\n--- docs/NEXT_STEPS.md ---\n{content}")

    if lines:
        separator = "─" * 60
        print(f"\n{separator}")
        print("\n".join(lines))
        print(separator)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
