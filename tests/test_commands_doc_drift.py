"""Event 172 — docs/COMMANDS.md claims to map EVERY subcommand; it had
silently dropped 12 (including `deferred`, central to the ledger, and
the four practice commands that were ALSO crashing from the installed
entry point). This diffs the argparse reality against the doc so the
promise is CI-enforced, not aspirational.
"""
from __future__ import annotations

import re
from pathlib import Path

from episteme.cli import build_parser  # pyright: ignore[reportMissingImports]

REPO = Path(__file__).resolve().parents[1]


def _cli_subcommands() -> set[str]:
    parser = build_parser()
    for action in parser._actions:  # noqa: SLF001
        if hasattr(action, "choices") and action.choices:
            return set(action.choices.keys())
    raise AssertionError("no subparsers found on the CLI parser")


def _documented() -> set[str]:
    text = (REPO / "docs" / "COMMANDS.md").read_text(encoding="utf-8")
    return set(re.findall(r"`episteme ([a-z0-9-]+)", text))


def test_every_cli_subcommand_is_documented():
    missing = _cli_subcommands() - _documented()
    assert not missing, (
        f"subcommands missing from docs/COMMANDS.md: {sorted(missing)} — "
        f"the doc promises a map of EVERY subcommand; keep the promise "
        f"or change the promise"
    )


def test_no_phantom_commands_documented():
    phantom = _documented() - _cli_subcommands()
    assert not phantom, (
        f"docs/COMMANDS.md documents commands the CLI does not expose: "
        f"{sorted(phantom)}"
    )
