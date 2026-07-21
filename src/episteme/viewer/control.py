"""Viewer control plane — operator-ratified action tiers (Event 175).

Positive system: an action exists ONLY if enumerated here. The tier boundary
is governance, not convenience — Tier 3 (governance mutations: rigor/mode
toggles, kernel manifest updates, review verdicts, profile acks) is
deliberately ABSENT from the executable registry and ships as a copyable
command catalog instead. The kernel's thesis is deliberate friction on
consequential ops; a UI that one-clicks them would bypass the exact ceremony
it visualizes. The absence of the endpoint IS the enforcement.

Security model (all enforced in server.py, tested in
tests/test_viewer_control.py): control is loopback-only (hard-disabled on any
other bind), every POST carries the per-server-start session token, and the
Host header must be in the loopback allowlist (DNS-rebinding defense).
"""

from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import List, Optional

#: Hard cap on captured action output returned to the client.
OUTPUT_CAP_BYTES = 65_536
#: Per-action subprocess timeout (sync can take a few seconds; doctor too).
ACTION_TIMEOUT_S = 120

#: Marker appended when output is truncated — the UI must show the cut,
#: never render a silently shortened result as complete.
TRUNCATION_MARKER = "\n… [output truncated at 64KB]"


@dataclass(frozen=True)
class Action:
    name: str        # registry key, also the URL segment
    tier: int        # 1 = diagnostic, 2 = reversible maintenance (confirm-gated in UI)
    label: str       # button text
    argv: tuple      # episteme CLI args
    description: str


#: The executable registry. Tier 3 is NOT here — by design, not omission.
ACTIONS: dict = {
    a.name: a
    for a in (
        Action("doctor", 1, "doctor", ("doctor",),
               "Verify runtime wiring (read-only)"),
        Action("kernel_verify", 1, "kernel verify", ("kernel", "verify"),
               "Check managed kernel files against the manifest (read-only)"),
        Action("docs_lint", 1, "docs lint", ("docs", "lint"),
               "Validate lifecycle markers on tracked docs (read-only)"),
        Action("docs_index_check", 1, "docs index --check", ("docs", "index", "--check"),
               "Verify the generated docs index is current (read-only)"),
        Action("sync", 2, "sync", ("sync",),
               "Propagate kernel memory + governance policies to agent surfaces"),
        Action("docs_index_write", 2, "docs index", ("docs", "index"),
               "Regenerate the docs/README.md index from lifecycle markers"),
        Action("docmap_rebuild", 2, "rebuild doc map", (),
               "Rebuild the code→doc reverse-index cache for this project"),
    )
}

#: Tier 3 — rendered by the UI as copyable commands, never executable here.
#: Each entry names the ceremony the CLI flow enforces that a button would skip.
TIER3_CATALOG: List[dict] = [
    {"command": "episteme kernel update",
     "why_cli": "re-baselines the kernel integrity manifest — verify per-file provenance first"},
    {"command": "episteme review",
     "why_cli": "spot-check verdicts are operator judgment; each entry deserves the full context"},
    {"command": "episteme profile audit ack <run_id>",
     "why_cli": "acknowledging profile drift changes derived gate knobs"},
    {"command": "episteme deferred list",
     "why_cli": "closing deferred discoveries requires verification against reality (kernel rule 11)"},
]

_run_lock = threading.Lock()


def _cli_argv(extra: tuple) -> List[str]:
    # `python -m episteme` has no __main__; spawn the CLI through -c. Trailing
    # args land in the child's sys.argv[1:], which argparse consumes normally.
    return [
        sys.executable,
        "-c",
        "import sys; from episteme.cli import main; sys.exit(main())",
        *extra,
    ]


def _run_docmap_rebuild(cwd: str) -> "tuple[int, str]":
    from pathlib import Path

    from episteme import doc_references

    root = Path(cwd)
    cache = root / ".episteme" / "cache" / "doc_map.json"
    try:
        cache.unlink(missing_ok=True)
    except OSError:
        pass
    index = doc_references.cached_reverse_index(root)
    return 0, (
        f"doc map rebuilt: {len(index)} targets, "
        f"{sum(len(v) for v in index.values())} edges"
    )


def run_action(name: str, cwd: str) -> dict:
    """Execute one registered action; single-flight; output capped.

    Returns a JSON-ready dict. ``busy`` (HTTP 409 upstream) when another
    action is running — one operator, one mutation at a time.
    """
    action: Optional[Action] = ACTIONS.get(name)
    if action is None:
        return {"error": "unknown_action", "name": name}
    if not _run_lock.acquire(blocking=False):
        return {"error": "busy"}
    try:
        if name == "docmap_rebuild":
            code, output = _run_docmap_rebuild(cwd)
        else:
            try:
                proc = subprocess.run(
                    _cli_argv(action.argv),
                    capture_output=True,
                    text=True,
                    timeout=ACTION_TIMEOUT_S,
                    cwd=cwd,
                )
                code = proc.returncode
                output = (proc.stdout or "") + (proc.stderr or "")
            except subprocess.TimeoutExpired:
                return {
                    "error": "timeout",
                    "name": name,
                    "timeout_s": ACTION_TIMEOUT_S,
                }
        truncated = len(output.encode("utf-8", errors="replace")) > OUTPUT_CAP_BYTES
        if truncated:
            output = output[:OUTPUT_CAP_BYTES] + TRUNCATION_MARKER
        return {
            "name": name,
            "tier": action.tier,
            "exit_code": code,
            "output": output,
            "truncated": truncated,
        }
    finally:
        _run_lock.release()


def catalog() -> dict:
    """The full action surface for the UI: executable tiers + Tier 3 display."""
    return {
        "actions": [
            {
                "name": a.name,
                "tier": a.tier,
                "label": a.label,
                "description": a.description,
            }
            for a in sorted(ACTIONS.values(), key=lambda a: (a.tier, a.name))
        ],
        "tier3": TIER3_CATALOG,
    }
