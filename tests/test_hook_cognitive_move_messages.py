"""Tests for cognitive-move-name threading in signed-surface validator hook errors."""
from __future__ import annotations

import json

import pytest

from episteme.hooks import signed_surface_validator as v
from episteme.surface import run_surface_cli


@pytest.fixture
def isolated_root(tmp_path, monkeypatch):
    root = tmp_path / ".episteme"
    monkeypatch.setenv("EPISTEME_ROOT", str(root))
    for env_var in (
        "EPISTEME_SIGNED_SURFACE_REQUIRED",
        "EPISTEME_ALLOW_TEST_SIGNATURES",
        "EPISTEME_ENFORCE_TSA",
        "EPISTEME_ENFORCE_REKOR",
    ):
        monkeypatch.delenv(env_var, raising=False)
    return root


def test_no_active_surface_error_includes_cognitive_move(isolated_root, monkeypatch, capsys):
    monkeypatch.setenv("EPISTEME_SIGNED_SURFACE_REQUIRED", "1")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin master"}})
    rc = v.main(payload)
    assert rc == 2
    stderr = capsys.readouterr().err
    err_obj = json.loads(stderr)
    assert err_obj["code"] == "no_active_signed_surface"
    assert "cognitive_move" in err_obj
    move = err_obj["cognitive_move"]
    assert move["id"]
    assert move["name"]
    assert move["stage"]
    assert "counters" in move
    assert "doc_anchor" in move


def test_test_signature_rejected_maps_to_handoff_signature_move(isolated_root, monkeypatch, capsys):
    # Author a test-mode-signed surface, then attempt irreversible without allow-test.
    run_surface_cli([
        "author",
        "--core-question", "Smoke surface for hook cognitive-move test",
        "--decision-choice", "proceed",
        "--decision-confidence", "0.8",
        "--stop-rollback-path", "git reset --hard ORIG_HEAD on the test branch",
        "--reversibility", "irreversible",
        "--blast-radius", "regulated_artifact",
        "--ai-act-tier", "high",
        "--blueprint", "consequence_chain",
        "--format", "json",
    ])
    monkeypatch.setenv("EPISTEME_SIGNED_SURFACE_REQUIRED", "1")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin master"}})
    rc = v.main(payload)
    assert rc == 2
    stderr = capsys.readouterr().err
    err_obj = json.loads(stderr)
    assert err_obj["code"] == "test_signature_rejected"
    move = err_obj["cognitive_move"]
    assert move["id"] == "handoff.operator_signature"


def test_action_class_mismatch_maps_to_reversibility_move(isolated_root, monkeypatch, capsys):
    run_surface_cli([
        "author",
        "--core-question", "Reversible decision but irreversible attempted action",
        "--decision-choice", "proceed",
        "--decision-confidence", "0.8",
        "--stop-rollback-path", "no rollback needed, fully reversible action",
        "--reversibility", "reversible",  # mismatch with git push (irreversible-class)
        "--blast-radius", "local",
        "--ai-act-tier", "minimal",
        "--blueprint", "consequence_chain",
        "--format", "json",
    ])
    monkeypatch.setenv("EPISTEME_SIGNED_SURFACE_REQUIRED", "1")
    monkeypatch.setenv("EPISTEME_ALLOW_TEST_SIGNATURES", "1")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin master"}})
    rc = v.main(payload)
    assert rc == 2
    stderr = capsys.readouterr().err
    err_obj = json.loads(stderr)
    assert err_obj["code"] == "action_class_mismatch"
    move = err_obj["cognitive_move"]
    assert move["id"] == "frame.reversibility"


def test_hook_still_returns_exit_2_on_block(isolated_root, monkeypatch):
    """The Claude Code contract: block → exit 2 regardless of inner code."""
    monkeypatch.setenv("EPISTEME_SIGNED_SURFACE_REQUIRED", "1")
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin master"}})
    rc = v.main(payload)
    assert rc == 2  # NOT 10, 11, 14, etc. — those are in stderr JSON
