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
"""
from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parents[1] / "core" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import _marker_reaper  # type: ignore  # noqa: E402  # pyright: ignore[reportMissingImports]


def main() -> int:
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
