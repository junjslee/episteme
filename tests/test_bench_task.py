"""Tests for `episteme bench new-task` scaffolder."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from episteme import _bench_task  # noqa: E402


class CombinedIdParsing(unittest.TestCase):

    def test_valid(self):
        self.assertEqual(
            _bench_task.parse_combined_id("fence-reconstruction/01-soft-delete"),
            ("fence-reconstruction", "01-soft-delete"),
        )

    def test_missing_slash(self):
        with self.assertRaises(_bench_task.BenchTaskError):
            _bench_task.parse_combined_id("noslash")

    def test_unknown_category(self):
        with self.assertRaises(_bench_task.BenchTaskError):
            _bench_task.parse_combined_id("not-a-category/x")

    def test_invalid_task_id(self):
        with self.assertRaises(_bench_task.BenchTaskError):
            _bench_task.parse_combined_id("fence-reconstruction/UPPERCASE")

    def test_empty_segments(self):
        for combined in ("/", "fence-reconstruction/", "/foo", ""):
            with self.subTest(combined=combined):
                with self.assertRaises(_bench_task.BenchTaskError):
                    _bench_task.parse_combined_id(combined)


class NewTask(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_creates_4_artifacts(self):
        path = _bench_task.new_task(
            "fence-reconstruction/01-probe", project_root=self.root,
        )
        self.assertTrue((path / "README.md").exists())
        self.assertTrue((path / "grader.json").exists())
        self.assertTrue((path / "seed.json").exists())
        self.assertTrue((path / "repo-state").is_dir())

    def test_grader_json_carries_category_and_task_id(self):
        path = _bench_task.new_task(
            "axiomatic-judgment/01-conflicting", project_root=self.root,
        )
        grader = json.loads((path / "grader.json").read_text())
        self.assertEqual(grader["category"], "axiomatic-judgment")
        self.assertEqual(grader["task_id"], "01-conflicting")
        self.assertIn("ground_truth", grader)
        self.assertIn("failure_modes", grader)
        self.assertIn("disconfirmation_observables", grader)

    def test_seed_pins_sonnet_4_6(self):
        # Operator decision #2 (Event 116): Sonnet 4.6 single model.
        path = _bench_task.new_task(
            "consequence-chain/01-tf", project_root=self.root,
        )
        seed = json.loads((path / "seed.json").read_text())
        self.assertEqual(seed["model"], "claude-sonnet-4-6")

    def test_refuses_overwrite_without_force(self):
        _bench_task.new_task(
            "fence-reconstruction/01", project_root=self.root,
        )
        with self.assertRaises(_bench_task.BenchTaskError):
            _bench_task.new_task(
                "fence-reconstruction/01", project_root=self.root,
            )

    def test_force_overwrites(self):
        _bench_task.new_task(
            "fence-reconstruction/01", project_root=self.root,
        )
        path = _bench_task.new_task(
            "fence-reconstruction/01", project_root=self.root, force=True,
        )
        self.assertTrue((path / "README.md").exists())

    def test_all_four_categories_accepted(self):
        for i, cat in enumerate(_bench_task.CATEGORIES):
            with self.subTest(category=cat):
                _bench_task.new_task(
                    f"{cat}/0{i}-x", project_root=self.root,
                )


if __name__ == "__main__":
    unittest.main()
