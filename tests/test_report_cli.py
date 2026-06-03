"""Tests for `episteme report` CLI (value-visibility report).

Mirrors tests/test_evaluate_cli.py: sys.path insert of src/, tmp_path JSONL
seeders, capsys capture, and EPISTEME_NO_RICH=1 (via monkeypatch) for
deterministic ASCII output with no ANSI escapes.
"""
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
    from episteme import _report
    return _report


@pytest.fixture(autouse=True)
def _ascii(monkeypatch):
    """Force deterministic plain-ASCII rendering across every test."""
    monkeypatch.setenv("EPISTEME_NO_RICH", "1")


def _seed_audit(path: Path, ops: list[tuple[str, str]]) -> None:
    """Seed ~/.episteme/audit.jsonl-shaped records.

    `ops` is a list of (op_label, action) tuples. Action is one of
    passed / advisory / blocked — matching reasoning_surface_guard._write_audit.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for i, (op, action) in enumerate(ops):
            f.write(json.dumps({
                "ts": (
                    datetime.now(timezone.utc) - timedelta(hours=i)
                ).isoformat(),
                "tool": "Bash",
                "op": op,
                "cwd": "/repo",
                "status": "ok" if action == "passed" else "missing",
                "action": action,
                "mode": "strict",
            }) + "\n")


def _seed_calibration(
    directory: Path,
    day: str,
    pairs: list[int],
    ts_key: str = "ts",
) -> None:
    """Seed a day-scoped *-audit.jsonl with paired prediction+outcome records.

    `pairs` is a list of exit codes; each entry becomes one prediction +
    one outcome sharing a correlation_id, timestamped on `day` (YYYY-MM-DD).
    `ts_key` lets a test prove the reader keys on 'ts' (the runtime key).
    """
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{day}-audit.jsonl"
    ts = f"{day}T12:00:00+00:00"
    with open(target, "a", encoding="utf-8") as f:
        for i, exit_code in enumerate(pairs):
            cid = f"{day}-{i}"
            f.write(json.dumps({
                ts_key: ts,
                "event": "prediction",
                "correlation_id": cid,
                "exit_code": None,
            }) + "\n")
            f.write(json.dumps({
                ts_key: ts,
                "event": "outcome",
                "correlation_id": cid,
                "exit_code": exit_code,
            }) + "\n")


def _seed_tier1(directory: Path, count: int, span_days: int = 8) -> Path:
    """Seed tier1.jsonl with `count` operator-confirmed, non-reverted records
    spread across `span_days` so the soak gate can open. Returns the path."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "tier1.jsonl"
    now = datetime.now(timezone.utc)
    with open(target, "a", encoding="utf-8") as f:
        for i in range(count):
            # First record dated span_days ago to satisfy calendar span.
            offset = span_days if i == 0 else (i % span_days)
            f.write(json.dumps({
                "timestamp": (now - timedelta(days=offset)).isoformat(),
                "pattern": "git push (non-protected branch)",
                "operator_confirmed": True,
                "subsequent_revert_within_24h": False,
            }) + "\n")
    return target


def _empty_args(tmp_path: Path) -> list[str]:
    """Args pointing every store at a fresh, empty location."""
    return [
        "--telemetry-dir", str(tmp_path / "telemetry"),
        "--audit-path", str(tmp_path / "audit.jsonl"),
        "--tier1-path", str(tmp_path / "telemetry" / "tier1.jsonl"),
    ]


class TestReportEmptyState:
    def test_empty_state_renders_worked_example_not_empty_box(
        self, cli_module, tmp_path, capsys
    ):
        # No --demo, no telemetry → must fall through to the worked example.
        result = cli_module.run_report_cli(_empty_args(tmp_path))
        assert result == 0
        out = capsys.readouterr().out
        # The worked-example banner is present.
        assert "WORKED EXAMPLE" in out
        # The one-line empty-state notice is present.
        assert "No telemetry yet" in out
        # The worked-example numbers are present (47/52, the buckets).
        assert "47" in out and "52" in out
        assert "31" in out  # WYSIATI demo count
        assert "12" in out  # cascade demo count
        assert "6" in out   # fence demo count
        # NEVER an empty box: there is real content between box borders.
        assert "Surface Authoring" in out
        # No empty bordered region (a line that is just border + spaces).
        assert "|  |" not in out

    def test_empty_state_exit_zero(self, cli_module, tmp_path, capsys):
        result = cli_module.run_report_cli(_empty_args(tmp_path))
        capsys.readouterr()
        assert result == 0


