"""Event 178 — installed-user memory lane: resolution precedence + init seeding."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from episteme import cli


class ResolveMemoryFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.checkout = root / "checkout" / "core" / "memory" / "global"
        (self.checkout / "examples").mkdir(parents=True)
        self.home = root / "home" / ".episteme"
        (self.checkout / "examples" / "overview.example.md").write_text("example\n")

        self._p1 = patch.object(cli, "GLOBAL_MEMORY_DIR", self.checkout)
        self._p2 = patch.dict("os.environ", {"EPISTEME_HOME": str(self.home)})
        self._p1.start(); self._p2.start()
        self.addCleanup(self._p1.stop); self.addCleanup(self._p2.stop)

    def test_examples_fallback_when_nothing_personal(self):
        resolved = cli._resolve_memory_file("overview")
        self.assertEqual(resolved.name, "overview.example.md")

    def test_home_lane_outranks_examples(self):
        home_file = self.home / "memory" / "global" / "overview.md"
        home_file.parent.mkdir(parents=True)
        home_file.write_text("home personal\n")
        self.assertEqual(cli._resolve_memory_file("overview"), home_file)

    def test_checkout_outranks_home(self):
        (self.home / "memory" / "global").mkdir(parents=True)
        (self.home / "memory" / "global" / "overview.md").write_text("home\n")
        checkout_file = self.checkout / "overview.md"
        checkout_file.write_text("checkout personal\n")
        self.assertEqual(cli._resolve_memory_file("overview"), checkout_file)

    def test_real_fresh_clone_shape(self):
        # Review F1/F2: a REAL fresh clone is not an empty checkout — it
        # carries exactly one tracked personal file, overview.md (shared
        # project topology). This pins the real shape: overview resolves to
        # the checkout copy (the documented exception), while a personal-
        # class name (runtime_digest, gitignored → absent in a clone) falls
        # through to the user's home lane.
        (self.checkout / "overview.md").write_text("tracked topology\n")
        home_dir = self.home / "memory" / "global"
        home_dir.mkdir(parents=True)
        (home_dir / "overview.md").write_text("home overview\n")
        (home_dir / "runtime_digest.md").write_text("home digest\n")
        self.assertEqual(
            cli._resolve_memory_file("overview"), self.checkout / "overview.md"
        )
        self.assertEqual(
            cli._resolve_memory_file("runtime_digest"),
            home_dir / "runtime_digest.md",
        )

    def test_tracked_personal_files_are_exactly_overview(self):
        # The F1 exception stays a SINGLE conscious exception: if another
        # personal memory file ever becomes git-tracked, the precedence
        # documentation is wrong again and this fails loudly.
        import subprocess

        repo = Path(__file__).resolve().parents[1]
        out = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "core/memory/global/*.md"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        tracked = [
            p for p in out
            if "/examples/" not in p and "/.generated/" not in p
        ]
        self.assertEqual(tracked, ["core/memory/global/overview.md"])


class InstalledInitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        packaged = root / "assets" / "core" / "memory" / "global"
        (packaged / "examples").mkdir(parents=True)
        for name in ("overview", "operator_profile"):
            (packaged / "examples" / f"{name}.example.md").write_text(f"{name} tpl\n")
        self.home = root / "home" / ".episteme"

        self._p1 = patch.object(cli, "GLOBAL_MEMORY_DIR", packaged)
        self._p2 = patch.dict("os.environ", {"EPISTEME_HOME": str(self.home)})
        self._p3 = patch("episteme._assets.is_installed_context", return_value=True)
        for p in (self._p1, self._p2, self._p3):
            p.start(); self.addCleanup(p.stop)

    def test_init_seeds_home_lane_from_packaged_examples(self):
        rc = cli._init_memory()
        self.assertEqual(rc, 0)
        dest = self.home / "memory" / "global"
        self.assertEqual(
            sorted(p.name for p in dest.glob("*.md")),
            ["operator_profile.md", "overview.md"],
        )
        self.assertEqual((dest / "overview.md").read_text(), "overview tpl\n")

    def test_init_never_clobbers_a_personalization(self):
        dest = self.home / "memory" / "global"
        dest.mkdir(parents=True)
        (dest / "overview.md").write_text("MY edited posture\n")
        rc = cli._init_memory()
        self.assertEqual(rc, 0)
        self.assertEqual((dest / "overview.md").read_text(), "MY edited posture\n")
        # the other template still seeds
        self.assertTrue((dest / "operator_profile.md").exists())

    def test_seeded_memory_composes_through_resolution(self):
        cli._init_memory()
        resolved = cli._resolve_memory_file("overview")
        self.assertEqual(resolved, self.home / "memory" / "global" / "overview.md")


if __name__ == "__main__":
    unittest.main()
