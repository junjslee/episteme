import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.hooks import calibration_telemetry as tel


class CalibrationTelemetryTests(unittest.TestCase):
    def _run(self, payload: dict) -> int:
        raw = json.dumps(payload)
        with patch("sys.stdin", new=io.StringIO(raw)):
            return tel.main()

    def _read_telemetry(self, home: Path) -> list[dict]:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tpath = home / ".episteme" / "telemetry" / f"{day}-audit.jsonl"
        if not tpath.exists():
            return []
        return [
            json.loads(ln)
            for ln in tpath.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]

    def test_non_bash_tool_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run({"tool_name": "Edit", "tool_input": {"file_path": "x.py"}})
            self.assertEqual(rc, 0)
            self.assertEqual(self._read_telemetry(home), [])

    def test_bash_outcome_with_exit_code_is_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "git push origin main"},
                        "tool_use_id": "tu_abc",
                        "tool_response": {"exit_code": 0, "is_error": False},
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            records = self._read_telemetry(home)
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec["event"], "outcome")
            self.assertEqual(rec["correlation_id"], "tu_abc")
            self.assertEqual(rec["command_executed"], "git push origin main")
            self.assertEqual(rec["exit_code"], 0)
            self.assertEqual(rec["status"], "success")

    def test_bash_failure_outcome_is_recorded(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "npm publish"},
                        "tool_use_id": "tu_xyz",
                        "tool_response": {"exit_code": 1, "is_error": True},
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            records = self._read_telemetry(home)
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertEqual(rec["exit_code"], 1)
            self.assertEqual(rec["status"], "error")

    def test_missing_exit_code_fields_still_records_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "ls"},
                        "tool_response": {},
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            records = self._read_telemetry(home)
            self.assertEqual(len(records), 1)
            rec = records[0]
            self.assertIsNone(rec["exit_code"])
            self.assertEqual(rec["status"], "unknown")

    def test_returncode_fallback_field_is_honored(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "ls"},
                        "tool_response": {"returncode": 127},
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            records = self._read_telemetry(home)
            self.assertEqual(records[0]["exit_code"], 127)

    def test_empty_command_is_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {"tool_name": "Bash", "tool_input": {}, "tool_response": {"exit_code": 0}}
                )
            self.assertEqual(rc, 0)
            self.assertEqual(self._read_telemetry(home), [])

    def test_hook_never_raises_on_malformed_payload(self):
        with patch("sys.stdin", new=io.StringIO("not json {")):
            self.assertEqual(tel.main(), 0)
        with patch("sys.stdin", new=io.StringIO("")):
            self.assertEqual(tel.main(), 0)

    def test_claude_code_isError_camelCase_maps_to_exit_code(self):
        """Event 49 · CP-TEL-01 regression pin — Claude Code's Bash
        tool_response uses camelCase `isError` + no numeric exit_code.
        The extractor must map isError True→1 / False→0 and set status."""
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "true"},
                        "tool_response": {
                            "stdout": "",
                            "stderr": "",
                            "interrupted": False,
                            "isError": False,
                        },
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            recs = self._read_telemetry(home)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["exit_code"], 0)
            self.assertEqual(recs[0]["status"], "success")

    def test_claude_code_isError_true_maps_to_exit_code_one(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "false"},
                        "tool_response": {
                            "stdout": "",
                            "stderr": "exit 1",
                            "interrupted": False,
                            "isError": True,
                        },
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            recs = self._read_telemetry(home)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["exit_code"], 1)
            self.assertEqual(recs[0]["status"], "error")

    def test_snake_case_is_error_still_supported(self):
        """Regression — pre-Event-49 snake_case path preserved for
        other runtimes / test corpora."""
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "true"},
                        "tool_response": {"is_error": False},
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            recs = self._read_telemetry(home)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["exit_code"], 0)
            self.assertEqual(recs[0]["status"], "success")

    def test_claude_code_rci_none_is_success(self):
        """Event 49 · CP-TEL-01 — Claude Code actual payload shape:
        `returnCodeInterpretation: None` + `interrupted: False` means
        the command succeeded. No numeric exit_code field exists."""
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "echo hi"},
                        "tool_response": {
                            "stdout": "hi\n",
                            "stderr": "",
                            "interrupted": False,
                            "isImage": False,
                            "returnCodeInterpretation": None,
                        },
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            recs = self._read_telemetry(home)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["exit_code"], 0)
            self.assertEqual(recs[0]["status"], "success")

    def test_claude_code_rci_nonempty_is_error(self):
        """Event 49 · CP-TEL-01 — non-empty returnCodeInterpretation
        means command failed. Unparseable text defaults to exit 1."""
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "ls /nonexistent"},
                        "tool_response": {
                            "stdout": "",
                            "stderr": "No such file or directory",
                            "interrupted": False,
                            "returnCodeInterpretation": "No matches found",
                        },
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            recs = self._read_telemetry(home)
            self.assertEqual(len(recs), 1)
            self.assertEqual(recs[0]["exit_code"], 1)
            self.assertEqual(recs[0]["status"], "error")

    def test_claude_code_rci_with_exit_code_parsed(self):
        """Event 49 · CP-TEL-01 — when rci carries 'exit code N',
        extract N."""
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "exit 42"},
                        "tool_response": {
                            "interrupted": False,
                            "returnCodeInterpretation": "command exited with exit code 42",
                        },
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            recs = self._read_telemetry(home)
            self.assertEqual(recs[0]["exit_code"], 42)

    def test_claude_code_interrupted_is_sigint_convention(self):
        """Event 49 · CP-TEL-01 — interrupted True maps to 130."""
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with patch.object(tel.Path, "home", return_value=home):
                rc = self._run(
                    {
                        "tool_name": "Bash",
                        "tool_input": {"command": "sleep 60"},
                        "tool_response": {
                            "interrupted": True,
                            "returnCodeInterpretation": None,
                        },
                        "cwd": str(home),
                    }
                )
            self.assertEqual(rc, 0)
            recs = self._read_telemetry(home)
            self.assertEqual(recs[0]["exit_code"], 130)
            self.assertEqual(recs[0]["status"], "error")


if __name__ == "__main__":
    unittest.main()
