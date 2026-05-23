"""Event 135 — tests for `episteme evaluate` CLI."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture
def cli_module():
    src_dir = Path(__file__).resolve().parent.parent / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from episteme import _evaluate
    return _evaluate


def _seed_audit_records(directory: Path, count: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "2026-05-23-audit.jsonl"
    with open(target, "a", encoding="utf-8") as f:
        for i in range(count):
            f.write(json.dumps({
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(hours=i)
                ).isoformat(),
                "command_executed": "git push origin event-135",
                "epistemic_prediction": "expected exit 0",
            }) + "\n")


def _seed_tier1_records(directory: Path, count: int, reverted: int = 0) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "tier1.jsonl"
    with open(target, "a", encoding="utf-8") as f:
        for i in range(count):
            f.write(json.dumps({
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(hours=i)
                ).isoformat(),
                "operator_confirmed": True,
                "subsequent_revert_within_24h": i < reverted,
            }) + "\n")


class TestEvaluateCli:
    def test_self_audit_empty_state(self, cli_module, tmp_path, capsys):
        result = cli_module.run_evaluate_cli([
            "self-audit", "--telemetry-dir", str(tmp_path / "missing"),
            "--json",
        ])
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert data["mode"] == "self-audit"
        assert data["verdict"] == "empty-state"

    def test_self_audit_calibrated(self, cli_module, tmp_path, capsys):
        _seed_audit_records(tmp_path, 10)
        result = cli_module.run_evaluate_cli([
            "self-audit", "--telemetry-dir", str(tmp_path),
            "--json",
        ])
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert data["high_impact_op_count"] == 10
        assert data["surface_authored_count"] == 10
        assert data["surface_authoring_rate"] == 1.0
        assert "calibrated" in data["verdict"]

    def test_self_audit_with_tier1_telemetry(self, cli_module, tmp_path, capsys):
        _seed_audit_records(tmp_path, 10)
        _seed_tier1_records(tmp_path, 5, reverted=0)
        result = cli_module.run_evaluate_cli([
            "self-audit", "--telemetry-dir", str(tmp_path),
            "--json",
        ])
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert data["tier1_total"] == 5
        assert data["tier1_confirmed"] == 5
        assert data["tier1_confirm_survival_rate"] == 1.0

    def test_challenge_set_returns_zero(self, cli_module, capsys):
        result = cli_module.run_evaluate_cli(["challenge-set", "--json"])
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert data["mode"] == "challenge-set"
        assert len(data["scenarios"]) >= 5
        # Each scenario has the required fields naming the System-1
        # failure mode the kernel's surface counters.
        for s in data["scenarios"]:
            assert "failure_mode" in s
            assert "surface_catches" in s

    def test_before_after_relative_specs(self, cli_module, tmp_path, capsys):
        _seed_audit_records(tmp_path, 5)
        # Use --flag=value form because relative specs start with `-` which
        # argparse would otherwise interpret as a flag.
        result = cli_module.run_evaluate_cli([
            "before-after", "--before=-7d", "--after=-1d",
            "--telemetry-dir", str(tmp_path),
        ])
        assert result == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["mode"] == "before-after"
        assert "before_window_end" in data
        assert "after_window_start" in data

    def test_before_after_bad_spec_returns_one(self, cli_module):
        result = cli_module.run_evaluate_cli([
            "before-after", "--before", "garbage", "--after=-1d",
        ])
        assert result == 1
