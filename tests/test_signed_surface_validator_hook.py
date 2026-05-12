"""Tests for the opt-in signed-surface validator PreToolUse hook.

Covers four behavioral paths:
  1. Non-irreversible Bash → allow (exit 0)
  2. Irreversible Bash + REQUIRED unset → advisory + allow (exit 0)
  3. Irreversible Bash + REQUIRED=1 + ALLOW_TEST=1 + active surface → allow (0)
  4. Irreversible Bash + REQUIRED=1 + ALLOW_TEST unset + test-mode sig → BLOCK (2)
"""
from __future__ import annotations

import json
import os

import pytest

from episteme.hooks import signed_surface_validator as v
from episteme.surface import run_surface_cli


@pytest.fixture
def isolated_root(tmp_path, monkeypatch):
    root = tmp_path / ".episteme"
    monkeypatch.setenv("EPISTEME_ROOT", str(root))
    # Reset env vars that affect hook behavior
    for env_var in (
        "EPISTEME_SIGNED_SURFACE_REQUIRED",
        "EPISTEME_ALLOW_TEST_SIGNATURES",
        "EPISTEME_ENFORCE_TSA",
        "EPISTEME_ENFORCE_REKOR",
    ):
        monkeypatch.delenv(env_var, raising=False)
    return root


def _author_irreversible():
    run_surface_cli([
        "author",
        "--core-question", "Test surface for the validator hook integration",
        "--decision-choice", "proceed",
        "--decision-confidence", "0.8",
        "--stop-rollback-path", "git reset --hard ORIG_HEAD on the test branch",
        "--reversibility", "irreversible",
        "--blast-radius", "regulated_artifact",
        "--ai-act-tier", "high",
        "--blueprint", "consequence_chain",
        "--with-tsa", "--with-rekor",
        "--format", "json",
    ])


def test_non_irreversible_bash_allows(isolated_root):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    assert v.main(payload) == 0


def test_irreversible_bash_with_required_unset_allows_with_advisory(isolated_root, capsys):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin master"}})
    rc = v.main(payload)
    assert rc == 0
    stderr = capsys.readouterr().err
    assert "EPISTEME_SIGNED_SURFACE_REQUIRED" in stderr


def test_irreversible_bash_required_with_no_active_surface_blocks(isolated_root, monkeypatch):
    monkeypatch.setenv("EPISTEME_SIGNED_SURFACE_REQUIRED", "1")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin master"}})
    rc = v.main(payload)
    assert rc == 2  # EXIT_BLOCK


def test_irreversible_bash_with_test_sig_and_allow_test_passes(isolated_root, monkeypatch):
    _author_irreversible()
    monkeypatch.setenv("EPISTEME_SIGNED_SURFACE_REQUIRED", "1")
    monkeypatch.setenv("EPISTEME_ALLOW_TEST_SIGNATURES", "1")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin master"}})
    rc = v.main(payload)
    assert rc == 0


def test_irreversible_bash_with_test_sig_no_allow_blocks(isolated_root, monkeypatch, capsys):
    _author_irreversible()
    monkeypatch.setenv("EPISTEME_SIGNED_SURFACE_REQUIRED", "1")
    # ALLOW_TEST not set — test-mode signature should be rejected.
    # The hook always returns exit 2 (Claude Code "block" contract); the
    # specific failure code (10 = test_signature_rejected) is in the
    # structured JSON written to stderr for the model + operator to read.
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin master"}})
    rc = v.main(payload)
    assert rc == 2  # EXIT_BLOCK
    stderr = capsys.readouterr().err
    err_obj = json.loads(stderr)
    assert err_obj["code"] == "test_signature_rejected"
    assert err_obj["exit_code"] == 10


def test_action_class_mismatch_blocks(isolated_root, monkeypatch):
    # Author a REVERSIBLE surface, then attempt an IRREVERSIBLE action
    run_surface_cli([
        "author",
        "--core-question", "Reversible decision but irreversible action attempted",
        "--decision-choice", "proceed",
        "--decision-confidence", "0.8",
        "--stop-rollback-path", "no rollback needed, reversible action only",
        "--reversibility", "reversible",  # mismatch
        "--blast-radius", "local",
        "--ai-act-tier", "minimal",
        "--blueprint", "consequence_chain",
        "--format", "json",
    ])
    monkeypatch.setenv("EPISTEME_SIGNED_SURFACE_REQUIRED", "1")
    monkeypatch.setenv("EPISTEME_ALLOW_TEST_SIGNATURES", "1")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin master"}})
    rc = v.main(payload)
    assert rc == 2  # EXIT_BLOCK due to action_class_mismatch


def test_drop_table_pattern_matched(isolated_root, monkeypatch):
    monkeypatch.setenv("EPISTEME_SIGNED_SURFACE_REQUIRED", "1")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "psql -c 'DROP TABLE users'"}})
    rc = v.main(payload)
    assert rc == 2  # blocked because no active signed surface


def test_no_payload_allows(isolated_root):
    # Empty stdin payload — no hook context, treat as allow
    rc = v.main("")
    assert rc == 0


def test_malformed_payload_returns_usage_error(isolated_root):
    rc = v.main("not-json")
    assert rc == 64  # EXIT_USAGE
