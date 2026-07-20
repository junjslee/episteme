"""Phase A · v1.0.1 — `_advisory_footer()` in reasoning_surface_guard.

Covers the Frame-stage advisory that surfaces `preferred_lens_order`
(Munger latticework) and `explanation_form` (cognitive.explanation_depth)
from `~/.episteme/derived_knobs.json` inside the surface-template
message the operator sees when a high-impact op blocks on a
missing/stale/incomplete Reasoning Surface.

Advisory-only — the footer is purely informational. Zero exit-code
impact — verified by `test_exit_code_unchanged_*` cases. Soak-safe
per Event 25 scope.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from core.hooks import reasoning_surface_guard as guard


class _TmpKnobs:
    """Point the guard's derived-knobs read at a tmp dir via
    EPISTEME_HOME — the guard resolves the path per call since Event
    171 (the module-load constant was the sandbox-escape bug class).
    """
    def __init__(self, knobs: dict | None):
        self._tmp = tempfile.TemporaryDirectory()
        self._knobs = knobs
        self._patch = None

    def __enter__(self):
        from unittest.mock import patch as _patch
        home = Path(self._tmp.name)
        if self._knobs is not None:
            (home / "derived_knobs.json").write_text(
                json.dumps(self._knobs), encoding="utf-8")
        self._patch = _patch.dict(os.environ, {"EPISTEME_HOME": str(home)})
        self._patch.start()
        return home / "derived_knobs.json"

    def __exit__(self, *exc):
        if self._patch is not None:
            self._patch.stop()
        self._tmp.cleanup()
        return False



class AdvisoryFooterProducer(unittest.TestCase):
    """Unit tests for `_advisory_footer()`."""

    def test_silent_when_knobs_file_absent(self):
        with _TmpKnobs(knobs=None):
            self.assertEqual(guard._advisory_footer(), "")

    def test_silent_when_knobs_file_empty_dict(self):
        with _TmpKnobs(knobs={}):
            self.assertEqual(guard._advisory_footer(), "")

    def test_renders_lens_order_only(self):
        with _TmpKnobs(
            knobs={"preferred_lens_order": ["failure-first", "causal-chain"]}
        ):
            footer = guard._advisory_footer()
        self.assertIn("Operator lens order", footer)
        self.assertIn("failure-first → causal-chain", footer)
        # explanation_form is absent → that hint line is not rendered.
        self.assertNotIn("Explanation depth:", footer)

    def test_renders_explanation_form_only(self):
        with _TmpKnobs(knobs={"explanation_form": "causal-chain"}):
            footer = guard._advisory_footer()
        self.assertIn("Explanation depth: causal-chain", footer)
        self.assertNotIn("Operator lens order", footer)

    def test_renders_both_when_both_set(self):
        with _TmpKnobs(
            knobs={
                "preferred_lens_order": [
                    "failure-first", "causal-chain", "first-principles",
                    "second-order", "base-rate", "buffer", "variety-match",
                    "pattern-recognition",
                ],
                "explanation_form": "causal-chain",
            }
        ):
            footer = guard._advisory_footer()
        self.assertIn("Operator posture (from derived knobs)", footer)
        self.assertIn("Operator lens order", footer)
        # Truncates to first 5 lenses to keep the footer short.
        self.assertIn(
            "failure-first → causal-chain → first-principles → "
            "second-order → base-rate",
            footer,
        )
        self.assertNotIn("pattern-recognition", footer)
        self.assertIn("Explanation depth: causal-chain", footer)

    def test_filters_non_string_lens_entries(self):
        with _TmpKnobs(
            knobs={
                "preferred_lens_order": [
                    "failure-first", 42, None, "causal-chain",
                ],
            }
        ):
            footer = guard._advisory_footer()
        self.assertIn("failure-first → causal-chain", footer)
        self.assertNotIn("42", footer)

    def test_silent_when_lens_wrong_type(self):
        with _TmpKnobs(knobs={"preferred_lens_order": "failure-first"}):
            # Scalar string, not list — _load_derived_knob returns it
            # when default=None, but _advisory_footer's isinstance check
            # rejects non-list values.
            footer = guard._advisory_footer()
        self.assertEqual(footer, "")

    def test_silent_when_explanation_empty_string(self):
        with _TmpKnobs(knobs={"explanation_form": ""}):
            self.assertEqual(guard._advisory_footer(), "")


class SurfaceTemplateIntegration(unittest.TestCase):
    """Verify `_surface_template()` composes base + footer correctly."""

    def test_template_base_unchanged_when_no_knobs(self):
        with _TmpKnobs(knobs=None):
            out = guard._surface_template()
        # Base template content must still appear.
        self.assertIn("Write .episteme/reasoning-surface.json with:", out)
        self.assertIn('"core_question":', out)
        self.assertIn(
            "Lazy values (none, n/a, tbd, 해당 없음, 없음, ...) are rejected.",
            out,
        )
        # No footer added.
        self.assertNotIn("Operator posture", out)

    def test_template_appends_footer_when_knobs_set(self):
        with _TmpKnobs(
            knobs={
                "preferred_lens_order": ["failure-first", "causal-chain"],
                "explanation_form": "causal-chain",
            }
        ):
            out = guard._surface_template()
        # Base content still present.
        self.assertIn("Write .episteme/reasoning-surface.json with:", out)
        # Footer appended at the end.
        self.assertIn("Operator posture (from derived knobs)", out)
        self.assertIn("Operator lens order", out)
        self.assertIn("Explanation depth: causal-chain", out)
        # Order: base first, footer after.
        self.assertLess(
            out.index("Lazy values"),
            out.index("Operator posture"),
        )


class ExitCodeUnchanged(unittest.TestCase):
    """Soak-safety gate: advisory footer must not change any exit code.

    The Reasoning Surface guard returns:
    - 0 when the op is allowed (valid surface or non-high-impact op),
    - 2 when blocked by strict mode,
    - 0 with a JSON advisory on stdout when advisory-mode is active.

    Adding the footer to `_surface_template()` affects only the
    stderr block message and the `additionalContext` advisory string.
    It must NOT change exit codes on any input.
    """

    def test_allowed_op_exit_code_unchanged_with_knobs(self):
        """A non-high-impact payload returns 0 regardless of knob state.

        This is the most sensitive input: the majority of real tool
        calls do not trip HIGH_IMPACT_BASH. If the footer logic
        accidentally ran on these paths and raised, exit code would
        change from 0 → non-0.
        """
        import io
        payload = {"tool_name": "Read", "tool_input": {"file_path": "/x"}}
        for knobs in [
            None,
            {},
            {"preferred_lens_order": ["failure-first"]},
            {"explanation_form": "causal-chain"},
            {
                "preferred_lens_order": ["failure-first", "causal-chain"],
                "explanation_form": "causal-chain",
            },
        ]:
            with _TmpKnobs(knobs=knobs):
                stdin = io.StringIO(json.dumps(payload))
                stdout = io.StringIO()
                stderr = io.StringIO()
                orig_stdin, orig_stdout, orig_stderr = (
                    sys.stdin, sys.stdout, sys.stderr,
                )
                sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr
                try:
                    rc = guard.main()
                finally:
                    sys.stdin, sys.stdout, sys.stderr = (
                        orig_stdin, orig_stdout, orig_stderr,
                    )
                self.assertEqual(rc, 0, f"rc changed with knobs={knobs}")


if __name__ == "__main__":
    unittest.main()
