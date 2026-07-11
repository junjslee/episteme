"""Event 150 · sync self-heal — the forgotten-`episteme sync` gap.

Covers `_sync_selfheal_line()` (SessionStart) + the adapter substrate
(`settings_in_sync`, `read_sync_meta`, the sync sidecar): a synced runtime
stays silent; registration drift with a KNOWN governance pack (sidecar)
auto-heals and says so; drift with an UNKNOWN pack advises without writing
(healing with a guessed pack could silently downgrade strict); any failure
degrades to silence. Detection and heal target the same tree
(episteme.cli.HOME) by construction.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.hooks import session_context as sc  # pyright: ignore[reportAttributeAccessIssue]

import episteme.cli as ecli  # pyright: ignore[reportMissingImports]
from episteme.adapters import claude as cadapter  # pyright: ignore[reportMissingImports]


class _TmpHome:
    """Context manager: point episteme.cli.HOME at a tmp dir and run a real
    `sync('balanced')` there so tests start from a genuinely-synced state."""

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        self._orig = ecli.HOME
        ecli.HOME = Path(self._td.name)
        cadapter.sync("balanced")
        self.claude_root = ecli.HOME / ".claude"
        return self

    def __exit__(self, *exc):
        ecli.HOME = self._orig
        self._td.cleanup()
        return False


class SyncMetaTests(unittest.TestCase):
    def test_sidecar_written_by_sync_and_readable(self):
        with _TmpHome() as th:
            meta = cadapter.read_sync_meta(th.claude_root)
            self.assertEqual(meta.get("governance_pack"), "balanced")
            self.assertIn("synced_at", meta)

    def test_read_sync_meta_absent_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(cadapter.read_sync_meta(Path(td)), {})

    def test_read_sync_meta_malformed_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / cadapter.SYNC_META_FILENAME).write_text("not json{", encoding="utf-8")
            self.assertEqual(cadapter.read_sync_meta(Path(td)), {})


class SettingsInSyncTests(unittest.TestCase):
    def test_freshly_synced_settings_are_in_sync(self):
        with _TmpHome() as th:
            existing = json.loads((th.claude_root / "settings.json").read_text(encoding="utf-8"))
            self.assertTrue(cadapter.settings_in_sync(existing, "balanced"))

    def test_removed_hook_entry_is_drift(self):
        with _TmpHome() as th:
            existing = json.loads((th.claude_root / "settings.json").read_text(encoding="utf-8"))
            hooks = existing.get("hooks", {})
            first_event = next(iter(hooks))
            hooks[first_event] = hooks[first_event][1:]  # drop one registration
            self.assertFalse(cadapter.settings_in_sync(existing, "balanced"))


class SelfHealLineTests(unittest.TestCase):
    def test_synced_state_is_silent(self):
        with _TmpHome():
            self.assertIsNone(sc._sync_selfheal_line())

    def test_settings_drift_with_sidecar_heals_and_reports(self):
        with _TmpHome() as th:
            settings_path = th.claude_root / "settings.json"
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
            first_event = next(iter(existing["hooks"]))
            existing["hooks"][first_event] = existing["hooks"][first_event][1:]
            settings_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

            line = sc._sync_selfheal_line()
            assert line is not None
            self.assertIn("sync-selfheal", line)
            self.assertIn("balanced", line)
            self.assertIn("next session", line)
            healed = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertTrue(cadapter.settings_in_sync(healed, "balanced"))

    def test_claude_md_drift_with_sidecar_heals(self):
        with _TmpHome() as th:
            claude_md = th.claude_root / "CLAUDE.md"
            claude_md.write_text("# something the operator pasted over it\n", encoding="utf-8")
            line = sc._sync_selfheal_line()
            assert line is not None
            self.assertIn("sync-selfheal", line)
            body = claude_md.read_text(encoding="utf-8")
            self.assertIn("episteme Global Memory", body)

    def test_drift_without_sidecar_advises_without_writing(self):
        with _TmpHome() as th:
            (th.claude_root / cadapter.SYNC_META_FILENAME).unlink()
            settings_path = th.claude_root / "settings.json"
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
            first_event = next(iter(existing["hooks"]))
            existing["hooks"][first_event] = existing["hooks"][first_event][1:]
            drifted = json.dumps(existing, indent=2) + "\n"
            settings_path.write_text(drifted, encoding="utf-8")

            line = sc._sync_selfheal_line()
            assert line is not None
            self.assertIn("run `episteme sync`", line)
            self.assertIn("not auto-written", line)
            # Fail-safe: nothing was rewritten.
            self.assertEqual(settings_path.read_text(encoding="utf-8"), drifted)

    def test_any_exception_degrades_to_silence(self):
        with _TmpHome():
            with mock.patch.object(
                cadapter, "render_user_claude_md", side_effect=RuntimeError("boom")
            ):
                self.assertIsNone(sc._sync_selfheal_line())


if __name__ == "__main__":
    unittest.main()
