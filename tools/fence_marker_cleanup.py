#!/usr/bin/env python3
"""Manual marker GC — TTL-unlink orphaned pairing markers (Event 146).

Sweeps BOTH pending-marker directories
(``~/.episteme/state/cascade_pending/`` + ``~/.episteme/state/fence_pending/``)
and removes markers whose age exceeds MARKER_TTL_SECONDS (24 hours). A
well-formed marker ages by its ``written_at`` payload field (matching the
TTL read-check in ``core/hooks/_fence_synthesis.py``); a malformed marker
ages by file ``mtime`` and is removed only when it too is past TTL.

Single-handler (Event 145 B1): this tool and the SessionStart hook
(``core/hooks/session_context.py``) share ONE sweep implementation —
``core/hooks/_marker_reaper.py``. This file is the standalone / cron entry
point; it carries no cleanup logic and no duplicated TTL constant of its
own. The reaper normally runs automatically at SessionStart; run this only
to force a sweep out of band.

Prints a one-line summary to stderr and exits 0. Safe to run repeatedly;
idempotent.

Argument discipline (Event 148 · smallfix #3, closing an Event 146 finding):
the sweep is destructive (it unlinks marker files), so it must run ONLY on a
bare invocation. ``-h``/``--help`` prints usage and exits 0 without sweeping;
any unknown flag or positional exits 2 without sweeping. Previously the tool
ignored ``sys.argv`` entirely, so ``--help`` (and any typo'd flag) silently ran
a live sweep.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parents[1] / "core" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import _marker_reaper  # type: ignore  # noqa: E402  # pyright: ignore[reportMissingImports]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args. Defines no options, so a bare invocation runs the
    sweep; ``-h``/``--help`` (exit 0) and any unknown token (exit 2) both
    short-circuit via ``SystemExit`` before the sweep can start."""
    parser = argparse.ArgumentParser(
        prog="fence_marker_cleanup",
        description=(
            "Force an out-of-band sweep of orphaned pairing markers "
            "(cascade + fence pending dirs), TTL-unlinking any marker past "
            "MARKER_TTL_SECONDS. Takes no arguments; run bare to sweep."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    # Parse BEFORE any destructive work: --help / unknown-flag must not sweep.
    _parse_args(sys.argv[1:] if argv is None else argv)
    results = _marker_reaper.reap_all()
    cascade = results["cascade"]
    fence = results["fence"]
    print(
        f"marker_cleanup: {_marker_reaper.format_summary(results)}; "
        f"kept={cascade.kept + fence.kept} "
        f"vanished={cascade.vanished + fence.vanished}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
