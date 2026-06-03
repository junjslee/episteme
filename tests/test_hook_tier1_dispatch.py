"""Event 135 — Stage 2b — tests for the live hook's Tier-1 advisory dispatch.

Exercises the `_try_tier1_dispatch` helper added to
`core/hooks/reasoning_surface_guard.py`. The tests confirm:

- Tier 1 op + valid micro-surface + soak gate open → dispatch returns
  True (the hook would exit 0 with a stderr advisory).
- Tier 2/3 op → dispatch returns False (existing strict-block path
  handles the op).
- Tier 1 op + missing micro-surface → False (loss-averse: fall through).
- Tier 1 op + invalid micro-surface (branch mismatch, stale, etc.) →
  False.
- Tier 1 op + valid micro-surface + soak gate CLOSED → False (the
  Stage 3 calibration gate keeps the advisory disabled until lived
  behavior clears the threshold).
- Any exception in classify/validate/soak → False (existing gate
  remains source of truth).

The hook is normally invoked as a subprocess by Claude Code; for unit
testing we import the module directly and call `_try_tier1_dispatch`.
"""
from __future__ import annotations

import importlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture
def hook_module(monkeypatch, tmp_path):
    """Patch the classifier module's disk-path globals to tmp_path; load
    the hook module (one-time import — subsequent tests reuse the same
    module instance). Critically, do NOT call importlib.reload — that
    creates a new Tier enum class which breaks identity equality with
    enum values already imported by sibling test modules."""
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from core.hooks import _irreversible_tier as it
    monkeypatch.setattr(it, "TIER1_TELEMETRY_PATH", tmp_path / "tier1.jsonl")
    monkeypatch.setattr(it, "_DERIVED_KNOBS_PATH", tmp_path / "derived.json")
    monkeypatch.setattr(it, "_OPERATOR_PROFILE_MD", tmp_path / "profile.md")

    hooks_dir = repo_root / "core" / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    if "reasoning_surface_guard" in sys.modules:
        hook = sys.modules["reasoning_surface_guard"]
    else:
        hook = importlib.import_module("reasoning_surface_guard")
    return hook, it


def _make_payload(branch: str, cwd: Path, cmd: str = "git push origin event-135") -> dict:
    return {
        "tool_name": "Bash",
        "cwd": str(cwd),
        "tool_input": {"command": cmd},
    }


def _seed_soak_passing_telemetry(it_module, tmp_path: Path) -> None:
    """Write 20 confirmed records spanning 8 days so the soak gate opens."""
    now = datetime.now(timezone.utc)
    anchor = now - timedelta(days=8)
    for i in range(20):
        record = {
            "correlation_id": f"cid-{i}",
            "timestamp": (anchor + timedelta(hours=i * 8)).isoformat(),
            "pattern": "git push (non-protected branch)",
            "branch": "event-135",
            "rationale_one_line": "feature push — safe; revert via gh pr close",
            "exit_code": 0,
            "operator_confirmed": True,
            "subsequent_revert_within_24h": False,
        }
        it_module.write_tier1_record(record)


