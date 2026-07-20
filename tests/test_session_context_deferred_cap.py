"""Event 158 — deferred-discovery cap surfacing in the SessionStart banner.

Covers the extension of ``_framework_digest_line()``: below the open cap
the line is byte-identical to before; at/over cap it appends the
degradation notice (writes paused + skipped count); a cap-read failure
degrades to the plain line rather than killing the digest.
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
    def test_below_cap_line_unchanged(self):
        with mock.patch.object(_framework, "list_protocols", return_value=[]), \
             mock.patch.object(
                 _framework, "open_deferred_discoveries",
                 return_value=_open_stub(28),
             ), \
             mock.patch.object(
                 _framework, "_resolve_deferred_open_cap", return_value=100
             ), \
             mock.patch.object(sc, "_read_last_session_ts", return_value=None):
            line = sc._framework_digest_line()
        self.assertEqual(
            line,
            "framework: 0 protocols synthesized since last session "
            "(0 total), 28 deferred discoveries pending",
        )

    def test_at_cap_appends_degradation_notice(self):
        with mock.patch.object(_framework, "list_protocols", return_value=[]), \
             mock.patch.object(
                 _framework, "open_deferred_discoveries",
                 return_value=_open_stub(100),
             ), \
             mock.patch.object(
                 _framework, "_resolve_deferred_open_cap", return_value=100
             ), \
             mock.patch.object(
                 _framework, "read_deferred_skip_counter",
                 return_value={"skipped_count": 7},
             ), \
             mock.patch.object(sc, "_read_last_session_ts", return_value=None):
            line = sc._framework_digest_line()
        assert line is not None
        self.assertIn("100 deferred discoveries pending", line)
        self.assertIn("queue AT CAP (100)", line)
        self.assertIn("writes paused", line)
        self.assertIn("7 record(s) skipped", line)

    def test_cap_read_failure_degrades_to_plain_line(self):
        with mock.patch.object(_framework, "list_protocols", return_value=[]), \
             mock.patch.object(
                 _framework, "open_deferred_discoveries",
                 return_value=_open_stub(150),
             ), \
             mock.patch.object(
                 _framework, "_resolve_deferred_open_cap",
                 side_effect=RuntimeError("boom"),
             ), \
             mock.patch.object(sc, "_read_last_session_ts", return_value=None):
            line = sc._framework_digest_line()
        assert line is not None
        self.assertIn("150 deferred discoveries pending", line)
        self.assertNotIn("AT CAP", line)


if __name__ == "__main__":
    unittest.main()
