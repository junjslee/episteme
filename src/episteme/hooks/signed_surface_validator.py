"""Opt-in PreToolUse hook validating signed-surface@1.0 artifacts.

Runs ADDITIVELY alongside the existing core/hooks/reasoning_surface_guard.py
hot path. This hook does NOT replace, override, or interact with the
existing guard — Claude Code v2.0.10+ runs PreToolUse hooks in series, and
each independently decides exit 0 (allow) vs exit 2 (block).

Activation:
  1. Operator installs the skills/compliance-evidence-layer/ bundle which
     adds a PreToolUse hook entry to .claude/settings.json pointing at
     `python -m episteme.hooks.signed_surface_validator`.
  2. Operator sets EPISTEME_SIGNED_SURFACE_REQUIRED=1 in their environment.
     When this flag is unset, the hook is a no-op (exit 0).
  3. Operator authors a Signed Reasoning Surface via `episteme surface author`
     before each irreversible-class tool invocation.

The hook reads the active surface (pointer at .episteme/surfaces/active.txt),
verifies it cryptographically, and exits 2 with a structured error to stderr
if any of: signature invalid, surface stale, missing required fields, action
class declared reversible but the tool call is in A_irr.

Exit code contract (matches `episteme verify`):
  0   allow tool call (surface valid OR hook disabled)
  2   block tool call (standard Claude Code "deny" signal)
  10  signature invalid
  11  timestamp drift / TSA invalid (when enforce_tsa=true)
  14  self_hash mismatch
  20  surface file malformed / schema-invalid
  21  pubkey resolution failed
  64  hook usage error

Exit code 2 is what Claude Code interprets as "block tool call." The
specific verification code (10-21) is also written to stderr as structured
JSON so the model and operator can read the precise remediation.

Reading stdin (Claude Code v2.0.10+ PreToolUse contract):
  {
    "session_id": "...",
    "tool_name": "Bash" | "Write" | "Edit" | "MultiEdit",
    "tool_input": { ... tool-specific args ... }
  }
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


# ─── Irreversible-class action set (positive-system enumeration) ─────────
# Mirrors PRODUCTIZATION_PLAN.md § 3.4. Keep this list narrow and explicit
# per the operator's rule-shape discipline (CLAUDE.md agent_feedback rule
# on positive vs negative systems).

A_IRR_BASH_PATTERNS = [
    re.compile(r"^\s*git\s+push(\s|$)"),
    re.compile(r"^\s*git\s+reset\s+--hard(\s|$)"),
    re.compile(r"^\s*git\s+rebase\s+.*--onto"),
    re.compile(r"^\s*gh\s+pr\s+merge(\s|$)"),
    re.compile(r"^\s*rm\s+-rf?(\s|$)"),
    re.compile(r"^\s*kubectl\s+apply\s+"),
    re.compile(r"^\s*terraform\s+apply(\s|$)"),
    re.compile(r"^\s*helm\s+(install|upgrade|uninstall)\s+"),
    re.compile(r"^\s*npm\s+publish(\s|$)"),
    re.compile(r"^\s*pip\s+publish(\s|$)"),
    re.compile(r"^\s*cargo\s+publish(\s|$)"),
    re.compile(r"^\s*aws\s+s3\s+rm\s+"),
    re.compile(r"^\s*gcloud\s+sql\s+(restore|delete)\s+"),
    re.compile(r".*\bdrop\s+table\b", re.IGNORECASE),
    re.compile(r".*\btruncate\s+table\b", re.IGNORECASE),
]


# ─── Exit codes ──────────────────────────────────────────────────────────

EXIT_ALLOW = 0
EXIT_BLOCK = 2
EXIT_SIG_INVALID = 10
EXIT_TIMESTAMP = 11
EXIT_SELF_HASH = 14
EXIT_MALFORMED = 20
EXIT_KEY_RESOLUTION = 21
EXIT_USAGE = 64


# ─── Helpers ─────────────────────────────────────────────────────────────


def _required() -> bool:
    """The hook is opt-in. Returns True iff explicitly enabled by env."""
    return os.environ.get("EPISTEME_SIGNED_SURFACE_REQUIRED", "").lower() in {"1", "true", "yes"}


def _is_irreversible(tool_name: str, tool_input: Dict[str, Any]) -> Optional[str]:
    """Return the matched pattern label if this tool call is in A_irr; else None."""
    if tool_name == "Bash":
        cmd = tool_input.get("command", "") or ""
        for pat in A_IRR_BASH_PATTERNS:
            if pat.match(cmd):
                return pat.pattern
        return None
    # Phase 3 leaves Write/Edit out of A_irr by default (covered by
    # the soak-protected reasoning_surface_guard hot path). Operators can
    # opt into stricter scope via a config file in a later Event.
    return None


def _emit_block(code: str, exit_code: int, **ctx: Any) -> int:
    payload = {
        "block": True,
        "code": code,
        "exit_code": exit_code,
        "remediation": ctx.get("remediation", ""),
        "context": {k: v for k, v in ctx.items() if k != "remediation"},
    }
    print(json.dumps(payload), file=sys.stderr)
    return EXIT_BLOCK


# ─── Main ────────────────────────────────────────────────────────────────


def main(stdin_payload: Optional[str] = None) -> int:
    """Entry point. Reads JSON from stdin (or argument for testability)."""
    raw = stdin_payload if stdin_payload is not None else sys.stdin.read()
    if not raw.strip():
        # No payload — Claude Code didn't pipe a hook context. Treat as allow.
        return EXIT_ALLOW

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"signed_surface_validator: bad hook payload: {e}", file=sys.stderr)
        return EXIT_USAGE

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    matched = _is_irreversible(tool_name, tool_input)
    if not matched:
        return EXIT_ALLOW

    if not _required():
        # Hook is wired but operator hasn't opted in. Emit advisory log
        # to stderr (Claude Code surfaces stderr to operator) but allow.
        sys.stderr.write(
            "[episteme.signed_surface_validator] EPISTEME_SIGNED_SURFACE_REQUIRED "
            "is unset; allowing irreversible action without signed-surface check. "
            "Set EPISTEME_SIGNED_SURFACE_REQUIRED=1 to enforce.\n"
        )
        return EXIT_ALLOW

    # Lazy imports — only paid when the hook actually runs in enforce mode.
    from core.signing.canonical_surface import SurfaceVerificationError, verify_surface
    from core.signing.transparency import verify_inclusion_proof_shape
    from core.signing.tsa import verify_tsa_token
    from episteme.surface._storage import (
        get_active_surface_path,
        read_public_key_by_fingerprint,
    )

    surface_path = get_active_surface_path()
    if surface_path is None:
        return _emit_block(
            "no_active_signed_surface",
            EXIT_BLOCK,
            remediation=(
                "BLOCKED: no active Signed Reasoning Surface; the tool call matched the "
                "irreversible-class set (" + matched + ").\n"
                "Run:  episteme surface author --core-question '<...>' "
                "--decision-choice proceed --decision-confidence 0.X "
                "--stop-rollback-path '<...>'"
            ),
            matched_pattern=matched,
        )

    # Freshness check (15 minute TTL)
    try:
        mtime = surface_path.stat().st_mtime
        age_s = time.time() - mtime
    except OSError:
        age_s = 0
    if age_s > 900:
        return _emit_block(
            "surface_stale",
            EXIT_BLOCK,
            remediation=(
                f"BLOCKED: active Signed Reasoning Surface is {int(age_s/60)} minute(s) "
                "old (TTL 15 minutes). Re-author before proceeding.\n"
                "Run:  episteme surface author --interactive"
            ),
            age_seconds=int(age_s),
            matched_pattern=matched,
        )

    # Load and verify
    try:
        with open(surface_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return _emit_block(
            "malformed_surface",
            EXIT_MALFORMED,
            remediation=f"BLOCKED: active surface JSON unreadable: {e}",
        )

    def resolver(fp: str) -> str:
        pk = read_public_key_by_fingerprint(fp)
        if pk is None:
            raise FileNotFoundError(f"no pubkey file for fingerprint {fp}")
        return pk

    allow_test = os.environ.get("EPISTEME_ALLOW_TEST_SIGNATURES", "").lower() in {"1", "true", "yes"}
    verify_tsa = os.environ.get("EPISTEME_ENFORCE_TSA", "").lower() in {"1", "true", "yes"}
    verify_rekor = os.environ.get("EPISTEME_ENFORCE_REKOR", "").lower() in {"1", "true", "yes"}

    try:
        verify_surface(
            data,
            public_key_resolver=resolver,
            allow_test_signatures=allow_test,
            verify_tsa_fn=verify_tsa_token if verify_tsa else None,
            verify_rekor_fn=verify_inclusion_proof_shape if verify_rekor else None,
        )
    except SurfaceVerificationError as e:
        return _emit_block(
            e.code,
            e.exit_code,
            remediation=(
                f"BLOCKED: signed-surface verification failed [{e.exit_code}] {e.code}: {e.detail}\n"
                "Re-author and re-sign the active surface."
            ),
            matched_pattern=matched,
        )

    # Cross-check: surface declares irreversibility consistent with action class
    surf = data.get("surface", {})
    declared = surf.get("risk_classification", {}).get("reversibility")
    if declared != "irreversible":
        return _emit_block(
            "action_class_mismatch",
            EXIT_BLOCK,
            remediation=(
                f"BLOCKED: tool matched irreversible-class pattern ({matched}) but active "
                f"surface declares risk_classification.reversibility = '{declared}'.\n"
                "Re-author surface with --reversibility irreversible."
            ),
            declared_reversibility=declared,
            matched_pattern=matched,
        )

    return EXIT_ALLOW


if __name__ == "__main__":
    sys.exit(main())
