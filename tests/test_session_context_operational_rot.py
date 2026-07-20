"""Event 170 — the PLAN.md-class detector.

Private-doc symlinks are exempt from lifecycle lint (no markers, no git
history) — the blind spot that let docs/PLAN.md rot 13 days across ten
handoffs until the OPERATOR caught it by hand. `_operational_rot_line`
watches the symlinked operational set as a cohort: when one member lags
the newest by more than the grace window, it gets named at SessionStart.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
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


def _mk_link(root: Path, name: str, *, age_days: float, now: float) -> None:
    real = root / "private" / f"{name}.real"
    real.parent.mkdir(exist_ok=True)
    real.write_text("content", encoding="utf-8")
    stamp = now - age_days * 86400
    os.utime(real, (stamp, stamp))
    (root / "docs" / name).symlink_to(real)


class OperationalRotTests(unittest.TestCase):
    def _root(self, stack):
        td = stack.enter_context(tempfile.TemporaryDirectory())
        root = Path(td)
        (root / "docs").mkdir()
        return root

    def test_silent_when_cohort_moves_together(self):
        import contextlib, time
        now = time.time()
        with contextlib.ExitStack() as stack:
            root = self._root(stack)
            _mk_link(root, "NEXT_STEPS.md", age_days=0.1, now=now)
            _mk_link(root, "EVENTS.md", age_days=2, now=now)  # within grace
            with _chdir(root):
                self.assertIsNone(sc._operational_rot_line())

    def test_names_the_rotting_doc_with_lag(self):
        import contextlib, time
        now = time.time()
        with contextlib.ExitStack() as stack:
            root = self._root(stack)
            _mk_link(root, "NEXT_STEPS.md", age_days=0.1, now=now)
            _mk_link(root, "SOME_PLAN.md", age_days=13, now=now)  # the PLAN case
            with _chdir(root):
                line = sc._operational_rot_line()
            assert line is not None
            self.assertIn("operational doc rot", line)
            self.assertIn("SOME_PLAN.md", line)
            self.assertIn("12d behind", line)
            self.assertIn("track it or retire it", line)

    def test_dangling_symlink_named_immediately(self):
        import contextlib
        with contextlib.ExitStack() as stack:
            root = self._root(stack)
            (root / "docs" / "GONE.md").symlink_to(root / "private" / "missing.md")
            with _chdir(root):
                line = sc._operational_rot_line()
            assert line is not None
            self.assertIn("DANGLING", line)
            self.assertIn("GONE.md", line)

    def test_silent_with_fewer_than_two_members(self):
        import contextlib, time
        with contextlib.ExitStack() as stack:
            root = self._root(stack)
            _mk_link(root, "NEXT_STEPS.md", age_days=30, now=time.time())
            with _chdir(root):
                self.assertIsNone(sc._operational_rot_line())

    def test_regular_files_are_not_cohort_members(self):
        import contextlib, time
        now = time.time()
        with contextlib.ExitStack() as stack:
            root = self._root(stack)
            _mk_link(root, "NEXT_STEPS.md", age_days=0.1, now=now)
            old = root / "docs" / "TRACKED.md"
            old.write_text("tracked docs have lifecycle lint", encoding="utf-8")
            os.utime(old, (now - 40 * 86400, now - 40 * 86400))
            with _chdir(root):
                self.assertIsNone(sc._operational_rot_line())


if __name__ == "__main__":
    unittest.main()
