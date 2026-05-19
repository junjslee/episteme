"""Tests for `episteme practice trace` — the operator-facing PTSP surface.

The load-bearing assertions: the promotion gate at core/ptsp/promotion.py
is actually enforced through the CLI (inference cannot enter the Fact
ledger without valid evidence), seals hash-chain, render shows typed
tags distinctly, and trace state never touches the signed-surface chain.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from episteme.practice import run_practice_cli


@pytest.fixture
def trace_root(tmp_path, monkeypatch):
    root = tmp_path / ".episteme"
    monkeypatch.setenv("EPISTEME_ROOT", str(root))
    monkeypatch.setenv("EPISTEME_NO_RICH", "1")
    return root


def _r(*argv) -> int:
    return run_practice_cli(["trace", *argv])


def _working(root: Path, session: str) -> dict:
    return json.loads((root / "traces" / session / "working.json").read_text())


def _infer_id(root: Path, session: str, idx: int = 0) -> str:
    return _working(root, session)["inferences"][idx]["id"]


# ─── Lifecycle ───────────────────────────────────────────────────────────


def test_start_creates_working_step(trace_root):
    assert _r("start", "--session", "s1", "--question", "Is X safe?") == 0
    w = _working(trace_root, "s1")
    assert w["session_id"] == "s1"
    assert w["step_index"] == 0
    assert w["core_question"] == "Is X safe?"
    assert w["knowns"] == [] and w["inferences"] == []


def test_start_refuses_duplicate_session(trace_root):
    _r("start", "--session", "s1")
    assert _r("start", "--session", "s1") == 64  # EXIT_USAGE


def test_fact_and_infer_accumulate(trace_root):
    _r("start", "--session", "s1")
    assert _r("fact", "staging passed", "--source", "test://ci/1", "--method", "test_pass", "--session", "s1") == 0
    assert _r("infer", "prod matches staging", "--confidence", "0.6", "--session", "s1") == 0
    w = _working(trace_root, "s1")
    assert len(w["knowns"]) == 1
    assert len(w["inferences"]) == 1
    assert w["knowns"][0]["kind"] == "fact"
    assert w["inferences"][0]["kind"] == "inference"


def test_unknown_and_assume_accumulate(trace_root):
    _r("start", "--session", "s1")
    assert _r("unknown", "schema drift?", "--cost", "lock could last minutes; SLA breach", "--session", "s1") == 0
    assert _r("assume", "replica failover works", "--if-wrong", "p99 spike", "--detectability", "post_execution_soft", "--session", "s1") == 0
    w = _working(trace_root, "s1")
    assert len(w["unknowns"]) == 1
    assert len(w["assumptions"]) == 1


# ─── The load-bearing assertion: the gate is actually enforced ───────────


def test_promote_rejected_when_test_fails(trace_root):
    _r("start", "--session", "s1")
    _r("infer", "prod matches staging", "--session", "s1")
    inf = _infer_id(trace_root, "s1")
    rc = _r("promote", inf, "--test-id", "t-bad", "--exit-code", "1", "--session", "s1")
    assert rc == 5  # EXIT_PROMOTION_REJECTED
    # The inference MUST still be an inference — the gate did its job.
    w = _working(trace_root, "s1")
    assert any(i["id"] == inf for i in w["inferences"])
    assert not any(f["id"] == inf for f in w["knowns"])


def test_promote_accepted_when_test_passes(trace_root):
    _r("start", "--session", "s1")
    _r("infer", "prod matches staging", "--session", "s1")
    inf = _infer_id(trace_root, "s1")
    rc = _r("promote", inf, "--test-id", "t-good", "--exit-code", "0", "--session", "s1")
    assert rc == 0
    w = _working(trace_root, "s1")
    # inference removed; a new fact present, verified via test_pass
    assert not any(i["id"] == inf for i in w["inferences"])
    promoted = [f for f in w["knowns"] if f["content"] == "prod matches staging"]
    assert len(promoted) == 1
    assert promoted[0]["verification_method"] == "test_pass"
    assert promoted[0]["promoted_from"]["inference_id"] == inf


def test_promote_cosign_path(trace_root, monkeypatch):
    # Author a keypair via the surface CLI (writes .episteme/keys/)
    from episteme.surface import run_surface_cli
    run_surface_cli([
        "author",
        "--core-question", "Cosign keypair bootstrap for trace promote test",
        "--decision-choice", "proceed", "--decision-confidence", "0.8",
        "--stop-rollback-path", "discard the trace, no external effect",
        "--reversibility", "reversible", "--blast-radius", "local",
        "--ai-act-tier", "minimal", "--blueprint", "consequence_chain",
        "--format", "json",
    ])
    _r("start", "--session", "s1")
    _r("infer", "the cosign path works end to end", "--session", "s1")
    inf = _infer_id(trace_root, "s1")
    rc = _r("promote", inf, "--cosign", "--session", "s1")
    assert rc == 0
    w = _working(trace_root, "s1")
    promoted = [f for f in w["knowns"] if f["content"] == "the cosign path works end to end"]
    assert len(promoted) == 1
    assert promoted[0]["verification_method"] == "operator_cosign"


def test_promote_unknown_inference_id_is_usage_error(trace_root):
    _r("start", "--session", "s1")
    rc = _r("promote", "nonexistent-id", "--test-id", "t", "--session", "s1")
    assert rc == 64  # EXIT_USAGE


def test_promote_without_evidence_flag_is_usage_error(trace_root):
    _r("start", "--session", "s1")
    _r("infer", "needs evidence", "--session", "s1")
    inf = _infer_id(trace_root, "s1")
    rc = _r("promote", inf, "--session", "s1")  # no --test-id, no --cosign
    assert rc == 64


# ─── Seal + hash chain ───────────────────────────────────────────────────


def test_seal_writes_chained_step_and_carries_knowns(trace_root):
    _r("start", "--session", "s1")
    _r("fact", "fact one", "--source", "test://1", "--method", "test_pass", "--session", "s1")
    assert _r("seal", "--session", "s1") == 0
    step0 = json.loads((trace_root / "traces" / "s1" / "step-0000.json").read_text())
    assert step0["step_index"] == 0
    assert step0["parent_hash"] is None
    assert len(step0["self_hash"]) == 64
    # Working advanced to step 1 with knowns carried forward (Invariant I4)
    w = _working(trace_root, "s1")
    assert w["step_index"] == 1
    assert len(w["knowns"]) == 1


def test_two_seals_chain_parent_hash(trace_root):
    _r("start", "--session", "s1")
    _r("fact", "fact one", "--source", "test://1", "--method", "test_pass", "--session", "s1")
    _r("seal", "--session", "s1")
    _r("fact", "fact two", "--source", "test://2", "--method", "test_pass", "--session", "s1")
    _r("seal", "--session", "s1")
    step0 = json.loads((trace_root / "traces" / "s1" / "step-0000.json").read_text())
    step1 = json.loads((trace_root / "traces" / "s1" / "step-0001.json").read_text())
    # step1.parent_hash must equal step0.self_hash — unbroken chain
    assert step1["parent_hash"] == step0["self_hash"]
    assert step1["step_index"] == 1


# ─── Render shows typed tags distinctly ──────────────────────────────────


def test_show_renders_fact_and_inference_distinctly(trace_root, capsys):
    _r("start", "--session", "s1")
    _r("fact", "verified thing", "--source", "test://1", "--method", "test_pass", "--session", "s1")
    _r("infer", "unverified conjecture", "--session", "s1")
    _r("seal", "--session", "s1")
    capsys.readouterr()
    _r("show", "--session", "s1")
    out = capsys.readouterr().out
    assert "<fact " in out
    assert "<inference " in out
    assert "verified thing" in out
    assert "unverified conjecture" in out
    # The inference must NOT appear inside the <facts> block.
    facts_block = out[out.find("<facts>"):out.find("</facts>")]
    assert "unverified conjecture" not in facts_block


# ─── Isolation from the signed-surface chain ─────────────────────────────


def test_trace_does_not_touch_reasoning_surface(trace_root):
    _r("start", "--session", "s1")
    _r("fact", "f", "--source", "test://1", "--method", "test_pass", "--session", "s1")
    _r("seal", "--session", "s1")
    # No reasoning-surface.json created by trace ops under EPISTEME_ROOT
    assert not (trace_root / "reasoning-surface.json").exists()
    # Trace artifacts confined to traces/<session>/
    assert (trace_root / "traces" / "s1" / "step-0000.json").exists()
    assert not (trace_root / "surfaces").exists()


def test_status_json_shape(trace_root, capsys):
    _r("start", "--session", "s1")
    _r("fact", "f", "--source", "test://1", "--method", "test_pass", "--session", "s1")
    _r("seal", "--session", "s1")
    capsys.readouterr()
    _r("status", "--session", "s1", "--format", "json")
    info = json.loads(capsys.readouterr().out)
    assert info["session"] == "s1"
    assert info["sealed_steps"] == 1
    assert info["working_step_index"] == 1
    assert info["head_self_hash"] is not None


def test_no_active_session_returns_no_session_exit(trace_root):
    rc = _r("fact", "orphan", "--source", "test://1", "--method", "test_pass")
    assert rc == 4  # EXIT_NO_SESSION


def test_trace_via_top_level_cli(trace_root, capsys):
    from episteme.cli import main
    assert main(["practice", "trace", "start", "--session", "s1"]) == 0
    capsys.readouterr()
    assert main(["practice", "trace", "status", "--session", "s1", "--format", "json"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["session"] == "s1"
