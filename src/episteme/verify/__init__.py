"""Standalone Signed Reasoning Surface verifier.

Implementation surface for `episteme verify` CLI. Re-exports the load-bearing
verifier functions from `core.signing.canonical_surface` and provides the
CLI entry point.

Design intent: this verifier runs WITHOUT trusting the episteme runtime.
Auditors can ship just this module + Python stdlib to verify any signed
surface artifact. The pubkey resolution is pluggable (DNS / OIDC / Fulcio /
test-fixture file) so the verifier works in air-gapped audit environments.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from episteme.verify._cli import main, run_verify_cli

__all__ = ["main", "run_verify_cli"]
