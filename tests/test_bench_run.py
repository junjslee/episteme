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


if __name__ == "__main__":
    unittest.main()
