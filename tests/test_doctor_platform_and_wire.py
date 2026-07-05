"""Doctor owns the platform posture and the hook wire contract (§9.3/§9.4).

The enforcement layer exists only on Claude Code's PreToolUse contract
(JSON on stdin; exit 0 admits, exit 2 blocks). A breaking change to that
wire shape would silently disable the entire gate layer, so doctor probes
it live against the cheapest real hook. And the chain's fcntl locking
silently no-ops on Windows, so doctor must say so instead of implying
universality (PRODUCT_MASTER_PLAN §9.3/§9.4, Event 143).
"""
from __future__ import annotations

import unittest
from pathlib import Path

from episteme import cli


class PlatformPosture(unittest.TestCase):
    def test_win32_draws_a_warning_with_the_mechanism_named(self):
        level, msg = cli._platform_posture("win32")
        self.assertEqual(level, "warn")
        self.assertIn("fcntl", msg)
        self.assertIn("WSL2", msg)

    def test_macos_and_linux_are_supported(self):
        for key in ("darwin", "linux"):
            level, msg = cli._platform_posture(key)
            self.assertEqual(level, "ok", msg)
            self.assertIn("supported", msg)


class HookWireProbe(unittest.TestCase):
    def test_real_hook_passes_both_directions(self):
        status, msg = cli._probe_hook_wire_format()
        self.assertEqual(status, "ok", msg)
        self.assertIn("exit 0 admits, exit 2 blocks", msg)

    def test_missing_hook_reports_miss_not_fail(self):
        status, msg = cli._probe_hook_wire_format(
            hook_path=Path("/nonexistent/block_dangerous.py")
        )
        self.assertEqual(status, "miss")
        self.assertIn("missing", msg)

    def test_contract_drift_reports_fail(self):
        # A hook that admits everything (exit 0 for the dangerous shape)
        # is wire drift: the gate looks installed but blocks nothing.
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "fake_hook.py"
            fake.write_text("import sys; sys.exit(0)\n", encoding="utf-8")
            status, msg = cli._probe_hook_wire_format(hook_path=fake)
            self.assertEqual(status, "fail")
            self.assertIn("drift", msg)


if __name__ == "__main__":
    unittest.main()
