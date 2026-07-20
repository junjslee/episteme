"""Event 171 — the dead-mechanism sweep's live findings, wired and pinned.

Class precedents: write_skip (E157), codex.json (E167) — mechanisms that
existed with zero callers while their subsystems assumed they ran.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.hooks import session_context as sc  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _pending_contracts  # pyright: ignore[reportAttributeAccessIssue]
import episteme.cli as ecli  # pyright: ignore[reportMissingImports]


class _Home:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = os.environ.get("EPISTEME_HOME")
        os.environ["EPISTEME_HOME"] = self._tmp.name
        return Path(self._tmp.name)

    def __exit__(self, *exc):
        if self._orig is None:
            os.environ.pop("EPISTEME_HOME", None)
        else:
            os.environ["EPISTEME_HOME"] = self._orig
        self._tmp.cleanup()
        return False


class PendingContractsDrainWiredTests(unittest.TestCase):
    """The queue had a LIVE enqueue (guard's write_contract) and a
    drain — auto_archive_beyond_grace, its own 'safety net against
    unbounded growth' — that nothing called. Now the SessionStart
    reaper line runs it."""

    def _write_expired_contract(self, home: Path):
        past = datetime.now(timezone.utc) - timedelta(days=30)
        _pending_contracts.write_contract(
            correlation_id="tu_e171",
            op_label="git push",
            blueprint="generic",
            context_signature={},
            verification_trace={
                "command": "pytest -q", "window_seconds": 600,
                "threshold_observable": "suite green",
            },
            surface_provenance={"core_question": "q" * 30,
                                "disconfirmation": "d" * 30},
            now=past,
        )

    def test_reaper_line_archives_past_grace_contracts(self):
        with _Home() as home:
            self._write_expired_contract(home)
            active = home / "state" / "pending_contracts.jsonl"
            self.assertTrue(active.exists())
            line = sc._reaper_line()
            assert line is not None
            self.assertIn("pending-contracts: 1 past-grace", line)
            archive = home / "state" / "pending_contracts.archived.jsonl"
            self.assertTrue(archive.exists())
            self.assertIn("expired_without_audit",
                          archive.read_text(encoding="utf-8"))

    def test_reaper_line_silent_when_nothing_to_archive(self):
        with _Home():
            line = sc._reaper_line()
            self.assertTrue(line is None or "pending-contracts" not in line)


class DerivedKnobsRegenerationTests(unittest.TestCase):
    """The write path ('called by the adapter at sync time' per its own
    docstring) had zero callers; ~/.episteme/derived_knobs.json sat
    frozen since Apr 20 while three hooks read it. Sync now regenerates
    from generated profile scores and PRINTS changed knobs, because
    they shift live gate behavior."""

    def test_no_scores_is_a_silent_noop(self):
        from unittest import mock
        with _Home() as home:
            with mock.patch.object(ecli, "_load_generated_scores",
                                   return_value=(None, None)):
                self.assertEqual(ecli._regenerate_derived_knobs(), [])
            self.assertFalse((home / "derived_knobs.json").exists())

    def test_scores_regenerate_and_changes_are_reported(self):
        from unittest import mock
        with _Home() as home:
            knobs_file = home / "derived_knobs.json"
            knobs_file.write_text(json.dumps(
                {"unknown_specificity_min": 999}), encoding="utf-8")
            scores = ({"planning_strictness": 5, "risk_tolerance": 1,
                       "testing_rigor": 5, "parallelism_preference": 2,
                       "documentation_rigor": 5, "automation_level": 3},
                      {})
            with mock.patch.object(ecli, "_load_generated_scores",
                                   return_value=scores):
                lines = ecli._regenerate_derived_knobs()
            self.assertTrue(lines, "changed knobs must be reported, not silent")
            self.assertTrue(any("derived knob" in ln for ln in lines))
            data = json.loads(knobs_file.read_text(encoding="utf-8"))
            self.assertNotEqual(data.get("unknown_specificity_min"), 999)

    def test_unchanged_regeneration_stays_quiet(self):
        from unittest import mock
        with _Home():
            scores = ({"planning_strictness": 3}, {})
            with mock.patch.object(ecli, "_load_generated_scores",
                                   return_value=scores):
                first = ecli._regenerate_derived_knobs()
                second = ecli._regenerate_derived_knobs()
            self.assertTrue(first)   # initial write reports
            self.assertEqual(second, [])  # steady state is silent


class EpistemePythonHonoredTests(unittest.TestCase):
    """The operator's python_runtime_policy documented EPISTEME_PYTHON
    since day one; nothing read it (only the _PREFIX form). The promise
    and the wire now match."""

    def test_binary_pin_implies_prefix(self):
        from unittest import mock
        with mock.patch.dict(os.environ,
                             {"EPISTEME_PYTHON": "/opt/py311/bin/python3.11"}):
            self.assertEqual(ecli._detect_python_prefix(), Path("/opt/py311"))

    def test_prefix_form_still_wins_when_binary_absent(self):
        from unittest import mock
        env = {"EPISTEME_PYTHON_PREFIX": "/opt/other"}
        with mock.patch.dict(os.environ, env, clear=False):
            os.environ.pop("EPISTEME_PYTHON", None)
            self.assertEqual(ecli._detect_python_prefix(), Path("/opt/other"))


if __name__ == "__main__":
    unittest.main()
