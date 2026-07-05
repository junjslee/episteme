"""T13 — Blueprint D synthesis arm, end-to-end (Event 143).

Spec: docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md:204 — on successful
Blueprint D resolution, emit a context-specific cascade protocol:

    "In context `<project + subsystem + flaw_class>`, posture
    `<patch|refactor>` with blast-radius class `<surfaces>` resolved
    without divergence because `<observable>`."

Mechanism mirrors the Fence arm (the only previously-implemented
synthesis path): PreToolUse admission writes a pending marker under
every candidate correlation id; the PostToolUse hook joins by id and
writes the protocol through `_framework.write_protocol` iff
exit_code == 0. Honest T13 limit, same as CP5's: the emit gate is
exit_code == 0 — retrospective sync-plan verification is spec-deferred
to v1.0.1 (spec line 53).

This is the E1 answer: the dominant blueprint class (cascade) could
not compound because it had no emit path. These tests pin that it now
does — and that failure, rejection, and non-cascade ops emit nothing.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.hooks import reasoning_surface_guard as guard
from core.hooks import _scenario_detector as detector  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _cascade_synthesis as cascade_synth  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _framework  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import fence_synthesis as post_hook  # pyright: ignore[reportAttributeAccessIssue]


# ---------- Fixtures (mirrors test_fence_reconstruction_end_to_end) -----

def _valid_cascade_surface(**overrides) -> dict:
    surface = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "core_question": "Does the cascade resolve coherently across its blast radius?",
        "knowns": ["baseline suite green before the edit"],
        "unknowns": [
            "if the cross-surface orphan-reference detector lands v1.0.1"
        ],
        "assumptions": ["hook runner is Claude Code"],
        "disconfirmation": "CI fails or the test suite regresses below baseline",
        "flaw_classification": "schema-implementation-drift",
        "posture_selected": "refactor",
        "patch_vs_refactor_evaluation": (
            "Refactor required because the drift crosses hooks, schemas, "
            "and the CLI; a patch would entangle module layers."
        ),
        "blast_radius_map": [
            {"surface": "core/hooks/new_module.py", "status": "needs_update"},
            {"surface": "tests/test_new.py", "status": "needs_update"},
            {
                "surface": "kernel/CONSTITUTION.md",
                "status": "not-applicable",
                "rationale": "philosophy unchanged",
            },
        ],
        "sync_plan": [
            {"surface": "core/hooks/new_module.py", "action": "Create module"},
            {"surface": "tests/test_new.py", "action": "Add test suite"},
        ],
        "deferred_discoveries": [],
    }
    surface.update(overrides)
    return surface


def _run_guard(
    surface: dict,
    cwd: Path,
    command: str,
    tool_use_id: str | None = "test-use-id-cascade-t13",
) -> tuple[int, str, str]:
    (cwd / ".episteme").mkdir(exist_ok=True)
    (cwd / ".episteme" / "reasoning-surface.json").write_text(
        json.dumps(surface), encoding="utf-8"
    )
    payload: dict = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(cwd),
    }
    if tool_use_id is not None:
        payload["tool_use_id"] = tool_use_id
    raw = json.dumps(payload)
    with patch("sys.stdin", new=io.StringIO(raw)), \
         patch("sys.stdout", new=io.StringIO()) as fake_out, \
         patch("sys.stderr", new=io.StringIO()) as fake_err:
        rc = guard.main()
    return rc, fake_out.getvalue(), fake_err.getvalue()


def _run_post_hook(
    command: str, exit_code: int, cwd: Path,
    tool_use_id: str | None = "test-use-id-cascade-t13",
) -> tuple[int, str, str]:
    payload: dict = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(cwd),
        "tool_response": {"exit_code": exit_code},
    }
    if tool_use_id is not None:
        payload["tool_use_id"] = tool_use_id
    raw = json.dumps(payload)
    with patch("sys.stdin", new=io.StringIO(raw)), \
         patch("sys.stdout", new=io.StringIO()) as fake_out, \
         patch("sys.stderr", new=io.StringIO()) as fake_err:
        rc = post_hook.main()
    return rc, fake_out.getvalue(), fake_err.getvalue()


class _EphemeralEpistemeHome:
    def __enter__(self):
        self._home = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("EPISTEME_HOME")
        os.environ["EPISTEME_HOME"] = self._home.name
        detector._reset_trigger_cache_for_tests()
        return Path(self._home.name)

    def __exit__(self, *a):
        if self._prev is None:
            os.environ.pop("EPISTEME_HOME", None)
        else:
            os.environ["EPISTEME_HOME"] = self._prev
        self._home.cleanup()
        detector._reset_trigger_cache_for_tests()


_CMD = "python scripts/apply_cascade_edit.py"


# ---------- End-to-end synthesis ----------------------------------------

class CascadeSynthesisEndToEnd(unittest.TestCase):
    def test_admitted_cascade_writes_pending_marker(self):
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            rc, _, err = _run_guard(_valid_cascade_surface(), Path(d), _CMD)
            self.assertEqual(rc, 0, err)
            pending = home / "state" / "cascade_pending"
            self.assertTrue(pending.is_dir(), "pending dir must exist")
            markers = list(pending.glob("*.json"))
            self.assertGreaterEqual(len(markers), 1, "marker must be written")

    def test_exit_zero_synthesizes_cascade_protocol(self):
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            rc, _, err = _run_guard(_valid_cascade_surface(), Path(d), _CMD)
            self.assertEqual(rc, 0, err)
            rc, _, _ = _run_post_hook(_CMD, 0, Path(d))
            self.assertEqual(rc, 0)

            proto_path = home / "framework" / "protocols.jsonl"
            self.assertTrue(proto_path.is_file(), "protocol must be written")
            lines = proto_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            envelope = json.loads(lines[0])
            self.assertEqual(envelope["schema_version"], "cp7-chained-v1")
            self.assertEqual(envelope["prev_hash"], "sha256:GENESIS")
            self.assertTrue(envelope["entry_hash"].startswith("sha256:"))

            payload = envelope["payload"]
            self.assertEqual(payload["type"], "protocol")
            self.assertEqual(payload["blueprint"], "architectural_cascade")
            sig = payload["context_signature"]
            self.assertEqual(sig["blueprint"], "architectural_cascade")
            self.assertEqual(sig["project_name"], Path(d).resolve().name)

            text = payload["synthesized_protocol"]
            self.assertIn("posture `refactor`", text)
            self.assertIn("schema-implementation-drift", text)
            self.assertIn("core/hooks", text)  # subsystem from blast radius
            self.assertIn("resolved without divergence because", text)
            self.assertIn("CI fails or the test suite regresses", text)

            # Markers cleaned up in all candidate slots.
            pending = home / "state" / "cascade_pending"
            self.assertEqual(list(pending.glob("*.json")), [])

    def test_exit_nonzero_writes_no_protocol_and_cleans_markers(self):
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            rc, _, err = _run_guard(_valid_cascade_surface(), Path(d), _CMD)
            self.assertEqual(rc, 0, err)
            rc, _, _ = _run_post_hook(_CMD, 1, Path(d))
            self.assertEqual(rc, 0)
            proto_path = home / "framework" / "protocols.jsonl"
            self.assertFalse(
                proto_path.is_file() and proto_path.read_text(encoding="utf-8").strip(),
                "failed op must not synthesize",
            )
            pending = home / "state" / "cascade_pending"
            self.assertEqual(list(pending.glob("*.json")), [])

    def test_generic_op_writes_no_cascade_marker(self):
        generic_surface = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "core_question": "Is this ordinary op safe to run right now?",
            "knowns": ["suite green"],
            "unknowns": ["if CI returns non-zero exit code, parity was false"],
            "assumptions": ["hook runner is Claude Code"],
            "disconfirmation": "CI fails on main after push",
        }
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            _run_guard(generic_surface, Path(d), "echo benign")
            pending = home / "state" / "cascade_pending"
            self.assertEqual(
                list(pending.glob("*.json")) if pending.is_dir() else [],
                [],
                "non-cascade op must not write a cascade marker",
            )

    def test_rejected_surface_writes_no_marker(self):
        # deferred status without rationale is a structural reject.
        bad = _valid_cascade_surface(
            blast_radius_map=[
                {"surface": "core/hooks/x.py", "status": "needs_update"},
                {"surface": "kernel/x.md", "status": "deferred"},
            ],
        )
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            rc, _, _ = _run_guard(bad, Path(d), _CMD)
            self.assertEqual(rc, 2, "structural reject must block")
            pending = home / "state" / "cascade_pending"
            self.assertEqual(
                list(pending.glob("*.json")) if pending.is_dir() else [],
                [],
                "rejected surface must not write a marker",
            )

    def test_corrupt_marker_degrades_gracefully(self):
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            pending = home / "state" / "cascade_pending"
            pending.mkdir(parents=True)
            (pending / "test-use-id-cascade-t13.json").write_text(
                "{not json", encoding="utf-8"
            )
            rc, _, _ = _run_post_hook(_CMD, 0, Path(d))
            self.assertEqual(rc, 0, "PostToolUse must never block")
            proto_path = home / "framework" / "protocols.jsonl"
            self.assertFalse(
                proto_path.is_file() and proto_path.read_text(encoding="utf-8").strip(),
                "corrupt marker must not synthesize",
            )
            self.assertEqual(list(pending.glob("*.json")), [])

    def test_same_context_resolution_supersedes_not_duplicates(self):
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            for _ in range(2):
                rc, _, err = _run_guard(_valid_cascade_surface(), Path(d), _CMD)
                self.assertEqual(rc, 0, err)
                rc, _, _ = _run_post_hook(_CMD, 0, Path(d))
                self.assertEqual(rc, 0)
            proto_path = home / "framework" / "protocols.jsonl"
            lines = proto_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2, "append-only: both records persist")
            active = _framework.list_protocols()
            self.assertEqual(
                len(active), 1,
                "same context signature must supersede, not accumulate",
            )


if __name__ == "__main__":
    unittest.main()
