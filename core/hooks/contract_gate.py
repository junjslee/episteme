#!/usr/bin/env python3
"""Contract Gate — Stop hook (DESIGN STUB; NOT auto-installed).

Companion design doc: docs/CONTRACT_GATE.md
Principled basis:    kernel/ARTIFACT_TAXONOMY.md (contracts/ is frozen-purpose)
                     kernel/PATTERN_GOVERNANCE.md (patterns carry contract_ref)

This hook runs declared contract tests at turn-end (Stop event) and fails
the gate if any declared verifier reports non-zero exit. Composes with
existing core/hooks/quality_gate.py — both ship as Stop hooks; the
recommended firing order is quality_gate → contract_gate → checkpoint
(cheapest test first, then conformance, then commit).

Activation is operator-gated. This file ships in the repo but is NOT
registered in any settings.json by default. Downstream projects opt in by
adding the path to their settings.json Stop hooks list AFTER a
contracts/ directory exists with at least one supported spec file. The
dual signal (file presence + explicit settings entry) is deliberate —
mere presence of a contracts/ directory should not silently activate
behavior change for projects that adopt the name for unrelated reasons.

Exit codes mirror src/episteme/verify/ conventions:
    0   all contracts passed (or contracts/ absent / empty)
   10   one or more contract assertions failed
   11   a declared verifier was not found on PATH
   12   a contract artifact's syntax did not parse
   30   internal error in the gate itself

Implementation status (Event 130):
    The verifier resolution table, the per-format runner adapters, and
    the result aggregator are not yet implemented. The supported-format
    table is documented in docs/CONTRACT_GATE.md § What counts as a
    contract. A subsequent Event will land the runners — OpenAPI first
    (schemathesis or openapi-validator), then Hurl, then the others.

    Until activated, this file is a no-op (exits 0 unconditionally) so
    that a downstream project that wires it into settings.json
    prematurely does not break their turn-end flow. The no-op is the
    safe state; the real verifier-resolution chain ships in a future
    Event with its own Reasoning Surface and review.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Exit codes (kept in sync with docs/CONTRACT_GATE.md § CLI surface)
EXIT_OK = 0
EXIT_ASSERTION_FAILED = 10
EXIT_VERIFIER_NOT_FOUND = 11
EXIT_PARSE_FAILED = 12
EXIT_INTERNAL_ERROR = 30


def _find_contracts_root(cwd: Path) -> Path | None:
    """Walk upward from cwd looking for a contracts/ directory.

    Returns the contracts/ Path if found, else None. The walk stops at
    the repo root (detected by .git/ presence) or filesystem root,
    whichever is encountered first.
    """
    current = cwd.resolve()
    while True:
        candidate = current / "contracts"
        if candidate.is_dir():
            return candidate
        if (current / ".git").exists() or current.parent == current:
            return None
        current = current.parent


def main() -> int:
    """Stop-hook entrypoint.

    Current behavior: scan for a contracts/ root; if absent, exit 0 (no
    contracts declared = no enforcement claim). If present, log that the
    gate fired but the verifier chain is not yet implemented; exit 0
    anyway (the gate is a no-op until activated, per the file header).

    Future behavior: enumerate contracts/*, resolve each artifact's
    verifier by extension or adjacent .verifier file, run all verifiers,
    aggregate results, exit per the EXIT_* table above.
    """
    try:
        cwd = Path.cwd()
        contracts_root = _find_contracts_root(cwd)
        if contracts_root is None:
            # No contracts declared — gate is inert.
            return EXIT_OK

        # Contracts directory found, but the verifier-resolution chain
        # is not yet implemented. Log to stderr (visible to the operator
        # without affecting the gate's exit code) and return OK so an
        # over-eagerly-wired-up project does not break their turn-end
        # flow before the real implementation ships.
        print(
            "[contract_gate] contracts/ detected at "
            f"{contracts_root} but verifier chain is not yet "
            "implemented (Event 130 ships the design + this stub; "
            "runners ship in a future Event). Gate is currently a "
            "no-op; this message confirms the hook is wired correctly.",
            file=sys.stderr,
        )
        return EXIT_OK
    except Exception as exc:  # pragma: no cover — defensive
        print(f"[contract_gate] internal error: {exc}", file=sys.stderr)
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    sys.exit(main())
