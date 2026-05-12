"""Operator-facing CLI for authoring, signing, and managing Reasoning Surfaces.

The Phase 3 backbone (`core/ptsp/`, `core/signing/`, `episteme verify`) provides
the library APIs. This module is the operator UX — what someone actually types
when they decide to author a Signed Reasoning Surface before an irreversible
action.

Subcommands:
  episteme surface author    Interactive author + sign in one flow.
  episteme surface sign      Sign an already-drafted surface JSON file.
  episteme surface show      Display the active surface (or one by id).
  episteme surface list      List signed surfaces under .episteme/surfaces/.
  episteme surface status    Brief status of the active surface for prompts.
  episteme surface verify    Verify the active surface (round-trip self-test).

Storage layout:
  .episteme/keys/operator_signing.key      ed25519 (or test-hmac) private key
  .episteme/keys/<fingerprint>.pub         public key files (auditor-readable)
  .episteme/surfaces/<surface_id>.json     signed surface artifacts
  .episteme/surfaces/active.txt            pointer file to active surface_id

The key is OWNED by the operator. The agent process has no privileged read
path to it beyond the local-cwd `.episteme/keys/` directory; production
deployments are expected to keep the private key in OS keychain (macOS
Keychain / Linux libsecret / Windows DPAPI) and inject only the public-key
fingerprint binding through the resolver — this v1 CLI defaults to filesystem
storage for operator self-trial; keychain integration is a separate operator-
gated Event.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from episteme.surface._cli import build_parser, run_surface_cli, main

__all__ = ["build_parser", "run_surface_cli", "main"]
