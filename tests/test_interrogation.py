"""Event 138 · v2.0 Epistemic Engine — interrogation verdict artifact.

Covers:

- `_interrogation.artifact_status` — deterministic validation of the
  verdict artifact: freshness (content ts OR file mtime — stale-at-birth
  fix), structural floors (load-bearing claims, external-evidence
  verification, non-vacuous opposition / weakest link / disconfirmation),
  verdict semantics (stop fails closed; refuted load-bearing claim with a
  `proceed` verdict is a contradiction).
- Guard integration — a fresh valid verdict admits a high-impact op in
  strict mode when no Reasoning Surface exists; absent/invalid verdicts
  keep the v1 block.
- Lesson synthesis — `maybe_synthesize_lesson` writes a protocol from a
  fresh verdict's non-null lesson on a successful op, dedupes by lesson
  hash, and the protocol surfaces through the existing guidance query.

Spec: docs/DESIGN_V2_0_EPISTEMIC_ENGINE.md §§ 6-8.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.hooks import _interrogation  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _framework  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _guidance  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _context_signature  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import reasoning_surface_guard as guard


class EphemeralHome:
    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = None

    def __enter__(self) -> Path:
        self._orig = os.environ.get("EPISTEME_HOME")
        os.environ["EPISTEME_HOME"] = self._tmp.name
        return Path(self._tmp.name)

    def __exit__(self, *a):
        if self._orig is None:
            os.environ.pop("EPISTEME_HOME", None)
        else:
            os.environ["EPISTEME_HOME"] = self._orig
        self._tmp.cleanup()


def _valid_artifact(**overrides) -> dict:
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": "Merge the read-only exemption into the cascade detector",
        "claims": [
            {
                "claim": "The exemption rejects any command containing redirection",
                "tier": "measured",
                "load_bearing": True,
                "mechanism": (
                    "_WRITE_CAPABLE_RE matches '>' after safe-sink stripping, "
                    "so exemption short-circuits to False before head checks"
                ),
                "confidence": 0.9,
                "verification": {
                    "method": "execution",
                    "result": "supported",
                    "evidence": (
                        "pytest tests/test_blueprint_d_cascade.py::"
                        "DetectorReadOnlyExemption passed 17/17"
                    ),
                },
            },
            {
                "claim": "No existing caller depends on read-only ops being flagged",
                "tier": "inferred",
                "load_bearing": False,
                "mechanism": "full suite green implies no test encodes that dependency",
                "confidence": 0.7,
                "verification": {
                    "method": "none",
                    "result": "unverifiable",
                    "evidence": "",
                },
            },
        ],
        "opposition": (
            "A security reviewer would argue the allowlist widens the bypass "
            "surface: a future read-only head added carelessly could mask a "
            "mutating subcommand, and pipe-segment splitting is not a shell parser."
        ),
        "weakest_link": (
            "The segment splitter mishandles quoted separators; cheapest test: "
            "run the adversarial quoted-command cases in the suite"
        ),
        "disconfirmation": (
            "A mutating command admitted by the exemption appears in audit.jsonl"
        ),
        "verdict": "proceed",
        "lesson": None,
    }
    artifact.update(overrides)
    return artifact


def _write_artifact(project: Path, artifact: dict) -> Path:
    epi = project / ".episteme"
    epi.mkdir(parents=True, exist_ok=True)
    p = epi / "interrogation.json"
    p.write_text(json.dumps(artifact), encoding="utf-8")
    return p


class _TmpProject:
    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / ".episteme").mkdir(parents=True, exist_ok=True)
        return root

    def __exit__(self, *a):
        self._tmp.cleanup()


# ---------- artifact_status ----------------------------------------------


class ArtifactStatus(unittest.TestCase):
    def test_missing_file(self):
        with _TmpProject() as root:
            status, _ = _interrogation.artifact_status(root)
            self.assertEqual(status, "missing")

    def test_invalid_json(self):
        with _TmpProject() as root:
            p = root / ".episteme" / "interrogation.json"
            p.write_text("{not json", encoding="utf-8")
            status, _ = _interrogation.artifact_status(root)
            self.assertEqual(status, "invalid")

    def test_valid_fresh_artifact_ok(self):
        with _TmpProject() as root:
            _write_artifact(root, _valid_artifact())
            status, detail = _interrogation.artifact_status(root)
            self.assertEqual(status, "ok", detail)
            self.assertIn("proceed", detail)

    def test_stale_at_birth_ts_rescued_by_fresh_mtime(self):
        # An agent that guessed wall-clock wrong writes a past ts; the
        # file itself was just written. mtime is ground truth.
        old_ts = (
            datetime.now(timezone.utc) - timedelta(hours=7)
        ).isoformat()
        with _TmpProject() as root:
            _write_artifact(root, _valid_artifact(timestamp=old_ts))
            status, _ = _interrogation.artifact_status(root)
            self.assertEqual(status, "ok")

    def test_old_ts_and_old_mtime_is_stale(self):
        old_ts = (
            datetime.now(timezone.utc) - timedelta(hours=7)
        ).isoformat()
        with _TmpProject() as root:
            p = _write_artifact(root, _valid_artifact(timestamp=old_ts))
            backdate = time.time() - 7 * 3600
            os.utime(p, (backdate, backdate))
            status, _ = _interrogation.artifact_status(root)
            self.assertEqual(status, "stale")

    def test_no_load_bearing_claim_invalid(self):
        artifact = _valid_artifact()
        for c in artifact["claims"]:
            c["load_bearing"] = False
        with _TmpProject() as root:
            _write_artifact(root, artifact)
            status, detail = _interrogation.artifact_status(root)
            self.assertEqual(status, "invalid")
            self.assertIn("load", detail)

    def test_load_bearing_without_external_verification_invalid(self):
        artifact = _valid_artifact()
        artifact["claims"][0]["verification"]["method"] = "none"
        with _TmpProject() as root:
            _write_artifact(root, artifact)
            status, detail = _interrogation.artifact_status(root)
            self.assertEqual(status, "invalid")
            self.assertIn("verif", detail.lower())

    def test_short_evidence_invalid(self):
        artifact = _valid_artifact()
        artifact["claims"][0]["verification"]["evidence"] = "ok"
        with _TmpProject() as root:
            _write_artifact(root, artifact)
            status, _ = _interrogation.artifact_status(root)
            self.assertEqual(status, "invalid")

    def test_lazy_opposition_invalid(self):
        with _TmpProject() as root:
            _write_artifact(root, _valid_artifact(opposition="none"))
            status, _ = _interrogation.artifact_status(root)
            self.assertEqual(status, "invalid")

    def test_short_opposition_invalid(self):
        with _TmpProject() as root:
            _write_artifact(
                root, _valid_artifact(opposition="seems fine to me overall")
            )
            status, _ = _interrogation.artifact_status(root)
            self.assertEqual(status, "invalid")

    def test_stop_verdict_fails_closed(self):
        with _TmpProject() as root:
            _write_artifact(root, _valid_artifact(verdict="stop"))
            status, _ = _interrogation.artifact_status(root)
            self.assertEqual(status, "stop")

    def test_bad_verdict_enum_invalid(self):
        with _TmpProject() as root:
            _write_artifact(root, _valid_artifact(verdict="ship it"))
            status, _ = _interrogation.artifact_status(root)
            self.assertEqual(status, "invalid")

    def test_refuted_load_bearing_with_proceed_is_contradiction(self):
        artifact = _valid_artifact()
        artifact["claims"][0]["verification"]["result"] = "refuted"
        with _TmpProject() as root:
            _write_artifact(root, artifact)
            status, detail = _interrogation.artifact_status(root)
            self.assertEqual(status, "invalid")
            self.assertIn("refuted", detail)

    def test_refuted_load_bearing_with_revision_verdict_ok(self):
        artifact = _valid_artifact(verdict="proceed-with-revision")
        artifact["claims"][0]["verification"]["result"] = "refuted"
        # A second verified-supported load-bearing claim keeps the
        # external-evidence floor satisfied.
        artifact["claims"].append(dict(
            artifact["claims"][0],
            claim="The revision addresses the refuted dependency cleanly",
            verification={
                "method": "file-read",
                "result": "supported",
                "evidence": "read core/hooks/_cascade_detector.py exemption block",
            },
        ))
        with _TmpProject() as root:
            _write_artifact(root, artifact)
            status, detail = _interrogation.artifact_status(root)
            self.assertEqual(status, "ok", detail)


# ---------- Guard integration --------------------------------------------


def _run_guard_main(payload: dict) -> int:
    with patch.object(guard.sys, "stdin", io.StringIO(json.dumps(payload))):
        return guard.main()


class GuardIntegration(unittest.TestCase):
    def _payload(self, root: Path) -> dict:
        return {
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin main"},
            "cwd": str(root),
        }

    def test_valid_verdict_admits_high_impact_op_without_surface(self):
        with EphemeralHome(), _TmpProject() as root:
            _write_artifact(root, _valid_artifact())
            rc = _run_guard_main(self._payload(root))
            self.assertEqual(rc, 0)

    def test_no_surface_no_verdict_blocks_in_strict_mode(self):
        with EphemeralHome(), _TmpProject() as root:
            rc = _run_guard_main(self._payload(root))
            self.assertEqual(rc, 2)

    def test_stop_verdict_does_not_admit(self):
        with EphemeralHome(), _TmpProject() as root:
            _write_artifact(root, _valid_artifact(verdict="stop"))
            rc = _run_guard_main(self._payload(root))
            self.assertEqual(rc, 2)

    def test_vacuous_verdict_does_not_admit(self):
        with EphemeralHome(), _TmpProject() as root:
            _write_artifact(root, _valid_artifact(opposition="n/a"))
            rc = _run_guard_main(self._payload(root))
            self.assertEqual(rc, 2)

    def test_admission_audited_with_interrogation_source(self):
        with EphemeralHome() as home, _TmpProject() as root:
            _write_artifact(root, _valid_artifact())
            rc = _run_guard_main(self._payload(root))
            self.assertEqual(rc, 0)
            audit = Path.home() / ".episteme" / "audit.jsonl"
            # _write_audit targets Path.home()/.episteme — EPISTEME_HOME
            # redirection is a known gap there; read whichever exists.
            candidates = [audit, Path(home) / "audit.jsonl"]
            lines = []
            for c in candidates:
                if c.exists():
                    lines = c.read_text(encoding="utf-8").strip().splitlines()
                    break
            self.assertTrue(lines, "no audit record written")
            last = json.loads(lines[-1])
            self.assertEqual(last.get("action"), "passed")
            self.assertEqual(last.get("source"), "interrogation")


# ---------- Lesson synthesis ----------------------------------------------


def _lesson() -> dict:
    return {
        "context": "episteme core/hooks cascade detector calibration",
        "rule": "exempt provably read-only commands before sensitive-path checks",
        "because": "verified 18k high-impact classifications were inspection noise",
    }


class LessonSynthesis(unittest.TestCase):
    def _post_payload(self, root: Path) -> dict:
        return {
            "tool_name": "Bash",
            "tool_input": {"command": "git push origin main"},
            "cwd": str(root),
        }

    def test_lesson_written_as_protocol_on_success(self):
        with EphemeralHome(), _TmpProject() as root:
            _write_artifact(root, _valid_artifact(lesson=_lesson()))
            out = _interrogation.maybe_synthesize_lesson(
                self._post_payload(root), exit_code=0
            )
            self.assertIsNotNone(out)
            protocols = _framework.list_protocols(include_superseded=True)
            self.assertEqual(len(protocols), 1)
            payload = protocols[0]["payload"]
            self.assertEqual(payload.get("source"), "interrogation")
            self.assertIn("read-only", payload.get("protocol", ""))

    def test_dedupe_by_lesson_hash(self):
        with EphemeralHome(), _TmpProject() as root:
            _write_artifact(root, _valid_artifact(lesson=_lesson()))
            first = _interrogation.maybe_synthesize_lesson(
                self._post_payload(root), exit_code=0
            )
            second = _interrogation.maybe_synthesize_lesson(
                self._post_payload(root), exit_code=0
            )
            self.assertIsNotNone(first)
            self.assertIsNone(second)
            protocols = _framework.list_protocols(include_superseded=True)
            self.assertEqual(len(protocols), 1)

    def test_failed_op_synthesizes_nothing(self):
        with EphemeralHome(), _TmpProject() as root:
            _write_artifact(root, _valid_artifact(lesson=_lesson()))
            out = _interrogation.maybe_synthesize_lesson(
                self._post_payload(root), exit_code=1
            )
            self.assertIsNone(out)
            self.assertEqual(
                len(_framework.list_protocols(include_superseded=True)), 0
            )

    def test_null_lesson_synthesizes_nothing(self):
        with EphemeralHome(), _TmpProject() as root:
            _write_artifact(root, _valid_artifact(lesson=None))
            out = _interrogation.maybe_synthesize_lesson(
                self._post_payload(root), exit_code=0
            )
            self.assertIsNone(out)

    def test_e2e_lesson_surfaces_through_guidance_query(self):
        with EphemeralHome(), _TmpProject() as root:
            _write_artifact(root, _valid_artifact(lesson=_lesson()))
            out = _interrogation.maybe_synthesize_lesson(
                self._post_payload(root), exit_code=0
            )
            self.assertIsNotNone(out)
            _guidance._clear_cache_for_tests()
            candidate = _context_signature.build(
                root, blueprint_name="generic", op_class="git push",
            )
            match = _guidance.query(candidate, cwd=root)
            self.assertIsNotNone(match)
            self.assertEqual(
                match.protocol_payload.get("source"), "interrogation"
            )


class RootBoundary(unittest.TestCase):
    """Event 148 — interrogation artifact discovery walks UP to the
    governed root but STOPS at the first repo boundary (`.git` file or
    dir). A nested child repo without its own `.episteme` must NOT resolve
    to the parent's verdict (fail-open: a governed op admitted via a
    verdict the child never authored)."""

    @staticmethod
    def _mk(base: Path, rel: str, is_dir: bool = False, content: str = "") -> Path:
        p = base / rel
        if is_dir:
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        return p

    def test_walks_up_to_episteme_root_from_subdir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            self._mk(root, ".git", is_dir=True)
            self._mk(root, ".episteme", is_dir=True)
            sub = self._mk(root, "pkg/src", is_dir=True)
            self.assertEqual(_interrogation._canonical_project_root(sub), root)

    def test_child_repo_does_not_inherit_parent_verdict(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td).resolve()
            self._mk(td, "parent/.git", is_dir=True)
            self._mk(td, "parent/.episteme", is_dir=True)
            _write_artifact(td / "parent", _valid_artifact())
            self._mk(td, "parent/child/.git", content="gitdir: /nowhere")
            child = td / "parent" / "child"
            childsub = self._mk(td, "parent/child/src", is_dir=True)
            # child has no `.episteme` → status "missing", NOT the parent's
            # fresh "ok" verdict.
            self.assertEqual(_interrogation.artifact_status(child)[0], "missing")
            self.assertEqual(
                _interrogation.artifact_status(childsub)[0], "missing")

    def test_bare_dir_no_git_no_episteme_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            sub = self._mk(root, "a/b/c", is_dir=True)
            self.assertEqual(_interrogation.artifact_status(sub)[0], "missing")


# ---------- Verdict spot-check enqueue (E5 · Event 157 cap contract) -----


class VerdictSpotCheckEnqueue(unittest.TestCase):
    """enqueue_verdict_spot_check must honor the Layer 8 pending cap
    (Event 157): sample-all by design, but never past the backpressure
    bound the E148 closure rests on."""

    def _spot(self):
        from core.hooks import _spot_check  # pyright: ignore[reportAttributeAccessIssue]
        return _spot_check

    def test_enqueues_below_cap(self):
        with EphemeralHome(), _TmpProject() as proj:
            _write_artifact(proj, _valid_artifact())
            ok = _interrogation.enqueue_verdict_spot_check(
                proj, op_label="cascade:architectural"
            )
            self.assertTrue(ok)
            self.assertEqual(self._spot().count_pending(), 1)

    def test_idempotent_per_artifact_content(self):
        with EphemeralHome(), _TmpProject() as proj:
            _write_artifact(proj, _valid_artifact())
            self.assertTrue(
                _interrogation.enqueue_verdict_spot_check(
                    proj, op_label="cascade:architectural"
                )
            )
            self.assertFalse(
                _interrogation.enqueue_verdict_spot_check(
                    proj, op_label="cascade:architectural"
                )
            )
            self.assertEqual(self._spot().count_pending(), 1)

    def test_declines_at_cap_and_bumps_skip_counter(self):
        with EphemeralHome(), _TmpProject() as proj:
            _spot = self._spot()
            seed = {
                "type": _spot.ENTRY_TYPE,
                "correlation_id": "seed-fresh",
                "queued_at": _spot._iso(datetime.now(timezone.utc)),
                "op_label": "git push",
                "blueprint": "generic",
                "context_signature": {},
                "surface_snapshot": {},
                "multipliers_applied": [],
                "effective_rate_at_sample": 1.0,
            }
            self.assertTrue(_spot.enqueue_direct(seed).queued)
            _write_artifact(proj, _valid_artifact())
            with patch.dict(os.environ, {"EPISTEME_SPOT_CHECK_CAP": "1"}):
                ok = _interrogation.enqueue_verdict_spot_check(
                    proj, op_label="cascade:architectural"
                )
            self.assertFalse(ok)
            self.assertEqual(_spot.count_pending(), 1)
            self.assertEqual(
                _spot.read_skip_counter()["skipped_count"], 1
            )

    def test_at_cap_stale_relief_restores_interrogation_sampling(self):
        with EphemeralHome(), _TmpProject() as proj:
            _spot = self._spot()
            stale = {
                "type": _spot.ENTRY_TYPE,
                "correlation_id": "seed-stale",
                "queued_at": _spot._iso(
                    datetime.now(timezone.utc) - timedelta(days=8)
                ),
                "op_label": "git push",
                "blueprint": "generic",
                "context_signature": {},
                "surface_snapshot": {},
                "multipliers_applied": [],
                "effective_rate_at_sample": 1.0,
            }
            self.assertTrue(_spot.enqueue_direct(stale).queued)
            _write_artifact(proj, _valid_artifact())
            with patch.dict(os.environ, {"EPISTEME_SPOT_CHECK_CAP": "1"}):
                ok = _interrogation.enqueue_verdict_spot_check(
                    proj, op_label="cascade:architectural"
                )
            self.assertTrue(ok)
            self.assertEqual(_spot.stats()["expired"], 1)


if __name__ == "__main__":
    unittest.main()
