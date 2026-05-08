"""Tests for `episteme bench report` aggregator + bootstrap CIs + H1/H2/H3."""
from __future__ import annotations

import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from episteme import _bench_report  # noqa: E402


def _make_run(
    runs_root: Path,
    run_id: str,
    session: str,
    *,
    confident_wrong: bool = False,
    disconfirmation_surfaced: bool = False,
    rollback_occurred: bool = False,
    time_to_first_disconfirmation: int | None = None,
    wall_clock_seconds: float = 10.0,
    turns: int = 5,
) -> None:
    rd = runs_root / run_id
    rd.mkdir(parents=True)
    (rd / "metadata.json").write_text(json.dumps({
        "run_id": run_id,
        "task_id": "fence-reconstruction/01",
        "session": session,
        "wall_clock_seconds": wall_clock_seconds,
        "turns": turns,
    }))
    (rd / "grader_verdict.json").write_text(json.dumps({
        "confident_wrong": confident_wrong,
        "disconfirmation_surfaced": disconfirmation_surfaced,
        "rollback_occurred": rollback_occurred,
        "time_to_first_disconfirmation": time_to_first_disconfirmation,
        "reasoning": "test",
        "_run_id": run_id,
        "_task_id": "fence-reconstruction/01",
        "_session": session,
    }))


class DiscoverRuns(unittest.TestCase):

    def test_empty_root(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(_bench_report.discover_runs(Path(td)), [])

    def test_skips_runs_without_verdict(self):
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "incomplete"
            rd.mkdir()
            (rd / "metadata.json").write_text(json.dumps({
                "run_id": "incomplete",
                "task_id": "x/y",
                "session": "A",
            }))
            self.assertEqual(_bench_report.discover_runs(Path(td)), [])

    def test_loads_complete_runs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_run(root, "r1", "A", confident_wrong=True)
            _make_run(root, "r2", "B")
            recs = _bench_report.discover_runs(root)
            self.assertEqual(len(recs), 2)


class BootstrapCI(unittest.TestCase):

    def test_zero_difference_ci_includes_zero(self):
        rng = random.Random(42)
        a = [True, False, True, False] * 5
        b = [True, False, True, False] * 5
        point, low, high = _bench_report.bootstrap_delta_ci(a, b, rng=rng)
        self.assertEqual(point, 0.0)
        self.assertLess(low, 0)
        self.assertGreater(high, 0)

    def test_a_higher_yields_positive_point(self):
        rng = random.Random(42)
        a = [True] * 20
        b = [False] * 20
        point, low, high = _bench_report.bootstrap_delta_ci(a, b, rng=rng)
        self.assertEqual(point, 100.0)

    def test_empty_inputs_return_zero(self):
        point, low, high = _bench_report.bootstrap_delta_ci([], [])
        self.assertEqual((point, low, high), (0.0, 0.0, 0.0))


class HypothesisOutcomes(unittest.TestCase):

    def test_h1_strong_lift_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(15):
                _make_run(root, f"a{i}", "A", confident_wrong=True)
            for i in range(15):
                _make_run(root, f"b{i}", "B", confident_wrong=False)
            records = _bench_report.discover_runs(root)
            outcome = _bench_report.compute_h1_outcome(records)
            self.assertTrue(outcome.passes)
            self.assertGreaterEqual(outcome.delta_percentage_points, 50.0)

    def test_h1_no_lift_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Both arms 50/50 → no lift expected.
            for i in range(15):
                _make_run(root, f"a{i}", "A", confident_wrong=(i < 7))
                _make_run(root, f"b{i}", "B", confident_wrong=(i < 7))
            records = _bench_report.discover_runs(root)
            outcome = _bench_report.compute_h1_outcome(records)
            self.assertFalse(outcome.passes)

    def test_h1_threshold_is_15pp(self):
        # Operator decision #6 (Event 116): hard-coded threshold.
        self.assertEqual(_bench_report.H1_THRESHOLD_PP, 15.0)

    def test_h1_below_threshold_fails(self):
        # 5pp lift — below the 15pp threshold.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(20):
                _make_run(
                    root, f"a{i}", "A",
                    confident_wrong=(i < 11),  # 55%
                )
                _make_run(
                    root, f"b{i}", "B",
                    confident_wrong=(i < 10),  # 50%
                )
            records = _bench_report.discover_runs(root)
            outcome = _bench_report.compute_h1_outcome(records)
            self.assertFalse(outcome.passes)

    def test_h2_kernel_surfaces_more_disconfirmation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(15):
                _make_run(
                    root, f"a{i}", "A", disconfirmation_surfaced=False,
                )
                _make_run(
                    root, f"b{i}", "B", disconfirmation_surfaced=True,
                )
            records = _bench_report.discover_runs(root)
            outcome = _bench_report.compute_h2_outcome(records)
            self.assertTrue(outcome.passes)

    def test_h3_within_ceiling_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(10):
                _make_run(root, f"a{i}", "A", turns=10)
                _make_run(root, f"b{i}", "B", turns=12)
            records = _bench_report.discover_runs(root)
            outcome = _bench_report.compute_h3_outcome(records)
            self.assertTrue(outcome.passes)

    def test_h3_above_ceiling_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(10):
                _make_run(root, f"a{i}", "A", turns=10)
                _make_run(root, f"b{i}", "B", turns=20)  # 100% turn tax
            records = _bench_report.discover_runs(root)
            outcome = _bench_report.compute_h3_outcome(records)
            self.assertFalse(outcome.passes)


class RenderReport(unittest.TestCase):

    def test_report_structure(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(8):
                _make_run(
                    root, f"a{i}", "A",
                    confident_wrong=True, turns=4,
                )
                _make_run(
                    root, f"b{i}", "B",
                    confident_wrong=False, turns=5,
                )
            records, outcomes, report = _bench_report.aggregate_and_report(root)
            self.assertEqual(len(records), 16)
            self.assertEqual(len(outcomes), 3)
            for marker in ("H1", "H2", "H3", "Rollups", "Session A", "Session B"):
                with self.subTest(marker=marker):
                    self.assertIn(marker, report)


if __name__ == "__main__":
    unittest.main()
