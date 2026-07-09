"""Event 147 · A3 — SessionStart doc-lifecycle staleness banner.

Covers ``_doc_staleness_line()``: the silent-on-zero advisory that counts
tracked ``status=living`` docs whose ``reviewed_as_of`` lags the corpus by
more than 15 events (or 45 days when the marker carries a date). Same
discipline as ``_reaper_line`` — silent on the fresh-corpus session, one line
otherwise, never raises.

The producer globs ``docs/*.md`` relative to cwd (the hook runs with cwd =
project root), so these tests build a throwaway docs/ tree and chdir into it.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.hooks import session_context as sc  # pyright: ignore[reportAttributeAccessIssue]


@contextmanager
def _chdir(path: Path):
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def _marker(status: str, reviewed: str) -> str:
    return f"<!-- episteme-lifecycle: status={status}; reviewed_as_of={reviewed} -->\n# Title\n"


def _write_doc(docs: Path, name: str, status: str, reviewed: str) -> None:
    (docs / name).write_text(_marker(status, reviewed), encoding="utf-8")


class DocStalenessBanner(unittest.TestCase):
    def test_no_docs_dir_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            with _chdir(Path(td)):
                self.assertIsNone(sc._doc_staleness_line())

    def test_zero_case_emits_nothing(self):
        """All living docs within the 15-event window ⇒ silent."""
        with tempfile.TemporaryDirectory() as td:
            docs = Path(td) / "docs"
            docs.mkdir()
            (docs / "EVENTS.md").write_text("# Events\n- E200 something\n", encoding="utf-8")
            _write_doc(docs, "A.md", "living", "E200")
            _write_doc(docs, "B.md", "living", "E190")  # lag 10 ≤ 15
            with _chdir(Path(td)):
                self.assertIsNone(sc._doc_staleness_line())

    def test_stale_case_emits_one_line(self):
        """A living doc lagging >15 events ⇒ exactly one advisory line."""
        with tempfile.TemporaryDirectory() as td:
            docs = Path(td) / "docs"
            docs.mkdir()
            (docs / "EVENTS.md").write_text("# Events\n- E200\n- E147\n", encoding="utf-8")
            _write_doc(docs, "A.md", "living", "E200")  # fresh
            _write_doc(docs, "B.md", "living", "E147")  # lag 53 > 15 ⇒ stale
            _write_doc(docs, "C.md", "living", "E100")  # lag 100 > 15 ⇒ stale
            with _chdir(Path(td)):
                line = sc._doc_staleness_line()
            self.assertIsNotNone(line)
            assert line is not None
            self.assertEqual(line.count("\n"), 0, "must emit exactly one line")
            self.assertIn("doc-staleness: 2 living docs", line)
            self.assertIn("episteme docs lint", line)

    def test_non_living_status_ignored(self):
        """design-history / report / spec-implemented never count as stale."""
        with tempfile.TemporaryDirectory() as td:
            docs = Path(td) / "docs"
            docs.mkdir()
            (docs / "EVENTS.md").write_text("E200\n", encoding="utf-8")
            _write_doc(docs, "A.md", "design-history", "E10")
            _write_doc(docs, "B.md", "report", "E10")
            _write_doc(docs, "C.md", "spec-implemented", "E10")
            with _chdir(Path(td)):
                self.assertIsNone(sc._doc_staleness_line())

    def test_date_fallback_when_no_events_index(self):
        """No EVENTS.md ⇒ event-tagged docs skip; dated docs use the 45-day rule."""
        old = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d")
        fresh = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
        with tempfile.TemporaryDirectory() as td:
            docs = Path(td) / "docs"
            docs.mkdir()
            _write_doc(docs, "A.md", "living", old)      # >45 days ⇒ stale
            _write_doc(docs, "B.md", "living", fresh)    # within window
            _write_doc(docs, "C.md", "living", "E10")    # event-tagged, no index ⇒ skip
            with _chdir(Path(td)):
                line = sc._doc_staleness_line()
            self.assertIsNotNone(line)
            assert line is not None
            self.assertIn("doc-staleness: 1 living docs", line)
            # Event 148 · smallfix #1: the date-fallback fired, so the wording
            # must name the day threshold, not the event threshold.
            self.assertIn(">45 days", line)
            self.assertNotIn(">15 events", line)

    def test_event_lag_case_names_event_threshold(self):
        """When only the event-lag rule fires, the banner says '>15 events'."""
        with tempfile.TemporaryDirectory() as td:
            docs = Path(td) / "docs"
            docs.mkdir()
            (docs / "EVENTS.md").write_text("E200\n", encoding="utf-8")
            _write_doc(docs, "A.md", "living", "E100")  # lag 100 > 15 ⇒ stale
            with _chdir(Path(td)):
                line = sc._doc_staleness_line()
            self.assertIsNotNone(line)
            assert line is not None
            self.assertIn("doc-staleness: 1 living docs", line)
            self.assertIn(">15 events", line)
            self.assertNotIn(">45 days", line)

    def test_mixed_event_and_date_staleness_names_both(self):
        """Both classes stale ⇒ wording names both thresholds, count is the sum."""
        old = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d")
        with tempfile.TemporaryDirectory() as td:
            docs = Path(td) / "docs"
            docs.mkdir()
            (docs / "EVENTS.md").write_text("E200\n", encoding="utf-8")
            _write_doc(docs, "A.md", "living", "E100")  # event-lag stale
            _write_doc(docs, "B.md", "living", old)      # date-fallback stale
            with _chdir(Path(td)):
                line = sc._doc_staleness_line()
            self.assertIsNotNone(line)
            assert line is not None
            self.assertIn("doc-staleness: 2 living docs", line)
            self.assertIn(">15 events", line)
            self.assertIn(">45 days", line)
            self.assertEqual(line.count("\n"), 0, "must emit exactly one line")

    def test_symlinked_doc_skipped(self):
        """Private planning docs are symlinked and lifecycle-exempt."""
        with tempfile.TemporaryDirectory() as td:
            docs = Path(td) / "docs"
            docs.mkdir()
            (docs / "EVENTS.md").write_text("E200\n", encoding="utf-8")
            real = Path(td) / "PLAN_real.md"
            real.write_text(_marker("living", "E10"), encoding="utf-8")
            try:
                (docs / "PLAN.md").symlink_to(real)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unsupported on this platform")
            with _chdir(Path(td)):
                self.assertIsNone(sc._doc_staleness_line())

    def test_never_raises_on_unparseable_reviewed(self):
        with tempfile.TemporaryDirectory() as td:
            docs = Path(td) / "docs"
            docs.mkdir()
            (docs / "EVENTS.md").write_text("E200\n", encoding="utf-8")
            _write_doc(docs, "A.md", "living", "garbage-value")
            with _chdir(Path(td)):
                self.assertIsNone(sc._doc_staleness_line())


if __name__ == "__main__":
    unittest.main()
