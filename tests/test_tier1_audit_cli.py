"""Event 135 — tests for `episteme tier1 audit` CLI."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


@pytest.fixture
def cli_module():
    # Add src/ to sys.path so the package import resolves the same way
    # pyproject's pythonpath does under pytest.
    src_dir = Path(__file__).resolve().parent.parent / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from episteme import _tier1_audit
    return _tier1_audit


def _seed_passing_telemetry(target: Path, count: int = 20) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    anchor = now - timedelta(days=8)
    with open(target, "a", encoding="utf-8") as f:
        for i in range(count):
            record = {
                "correlation_id": f"cid-{i}",
                "timestamp": (anchor + timedelta(hours=i * 8)).isoformat(),
                "pattern": "git push (non-protected branch)",
                "branch": "event-135",
                "rationale_one_line": "feature push — safe",
                "exit_code": 0,
                "operator_confirmed": True,
                "subsequent_revert_within_24h": False,
            }
            f.write(json.dumps(record) + "\n")


class TestTier1AuditCli:
    def test_empty_telemetry_exits_zero(self, cli_module, tmp_path, capsys):
        target = tmp_path / "tier1.jsonl"
        result = cli_module.run_tier1_cli(
            ["audit", "--telemetry-path", str(target)]
        )
        assert result == 0
        out = capsys.readouterr().out
        assert "SOAK GATE: CLOSED" in out
        assert "Records:            0" in out

    def test_passing_telemetry_reports_open_gate(
        self, cli_module, tmp_path, capsys
    ):
        target = tmp_path / "tier1.jsonl"
        _seed_passing_telemetry(target)
        result = cli_module.run_tier1_cli(
            ["audit", "--telemetry-path", str(target)]
        )
        assert result == 0
        out = capsys.readouterr().out
        assert "SOAK GATE: OPEN" in out
        assert "Records:            20" in out
        # Rationale-accuracy line is one of two formats; just check the
        # 100.00% literal is present.
        assert "100.00%" in out

    def test_require_open_exits_two_on_closed(self, cli_module, tmp_path):
        target = tmp_path / "tier1.jsonl"
        result = cli_module.run_tier1_cli(
            ["audit", "--telemetry-path", str(target), "--require-open"]
        )
        assert result == 2

    def test_require_open_exits_zero_when_open(self, cli_module, tmp_path):
        target = tmp_path / "tier1.jsonl"
        _seed_passing_telemetry(target)
        result = cli_module.run_tier1_cli(
            ["audit", "--telemetry-path", str(target), "--require-open"]
        )
        assert result == 0

    def test_json_output_parses(self, cli_module, tmp_path, capsys):
        target = tmp_path / "tier1.jsonl"
        _seed_passing_telemetry(target)
        cli_module.run_tier1_cli(
            ["audit", "--telemetry-path", str(target), "--json"]
        )
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["record_count"] == 20
        assert data["soak_gate_open"] is True
        assert data["thresholds"]["min_ops"] == 20

    def test_pattern_distribution_reported(
        self, cli_module, tmp_path, capsys
    ):
        target = tmp_path / "tier1.jsonl"
        _seed_passing_telemetry(target)
        # Add one record with a different pattern.
        with open(target, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "pattern": "gh issue/pr create/comment",
                "operator_confirmed": True,
                "subsequent_revert_within_24h": False,
            }) + "\n")
        cli_module.run_tier1_cli(
            ["audit", "--telemetry-path", str(target)]
        )
        out = capsys.readouterr().out
        assert "Pattern distribution" in out
        assert "git push (non-protected branch)" in out
        assert "gh issue/pr create/comment" in out