def _write_micro_surface(cwd: Path, branch: str) -> None:
    surface_dir = cwd / ".episteme"
    surface_dir.mkdir(parents=True, exist_ok=True)
    micro = {
        "tier": 1,
        "branch": branch,
        "rationale_one_line": (
            "Pushing feature branch — no protected-branch impact; revert "
            "via gh pr close + git push origin --delete event-135."
        ),
        "disconfirmation_one_line": (
            "If pytest CI on the PR fails, close PR without merging."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    (surface_dir / "reasoning-surface.json").write_text(json.dumps(micro))


def _stub_git_context(it_module, monkeypatch, branch: str | None) -> None:
    """Force load_git_context to return a stub with the named branch."""
    def fake_loader(project_root=None):
        return it_module.GitContext(
            current_branch=branch,
            protected_branches=frozenset({"main", "master"}),
        )
    monkeypatch.setattr(it_module, "load_git_context", fake_loader)


class TestHookTier1Dispatch:
    def test_tier_1_with_valid_surface_and_open_gate_dispatches(
        self, hook_module, monkeypatch, tmp_path
    ):
        hook, it = hook_module
        _seed_soak_passing_telemetry(it, tmp_path)
        cwd = tmp_path / "repo"
        cwd.mkdir()
        _write_micro_surface(cwd, "event-135")
        _stub_git_context(it, monkeypatch, "event-135")

        payload = _make_payload("event-135", cwd)
        dispatched = hook._try_tier1_dispatch(payload, "Bash", "git push")
        assert dispatched is True

    def test_tier_2_op_does_not_dispatch(self, hook_module, monkeypatch, tmp_path):
        hook, it = hook_module
        _seed_soak_passing_telemetry(it, tmp_path)
        cwd = tmp_path / "repo"
        cwd.mkdir()
        _write_micro_surface(cwd, "main")
        _stub_git_context(it, monkeypatch, "main")  # push to protected → Tier 2

        payload = _make_payload("main", cwd, cmd="git push origin main")
        dispatched = hook._try_tier1_dispatch(payload, "Bash", "git push")
        assert dispatched is False

    def test_tier_3_op_does_not_dispatch(self, hook_module, monkeypatch, tmp_path):
        hook, it = hook_module
        _seed_soak_passing_telemetry(it, tmp_path)
        cwd = tmp_path / "repo"
        cwd.mkdir()
        _stub_git_context(it, monkeypatch, "main")

        payload = _make_payload("main", cwd, cmd="git push --force origin main")
        dispatched = hook._try_tier1_dispatch(payload, "Bash", "git push")
        assert dispatched is False

    def test_missing_micro_surface_does_not_dispatch(
        self, hook_module, monkeypatch, tmp_path
    ):
        hook, it = hook_module
        _seed_soak_passing_telemetry(it, tmp_path)
        cwd = tmp_path / "repo"
        cwd.mkdir()
        # No .episteme/reasoning-surface.json written
        _stub_git_context(it, monkeypatch, "event-135")

        payload = _make_payload("event-135", cwd)
        dispatched = hook._try_tier1_dispatch(payload, "Bash", "git push")
        assert dispatched is False

    def test_blueprint_surface_does_not_dispatch(
        self, hook_module, monkeypatch, tmp_path
    ):
        # An on-disk surface with Blueprint D shape (no tier=1 field) is
        # NOT a micro-surface and should fall through.
        hook, it = hook_module
        _seed_soak_passing_telemetry(it, tmp_path)
        cwd = tmp_path / "repo"
        cwd.mkdir()
        surface_dir = cwd / ".episteme"
        surface_dir.mkdir()
        (surface_dir / "reasoning-surface.json").write_text(json.dumps({
            "scenario": "cascade:architectural",
            "core_question": "Some Blueprint D question",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "knowns": ["..."],
            "unknowns": ["..."],
            "assumptions": ["..."],
            "disconfirmation": "...",
        }))
        _stub_git_context(it, monkeypatch, "event-135")

        payload = _make_payload("event-135", cwd)
        dispatched = hook._try_tier1_dispatch(payload, "Bash", "git push")
        assert dispatched is False

    def test_invalid_micro_surface_branch_mismatch_does_not_dispatch(
        self, hook_module, monkeypatch, tmp_path
    ):
        hook, it = hook_module
        _seed_soak_passing_telemetry(it, tmp_path)
        cwd = tmp_path / "repo"
        cwd.mkdir()
        _write_micro_surface(cwd, "wrong-branch")  # surface says wrong-branch
        _stub_git_context(it, monkeypatch, "event-135")  # actual branch differs

        payload = _make_payload("event-135", cwd)
        dispatched = hook._try_tier1_dispatch(payload, "Bash", "git push")
        assert dispatched is False  # context-bleed counter fires

    def test_closed_soak_gate_does_not_dispatch(
        self, hook_module, monkeypatch, tmp_path
    ):
        # Telemetry is empty → soak gate closed → dispatch falls through
        # even with everything else valid.
        hook, it = hook_module
        # NOTE: no _seed_soak_passing_telemetry call — empty tier1.jsonl
        cwd = tmp_path / "repo"
        cwd.mkdir()
        _write_micro_surface(cwd, "event-135")
        _stub_git_context(it, monkeypatch, "event-135")

        payload = _make_payload("event-135", cwd)
        dispatched = hook._try_tier1_dispatch(payload, "Bash", "git push")
        assert dispatched is False

    def test_risk_tolerance_zero_force_escalates_to_tier_2(
        self, hook_module, monkeypatch, tmp_path
    ):
        # OperatorProfile loader returns risk_tolerance=0 (incident mode)
        # → classify() forces Tier 2 even on the otherwise-Tier-1 op.
        # Dispatch should NOT fire.
        hook, it = hook_module
        _seed_soak_passing_telemetry(it, tmp_path)
        cwd = tmp_path / "repo"
        cwd.mkdir()
        _write_micro_surface(cwd, "event-135")
        _stub_git_context(it, monkeypatch, "event-135")

        # Override the loader to return incident-mode profile.
        monkeypatch.setattr(
            it,
            "load_operator_profile",
            lambda: it.OperatorProfile(risk_tolerance=0),
        )

        payload = _make_payload("event-135", cwd)
        dispatched = hook._try_tier1_dispatch(payload, "Bash", "git push")
        assert dispatched is False