class TestReportDemoFlag:
    def test_demo_renders_all_five_section_headers(
        self, cli_module, tmp_path, capsys
    ):
        result = cli_module.run_report_cli(["--demo", *_empty_args(tmp_path)])
        assert result == 0
        out = capsys.readouterr().out
        for header in (
            "Surface Authoring",
            "Failure Modes Countered",
            "Tier-1 Soak",
            "Calibration Trend",
            "Verdict",
        ):
            assert header in out, f"missing section: {header}"
        assert "(worked example)" in out

    def test_demo_via_json_marks_is_demo(self, cli_module, tmp_path, capsys):
        result = cli_module.run_report_cli([
            "--demo", "--json", *_empty_args(tmp_path)
        ])
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert data["is_demo"] is True
        assert data["surface"]["authored"] == 47
        assert data["surface"]["total"] == 52
        assert data["verdict"].startswith("(worked example)")


class TestReportPopulatedState:
    def test_populated_state_renders_real_numbers(
        self, cli_module, tmp_path, capsys
    ):
        audit_path = tmp_path / "audit.jsonl"
        _seed_audit(audit_path, [
            ("git push origin feat", "passed"),
            ("npm publish", "passed"),
            ("cascade:metric-dip", "advisory"),
            ("gh pr merge", "blocked"),  # not counted in failure modes
        ])
        result = cli_module.run_report_cli([
            "--json",
            "--telemetry-dir", str(tmp_path / "telemetry"),
            "--audit-path", str(audit_path),
            "--tier1-path", str(tmp_path / "telemetry" / "tier1.jsonl"),
        ])
        assert result == 0
        data = json.loads(capsys.readouterr().out)
        assert data["is_demo"] is False
        assert data["surface"]["total"] == 4
        assert data["surface"]["authored"] == 2
        assert data["surface"]["rate"] == 0.5

    def test_failure_mode_bucketing(self, cli_module, tmp_path, capsys):
        audit_path = tmp_path / "audit.jsonl"
        _seed_audit(audit_path, [
            ("git push origin feat", "passed"),    # WYSIATI
            ("terraform apply", "passed"),          # WYSIATI
            ("SQL DROP TABLE", "advisory"),         # WYSIATI
            ("cascade:metric-dip", "passed"),       # cascade
            ("cascade:rollback", "advisory"),       # cascade
            ("fence:removed-guard", "passed"),      # fence
            ("git push other", "blocked"),          # not counted (blocked)
        ])
        result = cli_module.run_report_cli([
            "--json",
            "--telemetry-dir", str(tmp_path / "telemetry"),
            "--audit-path", str(audit_path),
            "--tier1-path", str(tmp_path / "telemetry" / "tier1.jsonl"),
        ])
        assert result == 0
        fm = json.loads(capsys.readouterr().out)["failure_modes"]
        assert fm[cli_module._FM_WYSIATI] == 3
        assert fm[cli_module._FM_CASCADE] == 2
        assert fm[cli_module._FM_FENCE] == 1

    def test_calibration_series_from_paired_telemetry_reading_ts(
        self, cli_module, tmp_path, capsys
    ):
        tel = tmp_path / "telemetry"
        # Day 1: 4 ops, 3 exit-0 → 0.75. Day 2: 4 ops, 4 exit-0 → 1.0.
        _seed_calibration(tel, "2026-05-20", [0, 0, 0, 1], ts_key="ts")
        _seed_calibration(tel, "2026-05-21", [0, 0, 0, 0], ts_key="ts")
        # Also seed surface data so the report doesn't fall through to demo.
        audit_path = tmp_path / "audit.jsonl"
        _seed_audit(audit_path, [("git push origin feat", "passed")])
        result = cli_module.run_report_cli([
            "--json",
            "--telemetry-dir", str(tel),
            "--audit-path", str(audit_path),
            "--tier1-path", str(tel / "tier1.jsonl"),
        ])
        assert result == 0
        cal = json.loads(capsys.readouterr().out)["calibration"]
        # exit_code==0 is "success" → fraction exit_code==0 per day.
        assert cal["series"] == [0.75, 1.0]
        assert cal["paired_ops"] == 8
        assert cal["days_tracked"] == 2

    def test_calibration_reads_ts_not_timestamp(
        self, cli_module, tmp_path, capsys
    ):
        """The critical-bug guard: records keyed on 'ts' (runtime shape) must
        be read; records keyed only on 'timestamp' is the fallback path."""
        tel = tmp_path / "telemetry"
        _seed_calibration(tel, "2026-05-20", [0, 0, 1], ts_key="ts")
        audit_path = tmp_path / "audit.jsonl"
        _seed_audit(audit_path, [("git push origin feat", "passed")])
        result = cli_module.run_report_cli([
            "--json",
            "--telemetry-dir", str(tel),
            "--audit-path", str(audit_path),
            "--tier1-path", str(tel / "tier1.jsonl"),
        ])
        assert result == 0
        cal = json.loads(capsys.readouterr().out)["calibration"]
        # 3 paired ops on one day → series is non-empty (would be [] if the
        # reader keyed only on 'timestamp'). JSON rounds the fraction to 4 dp.
        assert cal["series"] == [round(2 / 3, 4)]
        assert cal["days_tracked"] == 1


