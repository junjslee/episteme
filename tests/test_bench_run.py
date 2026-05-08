"""Tests for `episteme bench run` paired-comparison runner harness.

Subprocess to ``claude`` is mocked — tests don't depend on ``claude`` CLI presence.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from episteme import _bench_run, _bench_task  # noqa: E402


def _scaffold_task(root: Path, combined_id: str) -> Path:
    return _bench_task.new_task(combined_id, project_root=root)


def _mock_subprocess_result(stdout="", stderr="", returncode=0):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


class ResolveTaskDir(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        _scaffold_task(self.root, "fence-reconstruction/01")

    def tearDown(self):
        self._td.cleanup()

    def test_finds_existing(self):
        td = _bench_run._resolve_task_dir(
            "fence-reconstruction/01",
            self.root / "benchmarks/cognitive-lift-baseline/tasks",
        )
        self.assertTrue(td.exists())

    def test_unknown_raises(self):
        with self.assertRaises(_bench_run.BenchRunError):
            _bench_run._resolve_task_dir(
                "fence-reconstruction/missing",
                self.root / "benchmarks/cognitive-lift-baseline/tasks",
            )

    def test_no_slash_raises(self):
        with self.assertRaises(_bench_run.BenchRunError):
            _bench_run._resolve_task_dir(
                "noslash",
                self.root / "benchmarks/cognitive-lift-baseline/tasks",
            )


class RunSessionMocked(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        _scaffold_task(self.root, "fence-reconstruction/01")

    def tearDown(self):
        self._td.cleanup()

    def _run(self, session, **overrides):
        with patch(
            "episteme._bench_run.subprocess.run",
            return_value=_mock_subprocess_result(stdout="agent answer"),
        ):
            return _bench_run.run_session(
                "fence-reconstruction/01", session,
                project_root=self.root,
                claude_command=["mock-claude"],
                user_settings_path=Path("/nonexistent"),
                **overrides,
            )

    def test_session_a_creates_run_artifacts(self):
        run_dir = self._run("A")
        self.assertTrue((run_dir / "metadata.json").exists())
        self.assertTrue((run_dir / "transcript.txt").exists())
        self.assertTrue((run_dir / "stderr.txt").exists())
        self.assertTrue((run_dir / "final_diff.txt").exists())

    def test_session_a_metadata(self):
        run_dir = self._run("A")
        meta = json.loads((run_dir / "metadata.json").read_text())
        self.assertEqual(meta["session"], "A")
        self.assertEqual(meta["task_id"], "fence-reconstruction/01")
        self.assertIn("wall_clock_seconds", meta)

    def test_session_a_no_kernel_settings(self):
        run_dir = self._run("A")
        settings = json.loads(
            (run_dir / "work" / ".claude" / "settings.json").read_text()
        )
        self.assertEqual(settings, {"hooks": {}})

    def test_session_b_strict_mode_no_advisory_marker(self):
        # Operator decision #4 (Event 116): strict mode for Session B.
        run_dir = self._run("B")
        episteme_dir = run_dir / "work" / ".episteme"
        self.assertTrue(episteme_dir.exists())
        self.assertFalse((episteme_dir / "advisory-surface").exists())

    def test_invalid_session_raises(self):
        with self.assertRaises(_bench_run.BenchRunError):
            _bench_run.run_session(
                "fence-reconstruction/01", "X",
                project_root=self.root,
                claude_command=["mock-claude"],
            )

    def test_transcript_capture(self):
        run_dir = self._run("A")
        self.assertEqual(
            (run_dir / "transcript.txt").read_text(),
            "agent answer",
        )


# ---------- Event 118 — v3 JSONL → text extractor ------------------------


class IsJsonlStream(unittest.TestCase):

    def test_jsonl_with_type_field(self):
        text = '{"type": "assistant", "message": {}}\n{"type": "result", "result": "ok"}\n'
        self.assertTrue(_bench_run._is_jsonl_stream(text))

    def test_text_mode_returns_false(self):
        self.assertFalse(_bench_run._is_jsonl_stream("just a plain text response"))

    def test_empty_returns_false(self):
        self.assertFalse(_bench_run._is_jsonl_stream(""))

    def test_json_without_type_returns_false(self):
        # JSON dict without 'type' field is not stream-json shape.
        self.assertFalse(_bench_run._is_jsonl_stream('{"foo": "bar"}'))


class ExtractHumanTranscript(unittest.TestCase):

    def test_assistant_text_block(self):
        jsonl = json.dumps({
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "hello world"}]},
        })
        out = _bench_run.extract_human_transcript_from_jsonl(jsonl)
        self.assertIn("hello world", out)

    def test_assistant_tool_use_block(self):
        jsonl = json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"path": "x.py"}},
            ]},
        })
        out = _bench_run.extract_human_transcript_from_jsonl(jsonl)
        self.assertIn("[Tool call: Read", out)
        self.assertIn("x.py", out)

    def test_user_tool_result_block(self):
        jsonl = json.dumps({
            "type": "user",
            "message": {"content": [
                {"type": "tool_result", "content": "file contents here"},
            ]},
        })
        out = _bench_run.extract_human_transcript_from_jsonl(jsonl)
        self.assertIn("[Tool result]", out)
        self.assertIn("file contents here", out)

    def test_system_hook_event(self):
        jsonl = json.dumps({
            "type": "system",
            "subtype": "hook_started",
            "hook_name": "PreToolUse:Bash",
            "hook_event": "PreToolUse",
        })
        out = _bench_run.extract_human_transcript_from_jsonl(jsonl)
        self.assertIn("hook_started", out)
        self.assertIn("PreToolUse", out)

    def test_result_event(self):
        jsonl = json.dumps({"type": "result", "result": "task complete"})
        out = _bench_run.extract_human_transcript_from_jsonl(jsonl)
        self.assertIn("[Final result]", out)
        self.assertIn("task complete", out)

    def test_truncates_long_tool_input(self):
        long_path = "x" * 500
        jsonl = json.dumps({
            "type": "assistant",
            "message": {"content": [
                {"type": "tool_use", "name": "Read", "input": {"path": long_path}},
            ]},
        })
        out = _bench_run.extract_human_transcript_from_jsonl(jsonl)
        self.assertIn("...[truncated]", out)

    def test_skips_unknown_event_types(self):
        jsonl = (
            json.dumps({"type": "rate_limit_event", "tokens": 100}) + "\n"
            + json.dumps({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "real content"}
            ]}})
        )
        out = _bench_run.extract_human_transcript_from_jsonl(jsonl)
        self.assertIn("real content", out)
        self.assertNotIn("rate_limit_event", out)

    def test_preserves_non_json_lines(self):
        jsonl = "non-json noise\n" + json.dumps({"type": "result", "result": "ok"})
        out = _bench_run.extract_human_transcript_from_jsonl(jsonl)
        self.assertIn("non-json noise", out)
        self.assertIn("[Final result]", out)


class RunSessionWritesBothTranscriptArtifacts(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        _scaffold_task(self.root, "fence-reconstruction/01")

    def tearDown(self):
        self._td.cleanup()

    def test_jsonl_stdout_writes_jsonl_and_extracted_text(self):
        jsonl_stdout = (
            json.dumps({
                "type": "assistant",
                "message": {"content": [{"type": "text", "text": "agent answer"}]},
            }) + "\n"
            + json.dumps({"type": "result", "result": "done"})
        )
        with patch(
            "episteme._bench_run.subprocess.run",
            return_value=_mock_subprocess_result(stdout=jsonl_stdout),
        ):
            run_dir = _bench_run.run_session(
                "fence-reconstruction/01", "B",
                project_root=self.root,
                claude_command=["mock-claude"],
                user_settings_path=Path("/nonexistent"),
            )
        # v3: both files present
        self.assertTrue((run_dir / "transcript.jsonl").exists())
        self.assertTrue((run_dir / "transcript.txt").exists())
        # Raw is JSONL; extracted is human-readable
        self.assertEqual((run_dir / "transcript.jsonl").read_text(), jsonl_stdout)
        extracted = (run_dir / "transcript.txt").read_text()
        self.assertIn("agent answer", extracted)
        self.assertIn("[Final result]", extracted)

    def test_text_mode_writes_only_transcript_txt(self):
        with patch(
            "episteme._bench_run.subprocess.run",
            return_value=_mock_subprocess_result(stdout="plain text answer"),
        ):
            run_dir = _bench_run.run_session(
                "fence-reconstruction/01", "A",
                project_root=self.root,
                claude_command=["mock-claude"],
                user_settings_path=Path("/nonexistent"),
            )
        self.assertTrue((run_dir / "transcript.txt").exists())
        self.assertFalse((run_dir / "transcript.jsonl").exists())
        self.assertEqual(
            (run_dir / "transcript.txt").read_text(),
            "plain text answer",
        )


if __name__ == "__main__":
    unittest.main()
