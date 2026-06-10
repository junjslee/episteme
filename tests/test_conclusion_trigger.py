"""Event 139 — conclusion-shape trigger for the v2.0 Epistemic Engine.

The engine's primary decision shape — a load-bearing conclusion handed to
the operator — gets its live trigger:

- ``conclusion_guard.py`` (UserPromptSubmit): conservative positive-system
  lexicon of decision-question shapes (EN + KR). On a hit in a
  kernel-governed project (``.episteme/`` present), writes a per-prompt
  conclusion-pending marker and injects ONE factual context line.
- ``conclusion_gate.py`` (Stop): when the marker is live, the turn is
  ending, and no fresh interrogation verdict exists — block ONCE with a
  factual reason, set the nudge flag BEFORE blocking (livelock-proof by
  construction; the harness's 8-block cap is the backstop, not the
  mechanism). A fresh verdict (``ok`` or ``stop`` — the work happened)
  clears the marker silently. ``stop_hook_active`` short-circuits.
- ``_interrogation.enqueue_verdict_spot_check``: every consumed verdict
  is enqueued sample-all into the Layer 8 queue — the E5 falsifiability
  leg (operator judges substance vs theater).

Spec: docs/DESIGN_V2_0_EPISTEMIC_ENGINE.md §§ 4, 7, 10 (E3/E5).
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from core.hooks import conclusion_guard  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import conclusion_gate  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _interrogation  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _spot_check  # pyright: ignore[reportAttributeAccessIssue]
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


class _TmpProject:
    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        (root / ".episteme").mkdir(parents=True, exist_ok=True)
        return root

    def __exit__(self, *a):
        self._tmp.cleanup()


def _valid_artifact(**overrides) -> dict:
    artifact = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": "Merge the conclusion-trigger hooks into the kernel",
        "claims": [
            {
                "claim": "The nudge flag write precedes the block emission",
                "tier": "measured",
                "load_bearing": True,
                "mechanism": (
                    "conclusion_gate writes nudged=True and returns 0 on "
                    "OSError before any block JSON is emitted"
                ),
                "confidence": 0.9,
                "verification": {
                    "method": "execution",
                    "result": "supported",
                    "evidence": (
                        "pytest GateNudge.test_nudges_once_then_passes "
                        "asserts flag set and second stop passes"
                    ),
                },
            },
        ],
        "opposition": (
            "A reviewer would argue lexicon triggers are exactly the "
            "form-detection the v2 design rejects; counter: detection here "
            "only routes — the substance check stays with the interrogation."
        ),
        "weakest_link": (
            "Lexicon recall on real prompts is unmeasured; cheapest test "
            "is 14 days of soak telemetry on marker hits"
        ),
        "disconfirmation": (
            "A second block for the same prompt cycle appears in any test "
            "or transcript"
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


def _run_main(module, payload: dict) -> tuple[int, str]:
    """Run a hook main() with patched stdin; capture stdout."""
    out = io.StringIO()
    with patch.object(module.sys, "stdin", io.StringIO(json.dumps(payload))):
        with redirect_stdout(out):
            rc = module.main()
    return rc, out.getvalue()


# ---------- Lexicon -------------------------------------------------------


class ConclusionShapeLexicon(unittest.TestCase):
    def test_hits(self):
        for prompt in [
            "Should we migrate the telemetry store to sqlite?",
            "What should I do about the failing soak gate?",
            "Do you recommend merging this tonight?",
            "Is it safe to drop the legacy index now?",
            "Which approach is better for the retry logic — backoff or queue?",
            "Help me decide between pnpm and bun for this repo.",
            "Evaluate whether the cache layer is actually helping.",
            "What are the pros and cons of moving to a monorepo?",
            "이 구조로 가야 할까?",
            "어떤 게 더 나을까요 — REST or GraphQL?",
            "이 방식 추천해?",
            "지금 배포해도 괜찮을까?",
        ]:
            self.assertIsNotNone(
                conclusion_guard.detect_conclusion_shape(prompt),
                f"expected hit: {prompt!r}",
            )

    def test_misses(self):
        for prompt in [
            "Fix the auth bug in login flow.",
            "Run the tests and show me the failures.",
            "What does this function do?",
            "Summarize the changes in this PR.",
            "Rename the variable and update the imports.",
            "테스트 돌려줘",
        ]:
            self.assertIsNone(
                conclusion_guard.detect_conclusion_shape(prompt),
                f"expected miss: {prompt!r}",
            )


# ---------- conclusion_guard (UserPromptSubmit) ---------------------------


class GuardMarker(unittest.TestCase):
    def _payload(self, root: Path, prompt: str) -> dict:
        return {
            "session_id": "sess-1",
            "prompt": prompt,
            "cwd": str(root),
        }

    def test_hit_writes_marker_and_injects_context(self):
        with _TmpProject() as root:
            rc, out = _run_main(
                conclusion_guard,
                self._payload(root, "Should we merge this refactor?"),
            )
            self.assertEqual(rc, 0)
            marker = json.loads(
                (root / ".episteme" / "conclusion-pending.json").read_text()
            )
            self.assertEqual(marker["session_id"], "sess-1")
            self.assertFalse(marker["nudged"])
            data = json.loads(out)
            ctx = data["hookSpecificOutput"]["additionalContext"]
            self.assertIn("load-bearing conclusion", ctx)
            self.assertIn("interrogation", ctx)

    def test_miss_is_silent(self):
        with _TmpProject() as root:
            rc, out = _run_main(
                conclusion_guard, self._payload(root, "Run the tests.")
            )
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "")
            self.assertFalse(
                (root / ".episteme" / "conclusion-pending.json").exists()
            )

    def test_ungoverned_project_is_silent(self):
        with tempfile.TemporaryDirectory() as td:
            rc, out = _run_main(
                conclusion_guard,
                self._payload(Path(td), "Should we merge this refactor?"),
            )
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "")

    def test_fresh_verdict_suppresses_marker(self):
        with _TmpProject() as root:
            _write_artifact(root, _valid_artifact())
            rc, out = _run_main(
                conclusion_guard,
                self._payload(root, "Should we merge this refactor?"),
            )
            self.assertEqual(rc, 0)
            self.assertFalse(
                (root / ".episteme" / "conclusion-pending.json").exists()
            )


# ---------- conclusion_gate (Stop) ----------------------------------------


def _write_marker(root: Path, *, session_id="sess-1", nudged=False,
                  age_seconds=0) -> Path:
    p = root / ".episteme" / "conclusion-pending.json"
    ts = datetime.now(timezone.utc).timestamp() - age_seconds
    p.write_text(json.dumps({
        "session_id": session_id,
        "ts": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
        "prompt_head": "Should we merge this refactor?",
        "shape": "should-we",
        "nudged": nudged,
    }), encoding="utf-8")
    return p


class GateNudge(unittest.TestCase):
    def _payload(self, root: Path, *, active=False) -> dict:
        return {
            "session_id": "sess-1",
            "stop_hook_active": active,
            "cwd": str(root),
        }

    def test_nudges_once_then_passes(self):
        with _TmpProject() as root:
            _write_marker(root)
            rc, out = _run_main(conclusion_gate, self._payload(root))
            self.assertEqual(rc, 0)
            data = json.loads(out)
            self.assertEqual(data["decision"], "block")
            self.assertIn("interrogation", data["reason"])
            # Nudge flag set BEFORE the block landed.
            marker = json.loads(
                (root / ".episteme" / "conclusion-pending.json").read_text()
            )
            self.assertTrue(marker["nudged"])
            # Second Stop: passes and clears the marker.
            rc2, out2 = _run_main(conclusion_gate, self._payload(root))
            self.assertEqual(rc2, 0)
            self.assertEqual(out2.strip(), "")
            self.assertFalse(
                (root / ".episteme" / "conclusion-pending.json").exists()
            )

    def test_stop_hook_active_short_circuits(self):
        with _TmpProject() as root:
            _write_marker(root)
            rc, out = _run_main(
                conclusion_gate, self._payload(root, active=True)
            )
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "")

    def test_fresh_ok_verdict_clears_without_nudge(self):
        with _TmpProject() as root:
            _write_marker(root)
            _write_artifact(root, _valid_artifact())
            rc, out = _run_main(conclusion_gate, self._payload(root))
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "")
            self.assertFalse(
                (root / ".episteme" / "conclusion-pending.json").exists()
            )

    def test_stop_verdict_counts_as_interrogated(self):
        with _TmpProject() as root:
            _write_marker(root)
            _write_artifact(root, _valid_artifact(verdict="stop"))
            rc, out = _run_main(conclusion_gate, self._payload(root))
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "")

    def test_stale_marker_is_cleared_silently(self):
        with _TmpProject() as root:
            _write_marker(root, age_seconds=3 * 3600)
            rc, out = _run_main(conclusion_gate, self._payload(root))
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "")
            self.assertFalse(
                (root / ".episteme" / "conclusion-pending.json").exists()
            )

    def test_other_session_marker_ignored(self):
        with _TmpProject() as root:
            _write_marker(root, session_id="sess-OTHER")
            rc, out = _run_main(conclusion_gate, self._payload(root))
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "")

    def test_no_marker_no_output(self):
        with _TmpProject() as root:
            rc, out = _run_main(conclusion_gate, self._payload(root))
            self.assertEqual(rc, 0)
            self.assertEqual(out.strip(), "")


# ---------- E5 · verdict spot-check enqueue --------------------------------


class VerdictSpotCheck(unittest.TestCase):
    def test_enqueue_sample_all_and_idempotent(self):
        with EphemeralHome(), _TmpProject() as root:
            _write_artifact(root, _valid_artifact())
            first = _interrogation.enqueue_verdict_spot_check(
                root, op_label="git push"
            )
            second = _interrogation.enqueue_verdict_spot_check(
                root, op_label="git push"
            )
            self.assertTrue(first)
            self.assertFalse(second)
            self.assertEqual(_spot_check.count_pending(), 1)

    def test_guard_admission_enqueues_verdict(self):
        with EphemeralHome(), _TmpProject() as root:
            _write_artifact(root, _valid_artifact())
            payload = {
                "tool_name": "Bash",
                "tool_input": {"command": "git push origin main"},
                "cwd": str(root),
            }
            with patch.object(
                guard.sys, "stdin", io.StringIO(json.dumps(payload))
            ):
                rc = guard.main()
            self.assertEqual(rc, 0)
            self.assertEqual(_spot_check.count_pending(), 1)


if __name__ == "__main__":
    unittest.main()
