"""Event 158 — deferred-discovery cap surfacing in the SessionStart banner.

Covers the extension of ``_framework_digest_line()``: below the open cap
with zero machine-expiries the line is byte-identical to before; at/over
cap it appends the degradation notice (writes paused + skipped count);
machine-expired findings surface their own count so cap relief is never
an invisible loss; a cap-read failure degrades to the plain line rather
than killing the digest.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

from core.hooks import session_context as sc  # pyright: ignore[reportAttributeAccessIssue]

# The hook resolves `import _framework` as a TOP-LEVEL module via the
# hooks dir on sys.path — mirror that so mock.patch.object targets the
# same cached module object the hook uses.
_HOOKS_DIR = Path(__file__).resolve().parents[1] / "core" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import _framework  # noqa: E402  # pyright: ignore[reportMissingImports]


def _open_stub(n: int) -> list[dict]:
    return [{"payload": {"type": "deferred_discovery"}} for _ in range(n)]


class DeferredCapLineTests(unittest.TestCase):
    def _line(self, *, open_n, cap=100, skipped=0, expired=0,
              cap_error=False):
        cap_mock = (
            mock.patch.object(
                _framework, "_resolve_deferred_open_cap",
                side_effect=RuntimeError("boom"),
            )
            if cap_error
            else mock.patch.object(
                _framework, "_resolve_deferred_open_cap", return_value=cap
            )
        )
        with mock.patch.object(_framework, "list_protocols", return_value=[]), \
             mock.patch.object(
                 _framework, "open_deferred_discoveries",
                 return_value=_open_stub(open_n),
             ), \
             mock.patch.object(
                 _framework, "expired_unverdicted_count",
                 return_value=expired,
             ), \
             cap_mock, \
             mock.patch.object(
                 _framework, "read_deferred_skip_counter",
                 return_value={"skipped_count": skipped},
             ), \
             mock.patch.object(sc, "_read_last_session_ts", return_value=None):
            return sc._framework_digest_line()

    def test_below_cap_line_unchanged(self):
        line = self._line(open_n=28)
        self.assertEqual(
            line,
            "framework: 0 protocols synthesized since last session "
            "(0 total), 28 deferred discoveries pending",
        )

    def test_at_cap_appends_degradation_notice(self):
        line = self._line(open_n=100, cap=100, skipped=7)
        assert line is not None
        self.assertIn("100 deferred discoveries pending", line)
        self.assertIn("queue AT CAP (100)", line)
        self.assertIn("writes paused", line)
        self.assertIn("7 record(s) skipped", line)

    def test_over_cap_also_notices(self):
        line = self._line(open_n=178, cap=100, skipped=42)
        assert line is not None
        self.assertIn("178 deferred discoveries pending", line)
        self.assertIn("AT CAP (100)", line)
        self.assertIn("42 record(s) skipped", line)

    def test_expired_count_surfaces(self):
        # Machine expiry must never be invisible (Event 158 review).
        line = self._line(open_n=5, expired=173)
        assert line is not None
        self.assertIn("5 deferred discoveries pending", line)
        self.assertIn("173 expired-unreviewed discoveries", line)
        self.assertIn("--expired", line)
        self.assertNotIn("AT CAP", line)

    def test_cap_read_failure_degrades_to_plain_line(self):
        line = self._line(open_n=150, cap_error=True)
        assert line is not None
        self.assertIn("150 deferred discoveries pending", line)
        self.assertNotIn("AT CAP", line)


if __name__ == "__main__":
    unittest.main()
