"""Event 137 — SessionStart signal-quality bounds.

Covers the two producers that keep session-open context honest:

- ``_next_steps_block()`` — bounded NEXT_STEPS injection. The live
  failure this guards against: a 240KB NEXT_STEPS.md injected in full
  (twice, under dual hook registration) buried the resume-here block
  under months of history.
- ``_e1_line()`` — the kernel evaluating its own falsifiability
  condition (kernel/FALSIFIABILITY_CONDITIONS.md § E1) against live
  framework state instead of a hand-maintained doc status. The live
  failure: E1 fired (0 protocols, 49+ days of framework activity) and
  nothing surfaced it.

Producer-patching follows the bare-name sys.modules pattern documented
in tests/test_session_context_noise_watch.py — session_context imports
``_framework`` via sys.path injection, so tests patch the bare module
object, not the dotted-path one.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.hooks import session_context as sc  # pyright: ignore[reportAttributeAccessIssue]


def _bare_framework():
    """Return the bare-name ``_framework`` module session_context uses."""
    _hooks_dir = Path(sc.__file__).resolve().parent
    if str(_hooks_dir) not in sys.path:
        sys.path.insert(0, str(_hooks_dir))
    import _framework  # type: ignore  # pyright: ignore[reportMissingImports]
    return _framework


def _env(ts: datetime) -> dict:
    return {"ts": ts.isoformat(), "payload": {"type": "x"}}


# ---------- _next_steps_block --------------------------------------------


class NextStepsBlockBounds(unittest.TestCase):
    def test_missing_file_returns_none(self):
        self.assertIsNone(
            sc._next_steps_block(Path("/nonexistent/NEXT_STEPS.md"))
        )

    def test_empty_file_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "NEXT_STEPS.md"
            p.write_text("   \n", encoding="utf-8")
            self.assertIsNone(sc._next_steps_block(p))

    def test_under_cap_passes_through_unmodified(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "NEXT_STEPS.md"
            body = "# Next Steps\n\n## Resume here\n- do the thing\n"
            p.write_text(body, encoding="utf-8")
            block = sc._next_steps_block(p)
            assert block is not None
            self.assertIn(body.strip(), block)
            self.assertNotIn("truncated by session_context", block)

    def test_over_cap_truncates_at_newline_with_marker(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "NEXT_STEPS.md"
            head = "## Resume here\n- exact next action\n"
            tail = ("history line that should be cut\n"
                    * (sc._NEXT_STEPS_MAX_CHARS // 20))
            p.write_text(head + tail, encoding="utf-8")
            block = sc._next_steps_block(p)
            assert block is not None
            self.assertIn("- exact next action", block)
            self.assertIn("truncated by session_context", block)
            # Cap holds: block stays within max + marker headroom.
            self.assertLess(
                len(block), sc._NEXT_STEPS_MAX_CHARS + 200
            )

    def test_truncation_preserves_head_not_tail(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "NEXT_STEPS.md"
            filler = "x" * 30
            lines = [f"line-{i:05d} {filler}" for i in range(1000)]
            p.write_text("\n".join(lines), encoding="utf-8")
            block = sc._next_steps_block(p)
            assert block is not None
            self.assertIn("line-00000", block)
            self.assertNotIn("line-00999", block)


# ---------- _e1_line -------------------------------------------------------


class E1SelfCheck(unittest.TestCase):
    def _line_with(self, protocols: list, deferred: list) -> str | None:
        fw = _bare_framework()
        with patch.object(fw, "list_protocols", return_value=protocols), \
             patch.object(
                 fw, "list_deferred_discoveries", return_value=deferred
             ):
            return sc._e1_line()

    def test_fires_on_zero_protocols_after_window(self):
        old = datetime.now(timezone.utc) - timedelta(days=49)
        line = self._line_with([], [_env(old)])
        assert line is not None
        self.assertIn("E1 FIRED", line)
        self.assertIn("0 protocols", line)
        self.assertIn("FALSIFIABILITY_CONDITIONS.md", line)

    def test_silent_when_floor_met(self):
        old = datetime.now(timezone.utc) - timedelta(days=49)
        protocols = [_env(old) for _ in range(3)]
        self.assertIsNone(self._line_with(protocols, [_env(old)]))

    def test_silent_inside_window(self):
        recent = datetime.now(timezone.utc) - timedelta(days=5)
        self.assertIsNone(self._line_with([], [_env(recent)]))

    def test_silent_when_framework_unused(self):
        self.assertIsNone(self._line_with([], []))

    def test_fires_below_floor_not_just_zero(self):
        old = datetime.now(timezone.utc) - timedelta(days=40)
        line = self._line_with([_env(old)], [_env(old)])
        assert line is not None
        self.assertIn("E1 FIRED", line)
        self.assertIn("1 protocol ", line)

    def test_z_suffix_timestamp_parses(self):
        old = datetime.now(timezone.utc) - timedelta(days=40)
        env = {"ts": old.strftime("%Y-%m-%dT%H:%M:%SZ"), "payload": {}}
        line = self._line_with([], [env])
        assert line is not None
        self.assertIn("E1 FIRED", line)


if __name__ == "__main__":
    unittest.main()
