"""Tests for `episteme bench grade` blind LLM grader."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from episteme import _bench_grade, _bench_task  # noqa: E402


class BlindTranscript(unittest.TestCase):

    def test_strips_kernel_paths(self):
        s = "I edited .episteme/reasoning-surface.json today"
        out = _bench_grade.blind_transcript(s)
        self.assertNotIn(".episteme/reasoning-surface.json", out)
        self.assertIn("[blinded]", out)

    def test_strips_blueprint_d_phrase(self):
        s = "Blueprint D fired against my action"
        out = _bench_grade.blind_transcript(s)
        self.assertNotIn("Blueprint D", out)

    def test_strips_episteme_token(self):
        s = "the episteme kernel rejected my plan"
        out = _bench_grade.blind_transcript(s)
        self.assertNotIn("episteme", out.lower())

    def test_strips_reasoning_surface_phrase(self):
        s = "Reasoning Surface stale advisory"
        out = _bench_grade.blind_transcript(s)
        self.assertNotIn("Reasoning Surface", out)

    def test_preserves_non_kernel_content(self):
        s = "The agent applied a migration to the orders table"
        out = _bench_grade.blind_transcript(s)
        self.assertIn("orders table", out)


class ExtractJsonVerdict(unittest.TestCase):

    def test_extracts_clean_json(self):
        out = (
            '{"confident_wrong": true, "disconfirmation_surfaced": false, '
            '"rollback_occurred": false, "time_to_first_disconfirmation": null, '
            '"reasoning": "x"}'
        )
        v = _bench_grade.extract_json_verdict(out)
        self.assertTrue(v["confident_wrong"])

    def test_extracts_from_prose_wrap(self):
        out = (
            'Here is the verdict:\n\n'
            '{"confident_wrong": false, "disconfirmation_surfaced": true, '
            '"rollback_occurred": false, "time_to_first_disconfirmation": 3, '
            '"reasoning": "agent named falsifier early"}\n\n'
            'Thanks.'
        )
        v = _bench_grade.extract_json_verdict(out)
        self.assertFalse(v["confident_wrong"])
        self.assertEqual(v["time_to_first_disconfirmation"], 3)

    def test_raises_on_no_json(self):
        with self.assertRaises(_bench_grade.BenchGradeError):
            _bench_grade.extract_json_verdict("just prose, no JSON")


class ValidateVerdict(unittest.TestCase):

    def _good(self, **overrides):
        v = {
            "confident_wrong": False,
            "disconfirmation_surfaced": True,
            "rollback_occurred": False,
            "time_to_first_disconfirmation": 5,
            "depth_of_analysis": 6,
            "reasoning": "ok",
        }
        v.update(overrides)
        return v

    def test_good_passes(self):
        _bench_grade.validate_verdict(self._good())

    def test_missing_required_field(self):
        v = self._good()
        del v["reasoning"]
        with self.assertRaises(_bench_grade.BenchGradeError):
            _bench_grade.validate_verdict(v)

    def test_bool_field_must_be_bool(self):
        with self.assertRaises(_bench_grade.BenchGradeError):
            _bench_grade.validate_verdict(self._good(confident_wrong="yes"))

    def test_ttfd_null_ok(self):
        _bench_grade.validate_verdict(
            self._good(time_to_first_disconfirmation=None)
        )

    def test_ttfd_negative_rejected(self):
        with self.assertRaises(_bench_grade.BenchGradeError):
            _bench_grade.validate_verdict(
                self._good(time_to_first_disconfirmation=-1)
            )

    def test_depth_in_range_passes(self):
        for d in (0, 5, 10):
            with self.subTest(depth=d):
                _bench_grade.validate_verdict(self._good(depth_of_analysis=d))

    def test_depth_below_zero_rejected(self):
        with self.assertRaises(_bench_grade.BenchGradeError):
            _bench_grade.validate_verdict(self._good(depth_of_analysis=-1))

    def test_depth_above_ten_rejected(self):
        with self.assertRaises(_bench_grade.BenchGradeError):
            _bench_grade.validate_verdict(self._good(depth_of_analysis=11))

    def test_depth_bool_rejected(self):
        # bool is int subclass in Python; must explicitly reject.
        with self.assertRaises(_bench_grade.BenchGradeError):
            _bench_grade.validate_verdict(self._good(depth_of_analysis=True))

    def test_depth_float_rejected(self):
        with self.assertRaises(_bench_grade.BenchGradeError):
            _bench_grade.validate_verdict(self._good(depth_of_analysis=5.5))

    def test_reasoning_must_be_string(self):
        with self.assertRaises(_bench_grade.BenchGradeError):
            _bench_grade.validate_verdict(self._good(reasoning=12345))


class GradeRunIntegration(unittest.TestCase):
    """End-to-end with subprocess mocked."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        _bench_task.new_task("fence-reconstruction/01", project_root=self.root)
        run_dir = (
            self.root / "benchmarks/cognitive-lift-baseline/runs" / "test-run"
        )
        run_dir.mkdir(parents=True)
        (run_dir / "metadata.json").write_text(json.dumps({
            "run_id": "test-run",
            "task_id": "fence-reconstruction/01",
            "session": "B",
            "wall_clock_seconds": 12.3,
            "returncode": 0,
        }))
        (run_dir / "transcript.txt").write_text("agent did the thing")
        (run_dir / "final_diff.txt").write_text("diff")

    def tearDown(self):
        self._td.cleanup()

    def test_grade_run_writes_verdict(self):
        m = MagicMock()
        m.stdout = (
            '{"confident_wrong": false, "disconfirmation_surfaced": true, '
            '"rollback_occurred": false, "time_to_first_disconfirmation": 2, '
            '"depth_of_analysis": 7, "reasoning": "ok"}'
        )
        m.stderr = ""
        m.returncode = 0
        with patch("episteme._bench_grade.subprocess.run", return_value=m):
            verdict = _bench_grade.grade_run(
                "test-run", project_root=self.root,
                grader_command=["mock-grader"],
            )
        self.assertFalse(verdict["confident_wrong"])
        self.assertEqual(verdict["_run_id"], "test-run")
        self.assertEqual(verdict["_session"], "B")
        verdict_file = (
            self.root / "benchmarks/cognitive-lift-baseline/runs/test-run"
            / "grader_verdict.json"
        )
        self.assertTrue(verdict_file.exists())

    def test_grade_run_missing_run(self):
        with self.assertRaises(_bench_grade.BenchGradeError):
            _bench_grade.grade_run(
                "nonexistent-run", project_root=self.root,
                grader_command=["mock-grader"],
            )


if __name__ == "__main__":
    unittest.main()
