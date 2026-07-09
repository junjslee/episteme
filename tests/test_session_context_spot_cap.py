"""Event 148 verification finding — at-cap surfacing on the spot-check line.

Covers the extension of ``_spot_check_line()``: below the enqueue cap the
line is byte-identical to the pre-E148 form; at/over the cap it appends the
degradation notice (sampling paused + skip counter) so silently skipped
audit coverage is never invisible. Same producer, no new banner line
(anti-accretion). Never raises: cap/counter read failures degrade to the
plain line.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

from core.hooks import session_context as sc  # pyright: ignore[reportAttributeAccessIssue]

# The hook resolves `import _spot_check` as a TOP-LEVEL module via the hooks
# dir on sys.path (hooks run as standalone scripts). Import the same instance
# here so the patches below hit the module the hook actually uses — patching
# core.hooks._spot_check targets a different module object and silently
# leaves the hook reading the live queue.
_HOOKS_DIR = Path(__file__).resolve().parents[1] / "core" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))
import _spot_check  # noqa: E402  # pyright: ignore[reportMissingImports]


class SpotCheckCapLineTests(unittest.TestCase):
    def test_below_cap_line_unchanged(self):
        with mock.patch.object(_spot_check, "count_pending", return_value=28), \
             mock.patch.object(_spot_check, "_resolve_pending_cap", return_value=100):
            line = sc._spot_check_line()
        self.assertEqual(
            line, "28 surfaces flagged for review — run `episteme review`"
        )

    def test_at_cap_appends_degradation_notice(self):
        with mock.patch.object(_spot_check, "count_pending", return_value=100), \
             mock.patch.object(_spot_check, "_resolve_pending_cap", return_value=100), \
             mock.patch.object(
                 _spot_check, "read_skip_counter",
                 return_value={"skipped_count": 7},
             ):
            line = sc._spot_check_line()
        assert line is not None
        self.assertIn("queue AT CAP (100)", line)
        self.assertIn("sampling paused", line)
        self.assertIn("7 op(s) skipped", line)

    def test_over_cap_also_notices(self):
        with mock.patch.object(_spot_check, "count_pending", return_value=137), \
             mock.patch.object(_spot_check, "_resolve_pending_cap", return_value=100), \
             mock.patch.object(
                 _spot_check, "read_skip_counter",
                 return_value={"skipped_count": 37},
             ):
            line = sc._spot_check_line()
        assert line is not None
        self.assertIn("137 surfaces flagged", line)
        self.assertIn("AT CAP (100)", line)

    def test_cap_read_failure_degrades_to_plain_line(self):
        with mock.patch.object(_spot_check, "count_pending", return_value=100), \
             mock.patch.object(
                 _spot_check, "_resolve_pending_cap",
                 side_effect=RuntimeError("boom"),
             ):
            line = sc._spot_check_line()
        self.assertEqual(
            line, "100 surfaces flagged for review — run `episteme review`"
        )

    def test_zero_pending_stays_silent(self):
        with mock.patch.object(_spot_check, "count_pending", return_value=0):
            self.assertIsNone(sc._spot_check_line())


if __name__ == "__main__":
    unittest.main()
