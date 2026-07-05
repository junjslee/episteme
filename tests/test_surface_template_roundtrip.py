"""Round-trip contract for the guard's own remediation template.

The strict-mode block message prints a Reasoning Surface template. A
stranger who fills EXACTLY the placeholders that template names — with
no access to core/hooks source — must produce a surface that PASSES the
guard's own validation in ONE attempt.

Recon 2026-07-03 measured the pre-fix reality: 5 attempts WITH source
access, because (a) the template omitted `verification_trace` although
Layer 4 (CP6) rejects generic-blueprint high-impact ops without it, and
(b) the template omitted the six Blueprint D fields although the
architectural_cascade validator rejects surfaces missing them. The
template is the product's onboarding surface; PRODUCT_MASTER_PLAN §3
sets the bar (TTFP: one attempt, zero source reading).

Layer 2's rejection message is covered here too: the classifier demands
BOTH a conditional trigger AND a specific observable, but the pre-fix
message described only the trigger-without-observable failure shape —
so a stranger whose field had an observable but no trigger word was
told to add the thing they already had.
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

from core.hooks import _blueprint_d  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _specificity  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import reasoning_surface_guard as guard


# ---------- Helpers ------------------------------------------------------


class EphemeralHome:
    """Redirect EPISTEME_HOME so audit/telemetry writes stay in-test."""

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


def _run_guard(payload: dict, cwd: Path) -> tuple[int, str, str]:
    payload = {**payload, "cwd": str(cwd)}
    raw = json.dumps(payload)
    with patch("sys.stdin", new=io.StringIO(raw)), \
         patch("sys.stdout", new=io.StringIO()) as fake_out, \
         patch("sys.stderr", new=io.StringIO()) as fake_err:
        rc = guard.main()
    return rc, fake_out.getvalue(), fake_err.getvalue()


def _write_surface(cwd: Path, surface: dict) -> None:
    ep = cwd / ".episteme"
    ep.mkdir(exist_ok=True)
    (ep / "reasoning-surface.json").write_text(
        json.dumps(surface), encoding="utf-8"
    )


def _extract_template_json(template_text: str) -> dict:
    """Parse the JSON skeleton out of the printed template.

    The skeleton must be valid JSON — a stranger copies it verbatim and
    replaces placeholder values. Everything from the first `{` to the
    matching closing brace is the skeleton.
    """
    start = template_text.index("{")
    depth = 0
    for i in range(start, len(template_text)):
        ch = template_text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(template_text[start:i + 1])
    raise AssertionError("template JSON skeleton is unbalanced")


# The "mechanical stranger": fills ONLY keys the skeleton names, using
# the op's own context. If a validator-required key is absent from the
# skeleton, it stays absent from the fill — which is exactly the defect
# this suite guards against.
_GENERIC_FILL = {
    "timestamp": lambda: datetime.now(timezone.utc).isoformat(),
    "core_question": "Will pushing this branch regress the remote main?",
    "knowns": ["local suite passed 1366 tests before this push"],
    "unknowns": [
        "if CI diverges from local, the pushed branch turns the run "
        "status to failure"
    ],
    "assumptions": ["origin is reachable and the branch is up to date"],
    "disconfirmation": (
        "if the push lands a regression, CI on the pushed branch fails "
        "with a non-zero exit code within 10 minutes"
    ),
    "verification_trace": {
        "command": "git status --porcelain",
        "threshold_observable": "exit code == 0",
        "window_seconds": 300,
    },
}

_CASCADE_FILL = {
    **_GENERIC_FILL,
    "core_question": "Does editing pyproject.toml keep packaging coherent?",
    "unknowns": [
        "if the packaging config drifts from setup expectations, "
        "pip install exits non-zero"
    ],
    "disconfirmation": (
        "if this edit breaks packaging, `pip install -e .` fails with "
        "a non-zero exit code on the next run"
    ),
    "flaw_classification": sorted(_blueprint_d.FLAW_CLASSES)[0],
    "posture_selected": sorted(_blueprint_d.POSTURE_VALUES)[0],
    "patch_vs_refactor_evaluation": (
        "Patch is sufficient: only pyproject.toml's package metadata "
        "changes; no module boundary or hook layer moves with it."
    ),
    "blast_radius_map": [
        {"surface": "pyproject.toml", "status": "needs_update"},
        {
            "surface": "kernel/CONSTITUTION.md",
            "status": "not-applicable",
            "rationale": "packaging metadata does not touch kernel philosophy",
        },
    ],
    "sync_plan": [
        {"surface": "pyproject.toml", "action": "update package metadata"},
    ],
    "deferred_discoveries": [],
}


def _fill_skeleton(skeleton: dict, samples: dict) -> dict:
    filled = {}
    for key in skeleton:
        if key not in samples:
            raise AssertionError(
                f"template names field {key!r} but the stranger-fill table "
                f"has no sample for it — extend the table"
            )
        value = samples[key]
        filled[key] = value() if callable(value) else value
    return filled


# ---------- Template completeness (fill-free structural checks) ----------


class TemplateNamesRequiredFields(unittest.TestCase):
    """The skeleton must name every field the validators can demand."""

    def test_generic_template_names_verification_trace(self):
        # CP6: generic blueprint declares verification_trace_required
        # with no maps_to — Layer 4 rejects surfaces without the trace.
        tmpl = guard._surface_template("generic")
        skeleton = _extract_template_json(tmpl)
        self.assertIn("verification_trace", skeleton)

    def test_generic_trace_stanza_carries_rc_contract_slots(self):
        skeleton = _extract_template_json(guard._surface_template("generic"))
        trace = skeleton["verification_trace"]
        self.assertIsInstance(trace, dict)
        self.assertIn("command", trace)
        self.assertIn("threshold_observable", trace)
        # window_seconds ships as a literal valid value, not a
        # placeholder string, so a verbatim copy already parses.
        self.assertIsInstance(trace.get("window_seconds"), int)
        self.assertGreater(trace["window_seconds"], 0)
        # The alternate slots must be discoverable without source access.
        self.assertIn("or_test", tmpl_text := tmpl_cache["generic"])
        self.assertIn("or_dashboard", tmpl_text)

    def test_cascade_template_names_all_blueprint_d_fields(self):
        skeleton = _extract_template_json(
            guard._surface_template("architectural_cascade")
        )
        for field in (
            "flaw_classification",
            "posture_selected",
            "patch_vs_refactor_evaluation",
            "blast_radius_map",
            "sync_plan",
            "deferred_discoveries",
        ):
            self.assertIn(field, skeleton, f"template omits {field}")

    def test_cascade_template_lists_actual_enum_values(self):
        # Enum placeholders must enumerate the real vocabulary — sourced
        # from _blueprint_d so template/validator drift fails here.
        tmpl = guard._surface_template("architectural_cascade")
        for flaw in _blueprint_d.FLAW_CLASSES:
            self.assertIn(flaw, tmpl, f"flaw class {flaw!r} not in template")
        for posture in _blueprint_d.POSTURE_VALUES:
            self.assertIn(posture, tmpl, f"posture {posture!r} not in template")

    def test_template_json_skeleton_is_valid_json(self):
        for bp in ("generic", "architectural_cascade", "fence_reconstruction"):
            with self.subTest(blueprint=bp):
                _extract_template_json(guard._surface_template(bp))

    def test_unknown_blueprint_degrades_to_base_template(self):
        # Registry failure must never break the block message itself.
        skeleton = _extract_template_json(
            guard._surface_template("no-such-blueprint")
        )
        self.assertIn("core_question", skeleton)

    def test_default_call_stays_compatible(self):
        # Existing callers (advisory footer tests) call with no args.
        skeleton = _extract_template_json(guard._surface_template())
        self.assertIn("disconfirmation", skeleton)

    def test_base_placeholders_teach_the_fire_shape(self):
        # Layer 2 rejects disconfirmation/unknowns without BOTH a
        # conditional trigger and a specific observable; the placeholder
        # text must say so — it is the only documentation a stranger has.
        tmpl = guard._surface_template("generic")
        skeleton = _extract_template_json(tmpl)
        for field in ("unknowns", "disconfirmation"):
            raw = skeleton[field]
            text = raw[0] if isinstance(raw, list) else raw
            low = text.lower()
            self.assertIn("trigger", low, f"{field} placeholder lacks trigger guidance")
            self.assertIn("observable", low, f"{field} placeholder lacks observable guidance")


# Cache for cross-test template text access (built lazily at import).
tmpl_cache = {"generic": ""}


def setUpModule():
    tmpl_cache["generic"] = guard._surface_template("generic")


# ---------- End-to-end round-trips (strict mode) --------------------------


class StrictModeRoundTrip(unittest.TestCase):
    """Extract the template from a real strict-mode block, fill it
    mechanically, re-run the guard: the second attempt must PASS."""

    def _round_trip(self, payload: dict, samples: dict) -> None:
        with EphemeralHome(), tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            # Attempt 1: no surface → strict block (exit 2) printing
            # the template.
            rc, _, err = _run_guard(payload, cwd)
            self.assertEqual(rc, 2, f"expected strict block, got rc={rc}: {err}")
            self.assertIn("reasoning-surface.json", err)
            skeleton = _extract_template_json(
                err[err.index("Write .episteme/reasoning-surface.json"):]
            )
            # Attempt 2: fill exactly the printed fields, write, re-run.
            _write_surface(cwd, _fill_skeleton(skeleton, samples))
            rc2, _, err2 = _run_guard(payload, cwd)
            self.assertEqual(
                rc2, 0,
                "surface built from the guard's own template was "
                f"rejected — template round-trip broken: {err2}",
            )

    def test_git_push_generic_blueprint_round_trips(self):
        self._round_trip(
            {"tool_name": "Bash", "tool_input": {"command": "git push origin main"}},
            _GENERIC_FILL,
        )

    def test_pyproject_edit_cascade_blueprint_round_trips(self):
        self._round_trip(
            {"tool_name": "Edit", "tool_input": {"file_path": "pyproject.toml"}},
            _CASCADE_FILL,
        )

    def test_block_message_template_matches_active_blueprint(self):
        # The printed template must be the one for the blueprint that
        # will validate the retry — not a generic stub.
        with EphemeralHome(), tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            rc, _, err = _run_guard(
                {"tool_name": "Edit", "tool_input": {"file_path": "pyproject.toml"}},
                cwd,
            )
            self.assertEqual(rc, 2)
            self.assertIn("flaw_classification", err)
            self.assertIn("blast_radius_map", err)


# ---------- Layer 2 rejection message accuracy ----------------------------


class Layer2MessageNamesMissingPart(unittest.TestCase):
    """The tautological rejection must say which half is missing."""

    def _reject_detail(self, disconfirmation: str) -> str:
        with EphemeralHome(), tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            surface = _fill_skeleton(
                _extract_template_json(guard._surface_template("generic")),
                _GENERIC_FILL,
            )
            surface["disconfirmation"] = disconfirmation
            _write_surface(cwd, surface)
            rc, _, err = _run_guard(
                {"tool_name": "Bash",
                 "tool_input": {"command": "git push origin main"}},
                cwd,
            )
            self.assertEqual(rc, 2, f"expected Layer 2 reject: {err}")
            return err

    def test_observable_without_trigger_names_missing_trigger(self):
        # Pre-fix message told this user to "add an observable" they
        # already had. It must name the missing trigger instead.
        err = self._reject_detail(
            "the error rate metric exceeds 5% on the dashboard"
        )
        self.assertIn("missing conditional trigger", err)
        self.assertNotIn("missing specific observable", err)

    def test_trigger_without_observable_names_missing_observable(self):
        err = self._reject_detail(
            "if the deployment goes wrong in some way somehow"
        )
        self.assertIn("missing specific observable", err)
        self.assertNotIn("missing conditional trigger", err)

    def test_rejection_states_both_halves_required(self):
        err = self._reject_detail(
            "if the deployment goes wrong in some way somehow"
        )
        self.assertIn("BOTH", err)

    def test_specificity_parts_helper(self):
        verdict, has_trigger, has_observable = (
            _specificity.classify_disconfirmation_parts(
                "if the deploy goes wrong somehow"
            )
        )
        self.assertEqual(verdict, "tautological")
        self.assertTrue(has_trigger)
        self.assertFalse(has_observable)


if __name__ == "__main__":
    unittest.main()
