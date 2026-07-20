"""Fresh-user onboarding journey: init → doctor → bootstrap, for real.

The 2026-07-03 recon found the onboarding trio had ZERO integration
coverage — test_profile_cognition mocks _doctor and
_resolve_bootstrap_target — so a regression in the exact path a
stranger walks would ship through green CI (and dead-on-arrival
onboarding is how the project lost its one external adopter, issues
#1/#14). This suite drives the real commands as subprocesses against a
sandboxed working-tree copy with a sandboxed HOME: no mocks, no
operator-machine state, no writes outside the sandbox.

Also pins scaffold integrity (T5): every `@file` import in a generated
CLAUDE.md must resolve to a file the scaffold actually created —
templates/project/CLAUDE.md used to import @HARNESS.md
unconditionally while bootstrap only creates HARNESS.md under
--harness, so every default scaffold began life with a dangling
memory-index reference.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from episteme.doc_lifecycle import parse_marker_text, VALID_STATUSES  # noqa: E402

_IGNORE = shutil.ignore_patterns(
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
    "build", "dist", ".episteme", "web",
)

# The operator-instance canonicals are gitignored symlinks into
# ~/episteme-private; a stranger's clone does not have them. Remove
# them from the sandbox so `init` exercises its real seeding path.
_CANONICALS = (
    "operator_profile.md", "cognitive_profile.md",
    "workflow_policy.md", "python_runtime_policy.md",
    "agent_feedback.md",
)


class FreshUserJourney(unittest.TestCase):
    tmp: tempfile.TemporaryDirectory
    sandbox: Path
    home: Path

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.sandbox = root / "episteme"
        # Working-tree copy, not a git clone: the journey must test the
        # tree under development (a clone would test HEAD, making a
        # fix-then-test TDD cycle impossible).
        shutil.copytree(
            REPO_ROOT, cls.sandbox, ignore=_IGNORE, symlinks=True,
        )
        mem = cls.sandbox / "core" / "memory" / "global"
        for name in _CANONICALS:
            path = mem / name
            if path.exists() or path.is_symlink():
                path.unlink()
        for stale in (cls.sandbox / "docs").iterdir():
            if stale.is_symlink() and not stale.exists():
                stale.unlink()  # dangling private-doc symlinks
        cls.home = root / "home"
        cls.home.mkdir()
        # The fresh-user persona has Claude Code by definition (they arrive
        # via the plugin), but the machine running this suite may not (CI
        # runners don't). doctor treats `claude` as required, so the journey
        # must not inherit that host accident: a stub on PATH keeps the
        # verdict about episteme's own path, deterministic on every machine.
        cls.stub_bin = root / "stub-bin"
        cls.stub_bin.mkdir()
        stub = cls.stub_bin / "claude"
        stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        stub.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _run(self, *args: str, cwd: Path | None = None) -> tuple[int, str]:
        env = {
            **os.environ,
            "HOME": str(self.home),
            "EPISTEME_HOME": str(self.home / ".episteme"),
            "PYTHONPATH": str(self.sandbox / "src"),
            "PATH": f"{self.stub_bin}{os.pathsep}{os.environ.get('PATH', '')}",
        }
        proc = subprocess.run(
            [
                sys.executable, "-c",
                "import sys; from episteme.cli import main; "
                "raise SystemExit(main(sys.argv[1:]))",
                *args,
            ],
            cwd=str(cwd or self.sandbox),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc.returncode, proc.stdout + proc.stderr

    def _assert_imports_resolve(self, project: Path):
        claude_md = project / "CLAUDE.md"
        self.assertTrue(claude_md.exists())
        for line in claude_md.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("@"):
                ref = project / line[1:]
                self.assertTrue(
                    ref.exists(),
                    f"generated CLAUDE.md imports {line} but the "
                    f"scaffold never created {ref.name} — dangling "
                    f"memory-index reference",
                )

    def test_full_journey(self):
        # Step 1 — init seeds the canonicals a fresh clone lacks.
        rc, out = self._run("init")
        self.assertEqual(rc, 0, out)
        mem = self.sandbox / "core" / "memory" / "global"
        for name in ("operator_profile.md", "cognitive_profile.md",
                     "workflow_policy.md", "agent_feedback.md"):
            with self.subTest(seeded=name):
                self.assertTrue((mem / name).exists(), f"{name} not seeded")

        # Step 1b — init is idempotent; a second run must not fail or
        # clobber.
        marker = "operator-edited sentinel line"
        profile = mem / "operator_profile.md"
        profile.write_text(
            profile.read_text(encoding="utf-8") + f"\n{marker}\n",
            encoding="utf-8",
        )
        rc, out = self._run("init")
        self.assertEqual(rc, 0, out)
        self.assertIn(marker, profile.read_text(encoding="utf-8"))

        # Step 2 — doctor gives a verdict, exit 0, in the sandbox.
        rc, out = self._run("doctor")
        self.assertEqual(rc, 0, out)

        # Step 3 — default bootstrap scaffolds a coherent project.
        project = Path(self.tmp.name) / "proj"
        rc, out = self._run("bootstrap", str(project))
        self.assertEqual(rc, 0, out)
        # PLAN.md retired at Event 168 — the scaffold seeds only docs
        # that actually get tracked across handoffs.
        for rel in ("AGENTS.md", "CLAUDE.md", "docs/REQUIREMENTS.md",
                    "docs/EVENTS.md",
                    "docs/RUN_CONTEXT.md", "docs/NEXT_STEPS.md",
                    ".claude/settings.json"):
            with self.subTest(scaffold=rel):
                self.assertTrue((project / rel).exists(), f"{rel} missing")
        json.loads((project / ".claude" / "settings.json").read_text())
        # T5 contract: no dangling @imports in the default scaffold.
        self._assert_imports_resolve(project)
        # §9.5 contract: the prose seam matches the import seam — a default
        # scaffold's AGENTS.md must not tell agents to read a HARNESS.md
        # that bootstrap never created.
        self.assertNotIn(
            "HARNESS.md",
            (project / "AGENTS.md").read_text(encoding="utf-8"),
            "default scaffold AGENTS.md must not reference an absent HARNESS.md",
        )

        # Step 4 — bootstrap --harness creates HARNESS.md AND imports it.
        project_h = Path(self.tmp.name) / "proj-harness"
        rc, out = self._run("bootstrap", str(project_h), "--harness", "auto")
        self.assertEqual(rc, 0, out)
        self.assertTrue((project_h / "HARNESS.md").exists(), out)
        self.assertIn(
            "@HARNESS.md",
            (project_h / "CLAUDE.md").read_text(encoding="utf-8"),
            "harnessed scaffold must import the HARNESS.md it created",
        )
        self.assertIn(
            "`HARNESS.md`",
            (project_h / "AGENTS.md").read_text(encoding="utf-8"),
            "harnessed scaffold AGENTS.md must list HARNESS.md as memory",
        )
        self._assert_imports_resolve(project_h)

        # Step 4b — harness apply AFTER a default bootstrap keeps both
        # seams coherent in the other direction (T5 for CLAUDE.md, §9.5
        # for AGENTS.md prose).
        rc, out = self._run("harness", "apply", "generic", str(project))
        self.assertEqual(rc, 0, out)
        self.assertIn(
            "@HARNESS.md",
            (project / "CLAUDE.md").read_text(encoding="utf-8"),
            "post-hoc harness apply must add the CLAUDE.md import",
        )
        self.assertIn(
            "`HARNESS.md`",
            (project / "AGENTS.md").read_text(encoding="utf-8"),
            "post-hoc harness apply must add the AGENTS.md memory line",
        )
        self._assert_imports_resolve(project)

        # Step 5 — nothing leaked outside the sandbox HOME: the state
        # dir the hooks write to exists under the sandboxed HOME (or
        # not at all), never under the operator's real one (guarded by
        # env, asserted for the audit trail).
        self.assertFalse(
            (Path(self.tmp.name) / ".episteme").exists(),
            "state written outside the sandboxed HOME",
        )

    def test_scaffold_docs_carry_lifecycle_markers(self):
        """Event 150: a fresh scaffold hands the adopter the cured doc pattern.

        Every seeded ``docs/*.md`` ships a valid lifecycle marker on line 1
        (so the adopter's own ``episteme docs lint`` is green from day one),
        ``EVENTS.md`` carries its seeded one-line history row, and the retired
        pre-E145 append-log ``PROGRESS.md`` is NOT scaffolded.
        """
        project = Path(self.tmp.name) / "proj-markers"
        rc, out = self._run("bootstrap", str(project))
        self.assertEqual(rc, 0, out)

        seeded_docs = (
            "REQUIREMENTS.md", "EVENTS.md",
            "NEXT_STEPS.md", "RUN_CONTEXT.md",
        )
        for name in seeded_docs:
            with self.subTest(marker=name):
                path = project / "docs" / name
                self.assertTrue(path.exists(), f"docs/{name} missing")
                first_line = path.read_text(encoding="utf-8").splitlines()[0]
                marker = parse_marker_text(first_line)
                self.assertIsNotNone(
                    marker,
                    f"docs/{name} line 1 carries no lifecycle marker: "
                    f"{first_line!r}",
                )
                self.assertIn(
                    marker.status, VALID_STATUSES,
                    f"docs/{name} marker status={marker.status!r} is not a "
                    f"valid lifecycle status",
                )
                self.assertTrue(
                    marker.reviewed_as_of,
                    f"docs/{name} marker is missing reviewed_as_of",
                )

        events = (project / "docs" / "EVENTS.md").read_text(encoding="utf-8")
        self.assertIn(
            "| E1 |", events,
            "EVENTS.md must ship its seeded one-line history row",
        )
        self.assertFalse(
            (project / "docs" / "PROGRESS.md").exists(),
            "retired docs/PROGRESS.md must not be scaffolded (Event 150)",
        )


if __name__ == "__main__":
    unittest.main()
