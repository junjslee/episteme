"""Non-editable installs must fail honestly, not crash at import.

pyproject packages src/ only — core/, kernel/, and skills/ never ship
in a wheel. The 2026-07-03 recon verified empirically that `pip
install <repo>` produced a CLI whose `episteme --help` died at import
time with a raw FileNotFoundError from cli.py's module-level manifest
read. PyPI publish is merely commented out in release-please.yml, so
re-enabling it would have shipped a 100%-broken package.

Contract: importing the package and running manifest-free commands
(--help) works from a wheel-shaped layout; commands that need kernel
assets exit nonzero with a message that names the supported install
paths — never a traceback.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class WheelShapedInstall(unittest.TestCase):
    """The package copied WITHOUT the kernel tree, as a wheel lays it."""

    tmp: tempfile.TemporaryDirectory
    site: Path

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.site = Path(cls.tmp.name) / "site-packages"
        shutil.copytree(
            REPO_ROOT / "src" / "episteme",
            cls.site / "episteme",
            ignore=shutil.ignore_patterns("__pycache__"),
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _run(self, *args: str) -> tuple[int, str, str]:
        env = {**os.environ, "PYTHONPATH": str(self.site)}
        env.pop("PYTHONHOME", None)
        proc = subprocess.run(
            [
                sys.executable, "-c",
                "import sys; from episteme.cli import main; "
                "raise SystemExit(main(sys.argv[1:]))",
                *args,
            ],
            cwd=self.tmp.name,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def test_import_and_help_work_without_kernel_tree(self):
        rc, out, err = self._run("--help")
        self.assertEqual(rc, 0, err)
        self.assertIn("usage", (out + err).lower())
        self.assertNotIn("Traceback", err)

    def test_manifest_command_fails_honestly(self):
        rc, out, err = self._run("validate")
        self.assertNotEqual(rc, 0)
        combined = out + err
        self.assertNotIn(
            "Traceback", combined,
            "a stranger must get a named failure, not a stack trace",
        )
        self.assertIn("INSTALL.md", combined)
        self.assertIn("pip install -e", combined)
        self.assertIn("/plugin marketplace add", combined)


class SourceCheckoutStillEager(unittest.TestCase):
    """From the checkout, manifest consumers behave exactly as before."""

    def test_manifest_loads_from_checkout(self):
        from episteme import cli
        manifest = cli._load_runtime_manifest()
        self.assertIn("vendor_skills", manifest)
        self.assertIn("custom_skills", manifest)


if __name__ == "__main__":
    unittest.main()
