"""argparse glue for `episteme practice ...`."""
from __future__ import annotations

# pyright: reportMissingImports=false
import argparse
import sys
from typing import List, Optional

from episteme.practice._walk import run_walk
from episteme.practice._demo import run_demo
from episteme.practice._retro import run_retro


EXIT_OK = 0
EXIT_USAGE = 64


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="episteme practice",
        description=(
            "Make the practice tangible. Narrated walkthrough, retrospective "
            "over the surface store, or worked-example surface body."
        ),
    )
    sub = p.add_subparsers(dest="action", required=True)

    walk = sub.add_parser(
        "walk",
        help="Narrated walkthrough of the 5-stage practice (Frame → Decompose → Execute → Verify → Handoff)",
    )
    walk.add_argument(
        "--interactive",
        action="store_true",
        help="Pause between stages waiting for [Enter] (default: print all in one go)",
    )

    retro = sub.add_parser(
        "retro",
        help="Practice retrospective: gap observations over signed surfaces in a time window",
    )
    retro.add_argument("--since", help="ISO date — start of window (default: all-time)")
    retro.add_argument("--until", help="ISO date — end of window (default: now)")
    retro.add_argument("--format", choices=("human", "json"), default="human")

    demo = sub.add_parser(
        "demo",
        help="Output a worked-example signed-surface body, narrated stage-by-stage",
    )
    demo.add_argument(
        "--format",
        choices=("narrated", "json"),
        default="narrated",
        help="narrated = stage-by-stage narration; json = body only (suitable for `surface sign`)",
    )

    return p


def run_practice_cli(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.action == "walk":
        return run_walk(interactive=args.interactive)
    if args.action == "retro":
        return run_retro(since=args.since, until=args.until, format_=args.format)
    if args.action == "demo":
        return run_demo(format_=args.format)
    parser.print_help(sys.stderr)
    return EXIT_USAGE


def main(argv: Optional[List[str]] = None) -> int:
    return run_practice_cli(argv)


if __name__ == "__main__":
    sys.exit(main())
