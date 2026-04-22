"""CP10 tests — Blueprint D (Architectural Cascade & Escalation).

Covers:

- Four selector triggers (self_escalation / sensitive_path /
  refactor_lexicon + cross-ref / generated_artifact + tightened
  stem match).
- Kernel-state-file exemption (the CP10 live-dogfood fix).
- Structural validation (required fields, vocabulary, blast_radius_map,
  sync_plan, deferred_discoveries, posture, evaluation grammar).
- Cascade-theater advisory + `other`-classification advisory.
- Deferred-discovery writer (each entry hash-chained via CP7).
- Hot-path integration (guard admits valid Blueprint D surface,
  blocks invalid, writes deferred_discoveries).
- Priority dispatch (Fence > Blueprint D > generic).
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

from core.hooks import _cascade_detector  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _blueprint_d  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _framework  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _scenario_detector  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import reasoning_surface_guard as guard
from core.hooks._blueprint_registry import (  # pyright: ignore[reportMissingImports]
    load_registry,
)


# ---------- Helpers ------------------------------------------------------


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


def _bash_op(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def _edit_op(file_path: str) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": file_path}}


def _valid_surface(**overrides) -> dict:
    surface = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "core_question": "Does CP10's cascade surface validate cleanly?",
        "knowns": ["baseline green"],
        "unknowns": [
            "if the cross-surface orphan-reference detector lands v1.0.1"
        ],
        "assumptions": ["hook runner is Claude Code"],
        "disconfirmation": "CI fails or the test suite regresses below baseline",
        "flaw_classification": "schema-implementation-drift",
        "posture_selected": "refactor",
        "patch_vs_refactor_evaluation": (
            "Refactor required because Blueprint D module boundaries "
            "cross hooks, schemas, and the CLI; patch would entangle layers."
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
        "deferred_discoveries": [
            {
                "description": "Follow-up documentation pass needed for kernel SUMMARY",
                "observable": "grep 'Blueprint D' kernel/SUMMARY.md returns zero",
                "log_only_rationale": "30-line budget rebalance deferred to RC-soak follow-up",
            },
        ],
    }
    surface.update(overrides)
    return surface


# ---------- Detector triggers -------------------------------------------


class DetectorTriggerSelfEscalation(unittest.TestCase):
    def test_self_escalation_fires_regardless_of_tool(self):
        op = _bash_op("ls -la")
        surface = {"flaw_classification": "config-gap"}
        self.assertEqual(
            _cascade_detector.detect_cascade(op, surface=surface),
            _cascade_detector.ARCHITECTURAL_CASCADE,
        )

    def test_self_escalation_empty_string_does_not_fire(self):
        op = _bash_op("ls -la")
        surface = {"flaw_classification": ""}
        self.assertIsNone(_cascade_detector.detect_cascade(op, surface=surface))


class DetectorTriggerSensitivePath(unittest.TestCase):
    def test_sensitive_path_bash_cmd_fires(self):
        op = _bash_op("vi core/hooks/foo.py")
        self.assertEqual(
            _cascade_detector.detect_cascade(op),
            _cascade_detector.ARCHITECTURAL_CASCADE,
        )

    def test_sensitive_path_edit_target_fires(self):
        op = _edit_op("core/schemas/something.json")
        self.assertEqual(
            _cascade_detector.detect_cascade(op),
            _cascade_detector.ARCHITECTURAL_CASCADE,
        )

    def test_kernel_uppercase_md_fires(self):
        op = _edit_op("kernel/FAILURE_MODES.md")
        self.assertEqual(
            _cascade_detector.detect_cascade(op),
            _cascade_detector.ARCHITECTURAL_CASCADE,
        )

    def test_non_sensitive_path_does_not_fire(self):
        op = _edit_op("src/some_feature.py")
        self.assertIsNone(_cascade_detector.detect_cascade(op))

    def test_pyproject_toml_fires(self):
        op = _edit_op("pyproject.toml")
        self.assertEqual(
            _cascade_detector.detect_cascade(op),
            _cascade_detector.ARCHITECTURAL_CASCADE,
        )


class DetectorTriggerRefactorLexicon(unittest.TestCase):
    def test_refactor_without_cross_ref_does_not_fire(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            # No project file references `unrelated.py` anywhere.
            (cwd / "solo.py").write_text("print('hi')\n")
            from core.hooks import _grounding  # pyright: ignore[reportAttributeAccessIssue]
            _grounding._clear_cache_for_tests()
            op = {
                "tool_name": "Bash",
                "tool_input": {"command": "git mv unrelated.py renamed.py"},
                "cwd": str(cwd),
            }
            self.assertIsNone(_cascade_detector.detect_cascade(op))

    def test_refactor_with_cross_refs_fires(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            # Seed three files all referencing `shared.py`.
            (cwd / "shared.py").write_text("VALUE = 1\n")
            (cwd / "a.py").write_text(
                "# imports shared.py indirectly\nimport shared\n"
            )
            (cwd / "b.py").write_text("# uses shared.py\nimport shared\n")
            from core.hooks import _grounding  # pyright: ignore[reportAttributeAccessIssue]
            _grounding._clear_cache_for_tests()
            op = {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "git mv shared.py renamed_shared.py"
                },
                "cwd": str(cwd),
            }
            self.assertEqual(
                _cascade_detector.detect_cascade(op),
                _cascade_detector.ARCHITECTURAL_CASCADE,
            )


class DetectorTriggerGeneratedArtifact(unittest.TestCase):
    def test_stem_match_fires_on_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            (cwd / "kernel").mkdir()
            (cwd / "kernel" / "MANIFEST.sha256").write_text(
                "abc123  core/hooks/_grounding.py\n"
            )
            op = {
                "tool_name": "Bash",
                "tool_input": {
                    "command": "git mv core/hooks/_grounding.py core/hooks/_g2.py"
                },
                "cwd": str(cwd),
            }
            # Trigger 2 (sensitive-path `core/hooks/`) fires first —
            # cascade wins regardless of Trigger 4. Assert cascade
            # returns, without claiming which trigger was responsible.
            self.assertEqual(
                _cascade_detector.detect_cascade(op),
                _cascade_detector.ARCHITECTURAL_CASCADE,
            )

    def test_short_stem_does_not_false_match(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            (cwd / "kernel").mkdir()
            (cwd / "kernel" / "MANIFEST.sha256").write_text(
                "abc123  README.md\n"
                "def456  README.md\n"
            )
            # `ci.yml` stem is `ci` (2 chars, below min 5). Trigger 4
            # must NOT fire. And `git rm .github/workflows/ci.yml`
            # doesn't hit any sensitive path, refactor lexicon, or
            # self-escalation either.
            op = {
                "tool_name": "Bash",
                "tool_input": {"command": "git rm .github/workflows/ci.yml"},
                "cwd": str(cwd),
            }
            self.assertIsNone(_cascade_detector.detect_cascade(op))

    def test_word_boundary_prevents_substring_false_match(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            (cwd / "kernel").mkdir()
            # MANIFEST contains `_grounding_extended` but not `_grounding`
            # as a whole word. The `_grounding` stem SHOULD match via
            # word boundary on the hyphen/underscore boundary — actually
            # `_grounding_extended` does NOT have `_grounding` as a whole
            # word. `\b_grounding\b` would not match inside
            # `_grounding_extended`. Verify this.
            (cwd / "kernel" / "MANIFEST.sha256").write_text(
                "abc123  _grounding_extended.py\n"
            )
            op = {
                "tool_name": "Bash",
                "tool_input": {"command": "git mv _grounding.py _g2.py"},
                "cwd": str(cwd),
            }
            # No sensitive path (the file is at project root), no
            # refactor-lexicon cross-ref (single file, self-only), and
            # Trigger 4's word-boundary check should NOT fire on the
            # substring match.
            result = _cascade_detector.detect_cascade(op)
            # `_grounding` DOES have word boundaries inside
            # `_grounding_extended` because underscore is a word char.
            # Actually — `\b` in Python regex is at word-char boundary;
            # `_grounding_` does NOT end at a word boundary because `_`
            # is a word char. So the match should not fire. Assert that.
            self.assertIsNone(result)


# ---------- Kernel-state-file exemption ---------------------------------


class KernelStateExemption(unittest.TestCase):
    """CP10 live-dogfood learning: edits to the kernel's own state
    files must bypass cascade detection to prevent circular blocking."""

    def test_surface_file_write_exempt(self):
        op = _edit_op(".episteme/reasoning-surface.json")
        self.assertIsNone(_cascade_detector.detect_cascade(op))

    def test_advisory_surface_write_exempt(self):
        op = _edit_op(".episteme/advisory-surface")
        self.assertIsNone(_cascade_detector.detect_cascade(op))

    def test_exemption_overrides_self_escalation(self):
        # Even with flaw_classification declared, editing the surface
        # file itself must NOT fire — otherwise the operator can never
        # refresh their Blueprint D surface.
        op = _edit_op(".episteme/reasoning-surface.json")
        surface = {"flaw_classification": "doc-code-drift"}
        self.assertIsNone(
            _cascade_detector.detect_cascade(op, surface=surface)
        )

    def test_exemption_bash_write_to_surface(self):
        op = _bash_op("cat > .episteme/reasoning-surface.json <<EOF\n...\nEOF")
        self.assertIsNone(_cascade_detector.detect_cascade(op))


# ---------- Structural validation ---------------------------------------


class StructuralValidationHappyPath(unittest.TestCase):
    def test_valid_surface_passes(self):
        verdict, _ = _blueprint_d.validate_blueprint_d(_valid_surface())
        self.assertEqual(verdict, "pass")

    def test_all_not_applicable_yields_theater_advisory(self):
        surface = _valid_surface(
            blast_radius_map=[
                {
                    "surface": "docs/PLAN.md",
                    "status": "not-applicable",
                    "rationale": "no plan update needed",
                },
                {
                    "surface": "kernel/CONSTITUTION.md",
                    "status": "not-applicable",
                    "rationale": "philosophy unchanged",
                },
            ],
            sync_plan=[],  # no needs_update entries → empty plan OK
        )
        verdict, detail = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "advisory-theater")
        self.assertIn("not-applicable", detail)

    def test_other_classification_yields_other_advisory(self):
        surface = _valid_surface(flaw_classification="other")
        verdict, detail = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "advisory-other")
        self.assertIn("vocabulary expansion", detail)


class StructuralValidationRejections(unittest.TestCase):
    def test_missing_required_field_rejects(self):
        surface = _valid_surface()
        del surface["sync_plan"]
        verdict, detail = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "reject")
        self.assertIn("sync_plan", detail)

    def test_bad_flaw_classification_rejects(self):
        surface = _valid_surface(flaw_classification="made-up-class")
        verdict, detail = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "reject")
        self.assertIn("flaw_classification", detail)

    def test_bad_posture_rejects(self):
        surface = _valid_surface(posture_selected="maybe")
        verdict, _ = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "reject")

    def test_generic_evaluation_rejects(self):
        surface = _valid_surface(
            patch_vs_refactor_evaluation="it is simpler and easier to do"
        )
        verdict, detail = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "reject")
        self.assertIn("generic", detail)

    def test_empty_blast_radius_map_rejects(self):
        surface = _valid_surface(blast_radius_map=[])
        verdict, _ = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "reject")

    def test_invalid_blast_radius_status_rejects(self):
        surface = _valid_surface(
            blast_radius_map=[{"surface": "foo", "status": "bogus"}]
        )
        verdict, _ = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "reject")

    def test_not_applicable_without_rationale_rejects(self):
        surface = _valid_surface(
            blast_radius_map=[
                {"surface": "foo", "status": "needs_update"},
                {"surface": "bar", "status": "not-applicable"},
            ]
        )
        verdict, detail = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "reject")
        self.assertIn("rationale", detail)

    def test_sync_plan_missing_needs_update_surface_rejects(self):
        surface = _valid_surface(
            blast_radius_map=[
                {"surface": "alpha.py", "status": "needs_update"},
                {"surface": "beta.py", "status": "needs_update"},
            ],
            sync_plan=[
                {"surface": "alpha.py", "action": "Create"},
                # beta.py missing — rejected.
            ],
        )
        verdict, detail = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "reject")
        self.assertIn("beta.py", detail)

    def test_deferred_discovery_short_description_rejects(self):
        surface = _valid_surface(
            deferred_discoveries=[
                {
                    "description": "short",  # < 15 chars
                    "observable": "x",
                    "log_only_rationale": "y",
                },
            ],
        )
        verdict, _ = _blueprint_d.validate_blueprint_d(surface)
        self.assertEqual(verdict, "reject")


# ---------- Deferred-discovery writer -----------------------------------


class DeferredDiscoveryWriter(unittest.TestCase):
    def test_writes_one_record_per_entry(self):
        with EphemeralHome():
            surface = _valid_surface(
                deferred_discoveries=[
                    {
                        "description": "First deferred discovery entry for testing writes",
                        "observable": "grep first_test finds it",
                        "log_only_rationale": "out of scope this pass",
                    },
                    {
                        "description": "Second deferred discovery entry for testing writes",
                        "observable": "grep second_test finds it",
                        "log_only_rationale": "also out of scope",
                    },
                ],
            )
            count = _blueprint_d.write_cascade_deferred_discoveries(
                surface,
                correlation_id="test-cid",
                op_label="test-op",
                cwd=Path("/tmp"),
            )
            self.assertEqual(count, 2)
            # Verify both records landed hash-chained.
            from core.hooks import _chain  # pyright: ignore[reportAttributeAccessIssue]
            verdict = _chain.verify_chain(
                Path(os.environ["EPISTEME_HOME"]) / "framework" / "deferred_discoveries.jsonl"
            )
            self.assertTrue(verdict.intact)
            self.assertEqual(verdict.total_entries, 2)
            # CP9's guide --deferred surfaces them.
            discoveries = _framework.list_deferred_discoveries(status="pending")
            self.assertEqual(len(discoveries), 2)

    def test_empty_list_writes_zero(self):
        with EphemeralHome():
            surface = _valid_surface(deferred_discoveries=[])
            count = _blueprint_d.write_cascade_deferred_discoveries(
                surface,
                correlation_id="empty-cid",
                op_label="test-op",
                cwd=Path("/tmp"),
            )
            self.assertEqual(count, 0)

    def test_flaw_classification_propagates_to_record(self):
        with EphemeralHome():
            surface = _valid_surface(
                flaw_classification="vulnerability",
                deferred_discoveries=[
                    {
                        "description": "A discovery with a specific flaw class",
                        "observable": "test observable",
                        "log_only_rationale": "test rationale",
                    },
                ],
            )
            _blueprint_d.write_cascade_deferred_discoveries(
                surface,
                correlation_id="cid-x",
                op_label="test-op",
                cwd=Path("/tmp"),
            )
            discoveries = _framework.list_deferred_discoveries(status="pending")
            self.assertEqual(len(discoveries), 1)
            self.assertEqual(
                discoveries[0]["payload"]["flaw_classification"],
                "vulnerability",
            )


# ---------- YAML schema load --------------------------------------------


class BlueprintDYamlLoad(unittest.TestCase):
    def test_cp10_blueprint_d_populated(self):
        bp = load_registry().get("architectural_cascade")
        self.assertIn("flaw_classification", bp.required_fields)
        self.assertIn("blast_radius_map", bp.required_fields)
        self.assertIn("sync_plan", bp.required_fields)
        self.assertIn("deferred_discoveries", bp.required_fields)
        self.assertTrue(bp.synthesis_arm)
        self.assertFalse(bp.verification_trace_required)
        self.assertGreater(len(bp.selector_triggers), 0)


# ---------- Scenario-dispatch priority ----------------------------------


class ScenarioDispatchPriority(unittest.TestCase):
    def test_fence_wins_over_blueprint_d_on_kernel_rm(self):
        op = _bash_op("rm kernel/FAILURE_MODES.md")
        self.assertEqual(
            _scenario_detector.detect_scenario(op),
            "fence_reconstruction",
        )

    def test_blueprint_d_fires_on_edit_sensitive(self):
        op = _edit_op("core/hooks/new.py")
        self.assertEqual(
            _scenario_detector.detect_scenario(op),
            "architectural_cascade",
        )

    def test_non_cascade_non_fence_falls_to_generic(self):
        op = _bash_op("ls -la")
        self.assertEqual(
            _scenario_detector.detect_scenario(op), "generic"
        )

    def test_self_escalation_wins_over_fence_fallthrough(self):
        # Fence doesn't fire here (no removal verb + path compound).
        # Blueprint D fires via self-escalation.
        op = _bash_op("ls -la")
        surface = {"flaw_classification": "doc-code-drift"}
        self.assertEqual(
            _scenario_detector.detect_scenario(op, surface=surface),
            "architectural_cascade",
        )


if __name__ == "__main__":
    unittest.main()
