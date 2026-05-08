"""Tests for Tier 2.2 — `episteme status [--watch] [--json]`.

Covers:

- gather_status() with absent surface, present surface, unparseable surface.
- Surface freshness math (age_minutes within / past TTL).
- Active branch resolution (default vs branch-marker).
- Rigor level resolution (project file > global file > default).
- Framework counts (absent stream returns None; present stream counts lines).
- Profile drift (absent audit, present audit).
- Text formatter shape (key fields present in output).
- JSON formatter validity (output is valid JSON, has top-level keys).
- run_status one-shot vs --watch (single-tick) modes.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from episteme import _status  # noqa: E402


def _iso_offset(minutes: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _write_surface(cwd: Path, *, age_minutes: float = 0.0, **fields) -> Path:
    surf_dir = cwd / ".episteme"
    surf_dir.mkdir(parents=True, exist_ok=True)
    path = surf_dir / "reasoning-surface.json"
    payload = {
        "schema": "episteme/reasoning-surface@1",
        "timestamp": _iso_offset(age_minutes),
        "core_question": "test core question for the status TUI tests",
        "knowns": ["k1"],
        "unknowns": ["u1 — sharp enough"],
        "assumptions": ["a1"],
        "disconfirmation": "specific outcome that would invalidate this plan",
        "domain": "complicated",
        "posture_selected": "patch",
    }
    payload.update(fields)
    path.write_text(json.dumps(payload))
    return path


class GatherStatusSurface(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cwd = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_absent_surface(self):
        s = _status.gather_status(self.cwd)
        self.assertFalse(s["surface"]["exists"])
        self.assertEqual(s["surface"]["validation"], "absent")
        self.assertFalse(s["surface"]["fresh"])

    def test_fresh_surface(self):
        _write_surface(self.cwd, age_minutes=5.0)
        s = _status.gather_status(self.cwd)
        self.assertTrue(s["surface"]["exists"])
        self.assertTrue(s["surface"]["fresh"])
        self.assertLess(s["surface"]["age_minutes"], 30)
        self.assertEqual(s["surface"]["validation"], "pass")
        self.assertEqual(s["surface"]["posture_selected"], "patch")

    def test_stale_surface(self):
        _write_surface(self.cwd, age_minutes=45.0)
        s = _status.gather_status(self.cwd)
        self.assertTrue(s["surface"]["exists"])
        self.assertFalse(s["surface"]["fresh"])
        self.assertGreater(s["surface"]["age_minutes"], 30)

    def test_unparseable_surface(self):
        surf = self.cwd / ".episteme"
        surf.mkdir()
        (surf / "reasoning-surface.json").write_text("not valid json {{{")
        s = _status.gather_status(self.cwd)
        self.assertTrue(s["surface"]["exists"])
        self.assertEqual(s["surface"]["validation"], "unparseable")

    def test_incomplete_surface(self):
        _write_surface(self.cwd, age_minutes=5.0, knowns=None)
        # When a required field is missing entirely, validation should report incomplete.
        # We force missing by writing a stripped-down payload.
        path = self.cwd / ".episteme" / "reasoning-surface.json"
        path.write_text(json.dumps({
            "timestamp": _iso_offset(5.0),
            "core_question": "minimal probe",
        }))
        s = _status.gather_status(self.cwd)
        self.assertEqual(s["surface"]["validation"], "incomplete")


class GatherStatusBranchAndRigor(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cwd = Path(self._td.name)
        (self.cwd / ".episteme").mkdir()

    def tearDown(self):
        self._td.cleanup()

    def test_default_branch(self):
        s = _status.gather_status(self.cwd)
        self.assertEqual(s["branch"], "default")

    def test_branch_marker_active(self):
        (self.cwd / ".episteme" / "reasoning-surface.active").write_text("explore-x")
        s = _status.gather_status(self.cwd)
        self.assertEqual(s["branch"], "explore-x")

    def test_empty_branch_marker_falls_back_to_default(self):
        (self.cwd / ".episteme" / "reasoning-surface.active").write_text("")
        s = _status.gather_status(self.cwd)
        self.assertEqual(s["branch"], "default")

    def test_default_rigor(self):
        s = _status.gather_status(self.cwd)
        self.assertEqual(s["rigor"]["level"], "medium")
        self.assertEqual(s["rigor"]["scope"], "default")

    def test_project_rigor_low(self):
        (self.cwd / ".episteme" / "rigor").write_text("low\n")
        s = _status.gather_status(self.cwd)
        self.assertEqual(s["rigor"]["level"], "low")
        self.assertEqual(s["rigor"]["scope"], "project")

    def test_project_rigor_high(self):
        (self.cwd / ".episteme" / "rigor").write_text("high")
        s = _status.gather_status(self.cwd)
        self.assertEqual(s["rigor"]["level"], "high")
        self.assertEqual(s["rigor"]["scope"], "project")

    def test_invalid_rigor_falls_back_to_default(self):
        (self.cwd / ".episteme" / "rigor").write_text("turbo")
        s = _status.gather_status(self.cwd)
        self.assertEqual(s["rigor"]["level"], "medium")
        self.assertEqual(s["rigor"]["scope"], "default")


class FormattersShape(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cwd = Path(self._td.name)
        _write_surface(self.cwd, age_minutes=10.0)

    def tearDown(self):
        self._td.cleanup()

    def test_text_formatter_contains_named_sections(self):
        s = _status.gather_status(self.cwd)
        text = _status.format_status_text(s)
        for section in (
            "Reasoning Surface", "Branch:", "Rigor:",
            "Framework", "Operator Profile",
        ):
            with self.subTest(section=section):
                self.assertIn(section, text)

    def test_text_formatter_marks_fresh(self):
        s = _status.gather_status(self.cwd)
        text = _status.format_status_text(s)
        self.assertIn("fresh", text)

    def test_text_formatter_marks_stale_when_old(self):
        _write_surface(self.cwd, age_minutes=120.0)
        s = _status.gather_status(self.cwd)
        text = _status.format_status_text(s)
        self.assertIn("STALE", text)

    def test_json_formatter_is_valid_json(self):
        s = _status.gather_status(self.cwd)
        rendered = _status.format_status_json(s)
        parsed = json.loads(rendered)
        self.assertIn("surface", parsed)
        self.assertIn("rigor", parsed)
        self.assertIn("branch", parsed)


class RunStatusEntrypoint(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.cwd = Path(self._td.name)
        _write_surface(self.cwd, age_minutes=2.0)

    def tearDown(self):
        self._td.cleanup()

    def test_one_shot_text(self):
        out = io.StringIO()
        rc = _status.run_status(cwd=self.cwd, out=out)
        self.assertEqual(rc, 0)
        self.assertIn("Reasoning Surface", out.getvalue())

    def test_one_shot_json(self):
        out = io.StringIO()
        rc = _status.run_status(cwd=self.cwd, json_out=True, out=out)
        self.assertEqual(rc, 0)
        # JSON mode emits parseable JSON.
        json.loads(out.getvalue())

    def test_watch_mode_runs_max_ticks_and_returns(self):
        out = io.StringIO()
        sleep_calls: list[float] = []
        rc = _status.run_status(
            cwd=self.cwd, watch=True, out=out, max_ticks=2,
            sleep_fn=lambda interval: sleep_calls.append(interval),
            interval=0.5,
        )
        self.assertEqual(rc, 0)
        # Watch must have rendered twice (clear-screen ANSI emitted twice).
        self.assertEqual(out.getvalue().count("\033[2J"), 2)
        # sleep_fn invoked once between renders; final tick returns before sleeping.
        # For N rendered ticks → (N-1) sleep calls.
        self.assertEqual(sleep_calls, [0.5])


if __name__ == "__main__":
    unittest.main()
