"""Event 177 — asset-root resolution + the wheel's privacy shipping contract.

The privacy tests pin setup.py's ignore callable directly: a regression that
would ship the operator's personal memory, private skills, runtime state, or
key material must fail HERE, in CI, before any wheel is built — not be
discovered in a published artifact.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from episteme import _assets, _packaging

REPO_ROOT = Path(__file__).resolve().parents[1]
_ignore = _packaging.asset_ignore_for(REPO_ROOT)


class AssetRootTests(unittest.TestCase):
    def test_checkout_context_resolves_repo_root(self):
        self.assertEqual(_assets.asset_root(), REPO_ROOT)
        self.assertFalse(_assets.is_installed_context())

    def test_checkout_override_requires_markers(self):
        with TemporaryDirectory() as tmp:
            with patch.dict("os.environ", {"EPISTEME_CHECKOUT": tmp}):
                # A non-checkout override is ignored, not trusted.
                self.assertEqual(_assets.asset_root(), REPO_ROOT)

    def test_installed_context_uses_packaged_assets(self):
        with TemporaryDirectory() as tmp:
            fake_pkg = Path(tmp) / "site-packages" / "episteme"
            (fake_pkg / "_assets" / "core" / "hooks").mkdir(parents=True)
            fake_module_file = fake_pkg / "_assets.py"
            fake_module_file.write_text("# fake\n", encoding="utf-8")
            with patch.object(_assets, "__file__", str(fake_module_file)):
                self.assertIsNone(_assets.checkout_root())
                self.assertTrue(_assets.is_installed_context())
                self.assertEqual(
                    # resolve(): macOS tempdirs live under the /var →
                    # /private/var symlink and asset_root returns resolved.
                    _assets.asset_root(), (fake_pkg / "_assets").resolve()
                )


class PrivacyIgnoreTests(unittest.TestCase):
    """setup.py's shipping contract, pinned field by field."""

    def _ignored(self, rel: str, names: list) -> set:
        return _ignore(str(REPO_ROOT / rel), names)

    def test_operator_memory_ships_examples_only(self):
        names = [
            "examples", "runtime_digest.md", "operator_profile.md",
            "agent_feedback.md", "workflow_policy.md", "cognitive_profile.md",
            "overview.md", ".generated",
        ]
        ignored = self._ignored("core/memory/global", names)
        self.assertNotIn("examples", ignored)
        for personal in names:
            if personal != "examples":
                self.assertIn(personal, ignored, personal)

    def test_private_skills_never_ship(self):
        ignored = self._ignored("skills", ["custom", "vendor", "private"])
        self.assertEqual(ignored, {"private"})

    def test_runtime_state_and_key_material_dropped_anywhere(self):
        ignored = self._ignored(
            "core/hooks",
            ["workflow_guard.py", "state.jsonl", "signing.pem", "id.key",
             "bundle.p12", "cache.pyc", "__pycache__"],
        )
        self.assertEqual(
            ignored,
            {"state.jsonl", "signing.pem", "id.key", "bundle.p12",
             "cache.pyc", "__pycache__"},
        )

    def test_substrate_records_do_not_ship(self):
        ignored = self._ignored("core/memory", ["global", "substrates"])
        self.assertIn("substrates", ignored)
        self.assertNotIn("global", ignored)

    def test_asset_trees_are_the_ratified_four(self):
        self.assertEqual(
            _packaging.ASSET_TREES, ("core", "kernel", "skills", "templates")
        )

    def test_sdist_staged_build_keeps_privacy_rules(self):
        # The ignore is bound to an explicit root: when a build frontend
        # stages the tree elsewhere (sdist temp dir), the SAME relative
        # rules must hold — an unmatched root must not silently disable
        # the memory/global exclusion.
        with TemporaryDirectory() as tmp:
            staged = Path(tmp) / "staging"
            (staged / "core" / "memory" / "global").mkdir(parents=True)
            ignore = _packaging.asset_ignore_for(staged)
            ignored = ignore(
                str(staged / "core" / "memory" / "global"),
                ["examples", "runtime_digest.md", "operator_profile.md"],
            )
            self.assertEqual(ignored, {"runtime_digest.md", "operator_profile.md"})


if __name__ == "__main__":
    unittest.main()
