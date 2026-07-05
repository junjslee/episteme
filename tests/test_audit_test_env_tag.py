"""Audit records written under a test runner carry `test_env: true`.

E3 measurement integrity (kernel/FALSIFIABILITY_CONDITIONS.md § E3):
the 2026-07-03 recon found 38 of the first 50 interrogation-source
audit records were pytest fixtures — the documented E3 grep would have
counted suite noise as lived usage, making the condition unfalsifiable
as measured. The guard now tags records written while
PYTEST_CURRENT_TEST is set; the measurement excludes them. Tag, don't
drop: dropped records would hide real gate activity.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.hooks import reasoning_surface_guard as guard

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_SCRIPT = REPO_ROOT / "core" / "hooks" / "reasoning_surface_guard.py"


def _block_payload(cwd: Path) -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": "git push origin main"},
        "cwd": str(cwd),
    }


class AuditTestEnvTag(unittest.TestCase):
    def test_records_under_pytest_are_tagged(self):
        # In-process: the pytest runner sets PYTEST_CURRENT_TEST, so
        # the strict-block audit record must carry the tag.
        self.assertIn("PYTEST_CURRENT_TEST", os.environ)
        with tempfile.TemporaryDirectory() as home, \
             tempfile.TemporaryDirectory() as cwd, \
             patch.dict(os.environ, {"HOME": home}):
            raw = json.dumps(_block_payload(Path(cwd)))
            with patch("sys.stdin", new=io.StringIO(raw)), \
                 patch("sys.stdout", new=io.StringIO()), \
                 patch("sys.stderr", new=io.StringIO()):
                rc = guard.main()
            self.assertEqual(rc, 2)
            lines = (Path(home) / ".episteme" / "audit.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            record = json.loads(lines[-1])
            self.assertIs(record.get("test_env"), True)

    def test_records_outside_pytest_are_untagged(self):
        # Subprocess with PYTEST_CURRENT_TEST stripped — a lived-use
        # record must NOT carry the tag.
        with tempfile.TemporaryDirectory() as home, \
             tempfile.TemporaryDirectory() as cwd:
            env = {
                k: v for k, v in os.environ.items()
                if k != "PYTEST_CURRENT_TEST"
            }
            env["HOME"] = home
            proc = subprocess.run(
                [sys.executable, str(GUARD_SCRIPT)],
                input=json.dumps(_block_payload(Path(cwd))),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(proc.returncode, 2, proc.stderr)
            lines = (Path(home) / ".episteme" / "audit.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            record = json.loads(lines[-1])
            self.assertNotIn("test_env", record)


if __name__ == "__main__":
    unittest.main()
