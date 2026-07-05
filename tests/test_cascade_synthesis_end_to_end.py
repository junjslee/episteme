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

            # The pairing marker (tool_use_id) is cleaned; the guard's
            # sha1-fallback sibling may survive only when Pre/Post cross
            # a second boundary (TTL-bounded orphan, same shape as the
            # fence arm) — so assert on the deterministic pairing slot.
            pending = home / "state" / "cascade_pending"
            leftovers = [f.name for f in pending.glob("test-use-id-*.json")]
            self.assertEqual(leftovers, [])

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
            leftovers = [f.name for f in pending.glob("test-use-id-*.json")]
            self.assertEqual(leftovers, [])

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

    def test_same_content_emits_exactly_once_across_ops(self):
        # Live-dogfood lesson (Event 143): a session surface carrying
        # flaw_classification makes the self-escalation trigger classify
        # EVERY tool call as cascade — 438 identical-content protocols
        # chained in one session because each command head produced a
        # fresh op_class signature the supersede match could not bound.
        # The know-how lives in the resolution CONTENT: one surface
        # content = one protocol, ever, regardless of which or how many
        # ops run under it.
        surface = _valid_cascade_surface()
        commands = [_CMD, "grep -rn pattern src", "git log --oneline -5"]
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            for i, cmd in enumerate(commands):
                tid = f"test-use-id-cascade-dedup-{i}"
                rc, _, err = _run_guard(surface, Path(d), cmd, tool_use_id=tid)
                self.assertEqual(rc, 0, err)
                rc, _, _ = _run_post_hook(cmd, 0, Path(d), tool_use_id=tid)
                self.assertEqual(rc, 0)
            proto_path = home / "framework" / "protocols.jsonl"
            lines = proto_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(
                len(lines), 1,
                "identical resolution content must emit exactly one protocol",
            )
            payload = json.loads(lines[0])["payload"]
            self.assertTrue(str(payload.get("cascade_hash", "")).startswith("ch_"))

    def test_changed_content_still_supersedes_with_history(self):
        # Dedup must not kill legitimate evolution: the same context
        # resolving again with NEW content (a different pre-committed
        # observable) appends a second record that supersedes the first.
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            first = _valid_cascade_surface()
            rc, _, err = _run_guard(first, Path(d), _CMD, tool_use_id="dedup-a")
            self.assertEqual(rc, 0, err)
            _run_post_hook(_CMD, 0, Path(d), tool_use_id="dedup-a")

            second = _valid_cascade_surface(
                disconfirmation=(
                    "if the guidance bind rate stays at zero for 30 days "
                    "the emitted protocol never fired"
                ),
            )
            rc, _, err = _run_guard(second, Path(d), _CMD, tool_use_id="dedup-b")
            self.assertEqual(rc, 0, err)
            _run_post_hook(_CMD, 0, Path(d), tool_use_id="dedup-b")

            proto_path = home / "framework" / "protocols.jsonl"
            lines = proto_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2, "changed content must append")
            active = _framework.list_protocols()
            self.assertEqual(
                len(active), 1,
                "same context signature must supersede, not accumulate",
            )