class TestReportTier1:
    def test_tier1_progress_uses_soak_gate_open(
        self, cli_module, tmp_path, capsys
    ):
        tel = tmp_path / "telemetry"
        tier1_path = _seed_tier1(tel, count=20, span_days=8)
        audit_path = tmp_path / "audit.jsonl"
        _seed_audit(audit_path, [("git push origin feat", "passed")])
        result = cli_module.run_report_cli([
            "--json",
            "--telemetry-dir", str(tel),
            "--audit-path", str(audit_path),
            "--tier1-path", str(tier1_path),
        ])
        assert result == 0
        tier1 = json.loads(capsys.readouterr().out)["tier1"]
        assert tier1["ops"] == 20
        # 20 ops, 8d span, 100% accuracy → gate OPEN per soak_gate_open.
        assert tier1["gate_open"] is True
        assert tier1["accuracy"] == 1.0

    def test_tier1_gate_closed_below_floor(self, cli_module, tmp_path, capsys):
        tel = tmp_path / "telemetry"
        tier1_path = _seed_tier1(tel, count=5, span_days=8)
        audit_path = tmp_path / "audit.jsonl"
        _seed_audit(audit_path, [("git push origin feat", "passed")])
        result = cli_module.run_report_cli([
            "--json",
            "--telemetry-dir", str(tel),
            "--audit-path", str(audit_path),
            "--tier1-path", str(tier1_path),
        ])
        assert result == 0
        tier1 = json.loads(capsys.readouterr().out)["tier1"]
        assert tier1["ops"] == 5
        assert tier1["gate_open"] is False  # 5 < 20 floor


class TestReportJsonPurity:
    def test_json_is_pure_json_no_ansi(self, cli_module, tmp_path, capsys):
        # Even with a populated report, --json must be machine-parseable and
        # carry no ANSI escape sequences.
        audit_path = tmp_path / "audit.jsonl"
        _seed_audit(audit_path, [
            ("git push origin feat", "passed"),
            ("cascade:x", "advisory"),
        ])
        result = cli_module.run_report_cli([
            "--json",
            "--telemetry-dir", str(tmp_path / "telemetry"),
            "--audit-path", str(audit_path),
            "--tier1-path", str(tmp_path / "telemetry" / "tier1.jsonl"),
        ])
        assert result == 0
        out = capsys.readouterr().out
        assert "\033" not in out
        json.loads(out)  # must parse cleanly