class CascadeSynthesisHardening(unittest.TestCase):
    """Event 143 adversarial-review findings, each CONFIRMED by
    execution before these fixes: fail-open dedup on a broken chain,
    unredacted surface fields, cross-arm double emission, a false
    never-raises contract, and unbounded record bloat."""

    def test_dedup_survives_a_chain_break(self):
        # list_protocols(verify=True) silently stops at the first chain
        # break, blinding the dedup to everything past it — the 438-spam
        # can recur after any single upstream break. The dedup walk must
        # read unverified (integrity is verify_chains' job, not dedup's).
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            rc, _, err = _run_guard(_valid_cascade_surface(), Path(d), _CMD,
                                    tool_use_id="break-a")
            self.assertEqual(rc, 0, err)
            _run_post_hook(_CMD, 0, Path(d), tool_use_id="break-a")
            proto_path = home / "framework" / "protocols.jsonl"
            lines = proto_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            # Break chain integrity at record 0 WITHOUT touching the
            # dedup key: perturb the envelope ts so entry_hash no longer
            # matches its content.
            env = json.loads(lines[0])
            env["ts"] = "2020-01-01T00:00:00+00:00"
            proto_path.write_text(json.dumps(env) + "\n", encoding="utf-8")
            # Same content again under a fresh correlation id.
            rc, _, err = _run_guard(_valid_cascade_surface(), Path(d), _CMD,
                                    tool_use_id="break-b")
            self.assertEqual(rc, 0, err)
            _run_post_hook(_CMD, 0, Path(d), tool_use_id="break-b")
            lines = proto_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(
                len(lines), 1,
                "a chain break must not reopen emission for known content",
            )

    def test_surface_fields_are_redacted_in_the_record(self):
        # The observable quotes measured command/test output — exactly
        # where a leaked secret is most likely to appear. _redact was
        # applied to the command only.
        secret_surface = _valid_cascade_surface(
            disconfirmation=(
                "if the probe output shows password=hunter2 or the key "
                "AKIAIOSFODNN7EXAMPLE the gate failed"
            ),
        )
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            rc, _, err = _run_guard(secret_surface, Path(d), _CMD,
                                    tool_use_id="redact-a")
            self.assertEqual(rc, 0, err)
            _run_post_hook(_CMD, 0, Path(d), tool_use_id="redact-a")
            raw = (home / "framework" / "protocols.jsonl").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("hunter2", raw)
            self.assertNotIn("AKIAIOSFODNN7EXAMPLE", raw)
            self.assertIn("REDACTED", raw)

    def test_one_op_emits_at_most_one_arm(self):
        # A correlation-id collision (SHA-1 fallback + lingering marker)
        # could hand BOTH finalizers a marker for one op. Dispatch
        # priority is Fence > Blueprint D: fence emits, cascade must
        # stand down AND still clean its markers.
        from core.hooks import _fence_synthesis as fence_synth  # pyright: ignore[reportAttributeAccessIssue]

        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            cid = "collision-test-id"
            fence_synth.write_pending_marker(
                {
                    "constraint_identified": "core/hooks/_grounding.py:32",
                    "origin_evidence": "commit e1f49c9 added it for CP3 gap #9",
                    "removal_consequence_prediction": (
                        "if deep-scan exits non-zero ungrounded entities pass"
                    ),
                    "reversibility_classification": "reversible",
                    "rollback_path": "git revert HEAD",
                },
                cid, Path(d), "echo collision",
            )
            cascade_synth.write_pending_marker(
                _valid_cascade_surface(), cid, Path(d), "echo collision",
            )
            rc, _, _ = _run_post_hook("echo collision", 0, Path(d),
                                      tool_use_id=cid)
            self.assertEqual(rc, 0)
            lines = (home / "framework" / "protocols.jsonl").read_text(
                encoding="utf-8"
            ).strip().splitlines()
            self.assertEqual(len(lines), 1, "one op must emit at most once")
            payload = json.loads(lines[0])["payload"]
            self.assertEqual(payload["blueprint"], "fence_reconstruction")
            pending = home / "state" / "cascade_pending"
            self.assertEqual(
                list(pending.glob(f"{cid}.json")), [],
                "the standing-down arm must still clean its marker",
            )

    def test_finalize_never_raises_even_when_build_does(self):
        import _context_signature as flat_cs  # type: ignore

        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            cid = "raise-test-id"
            cascade_synth.write_pending_marker(
                _valid_cascade_surface(), cid, Path(d), "echo raising",
            )
            with patch.object(
                flat_cs, "build", side_effect=RuntimeError("boom")
            ):
                result = cascade_synth.finalize_on_success_with_fallback(
                    [cid], 0
                )
            self.assertIsNone(result, "a build failure must not emit")
            pending = home / "state" / "cascade_pending"
            self.assertEqual(list(pending.glob(f"{cid}.json")), [],
                             "marker cleanup must survive the failure")

    def test_blast_radius_list_is_capped_in_the_record(self):
        big = _valid_cascade_surface(
            blast_radius_map=(
                [{"surface": f"core/mod_{i}.py", "status": "needs_update"}
                 for i in range(100)]
            ),
            sync_plan=(
                [{"surface": f"core/mod_{i}.py", "action": "update"}
                 for i in range(100)]
            ),
        )
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            rc, _, err = _run_guard(big, Path(d), _CMD, tool_use_id="cap-a")
            self.assertEqual(rc, 0, err)
            _run_post_hook(_CMD, 0, Path(d), tool_use_id="cap-a")
            lines = (home / "framework" / "protocols.jsonl").read_text(
                encoding="utf-8"
            ).strip().splitlines()
            fields = json.loads(lines[0])["payload"]["source_fields"]
            self.assertLessEqual(len(fields["blast_radius_surfaces"]), 32)
            self.assertEqual(fields["blast_radius_count"], 100)


if __name__ == "__main__":
    unittest.main()
