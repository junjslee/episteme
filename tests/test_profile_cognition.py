import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.agent_os import cli


class ProfileCognitionTests(unittest.TestCase):
    def test_normalize_answers_accepts_both_ranges(self):
        raw = {
            "a": 1,
            "b": 4,
            "c": 0,
            "d": 3,
            "bad": 99,
            "text": "x",
        }
        got = cli._normalize_answers(raw)
        self.assertEqual(got["a"], 2)
        self.assertEqual(got["c"], 1)  # presence of 0 => zero-based mode
        self.assertEqual(got["d"], 4)
        self.assertNotIn("b", got)
        self.assertNotIn("bad", got)
        self.assertNotIn("text", got)

    def test_normalize_answers_one_based_mode_keeps_1_to_4(self):
        got = cli._normalize_answers({"a": 1, "b": 3, "c": 4})
        self.assertEqual(got, {"a": 1, "b": 3, "c": 4})

    def test_load_answers_file_supports_top_level_and_nested(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            top = base / "top.json"
            nested = base / "nested.json"

            top.write_text(json.dumps({"planning_strictness": 4}), encoding="utf-8")
            nested.write_text(json.dumps({"answers": {"testing_rigor": 2}}), encoding="utf-8")

            a = cli._load_answers_file(top)
            b = cli._load_answers_file(nested)

            self.assertEqual(a["planning_strictness"], 4)
            self.assertEqual(b["testing_rigor"], 2)

    def test_load_answers_file_raises_for_invalid_json(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.json"
            bad.write_text("{not-json}", encoding="utf-8")
            with self.assertRaises(ValueError):
                cli._load_answers_file(bad)

    def test_profile_hybrid_blending_is_deterministic(self):
        survey_payload = {
            "scores": {dim: 3 for dim in cli.PROFILE_DIMENSIONS},
            "evidence": {dim: ["survey"] for dim in cli.PROFILE_DIMENSIONS},
        }
        infer_payload = {
            "scores": {dim: 0 for dim in cli.PROFILE_DIMENSIONS},
            "evidence": {dim: ["infer"] for dim in cli.PROFILE_DIMENSIONS},
        }
        with patch.object(cli, "_profile_survey", return_value=survey_payload), patch.object(
            cli, "_profile_infer", return_value=infer_payload
        ):
            out = cli._profile_hybrid(Path("."), answers={"planning_strictness": 4})

        for dim in cli.PROFILE_DIMENSIONS:
            self.assertEqual(out["scores"][dim], 2)  # round(0.6*3 + 0.4*0)
            self.assertTrue(out["evidence"][dim][0].startswith("hybrid blend:"))

    def test_cognition_hybrid_blending_is_deterministic(self):
        survey_payload = {
            "scores": {dim: 3 for dim in cli.COGNITIVE_DIMENSIONS},
            "evidence": {dim: ["survey"] for dim in cli.COGNITIVE_DIMENSIONS},
        }
        infer_payload = {
            "scores": {dim: 1 for dim in cli.COGNITIVE_DIMENSIONS},
            "evidence": {dim: ["infer"] for dim in cli.COGNITIVE_DIMENSIONS},
        }
        with patch.object(cli, "_cognition_survey", return_value=survey_payload), patch.object(
            cli, "_cognition_infer", return_value=infer_payload
        ):
            out = cli._cognition_hybrid(Path("."), answers={"first_principles_depth": 4})

        for dim in cli.COGNITIVE_DIMENSIONS:
            self.assertEqual(out["scores"][dim], 2)  # round(0.6*3 + 0.4*1)
            self.assertTrue(out["evidence"][dim][0].startswith("hybrid blend:"))

    def test_cognition_infer_scores_are_bounded(self):
        with patch.object(cli, "_git_text", return_value=""), patch.object(cli, "_safe_read_text", return_value=""), patch.object(
            cli, "_project_has_ci", return_value=False
        ):
            out = cli._cognition_infer(Path("."))

        self.assertEqual(set(out["scores"].keys()), set(cli.COGNITIVE_DIMENSIONS))
        for value in out["scores"].values():
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 3)

    def test_setup_command_runs_selected_modes_and_post_steps(self):
        with patch.object(cli, "_resolve_bootstrap_target", return_value=Path(".")), patch.object(
            cli, "_profile_command", return_value=0
        ) as profile_cmd, patch.object(cli, "_cognition_command", return_value=0) as cognition_cmd, patch.object(
            cli, "_sync_user_runtime"
        ) as sync_cmd, patch.object(cli, "_doctor", return_value=0) as doctor_cmd:
            rc = cli._setup_command(
                path_arg=".",
                profile_mode="hybrid",
                cognition_mode="infer",
                write=True,
                overwrite=False,
                do_sync=True,
                do_doctor=True,
                profile_answers={"planning_strictness": 4},
                cognition_answers={"first_principles_depth": 3},
                interactive=False,
            )

        self.assertEqual(rc, 0)
        profile_cmd.assert_called_once_with(
            "hybrid",
            ".",
            write=True,
            overwrite=False,
            answers={"planning_strictness": 4},
        )
        cognition_cmd.assert_called_once_with(
            "infer",
            ".",
            write=True,
            overwrite=False,
            answers={"first_principles_depth": 3},
        )
        sync_cmd.assert_called_once()
        doctor_cmd.assert_called_once()

    def test_setup_command_rejects_invalid_mode(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            rc = cli._setup_command(
                path_arg=".",
                profile_mode="bad",
                cognition_mode="skip",
                write=False,
                overwrite=False,
                do_sync=False,
                do_doctor=False,
                profile_answers=None,
                cognition_answers=None,
                interactive=False,
            )
        self.assertEqual(rc, 1)

    def test_setup_answers_file_override_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fallback = root / "fallback.json"
            profile = root / "profile.json"
            cognition = root / "cognition.json"
            fallback.write_text(json.dumps({"answers": {"planning_strictness": 2, "first_principles_depth": 2}}), encoding="utf-8")
            profile.write_text(json.dumps({"planning_strictness": 4}), encoding="utf-8")
            cognition.write_text(json.dumps({"first_principles_depth": 3}), encoding="utf-8")

            parser = cli.build_parser()
            args = parser.parse_args(
                [
                    "setup",
                    ".",
                    "--profile-mode",
                    "survey",
                    "--cognition-mode",
                    "survey",
                    "--answers-file",
                    str(fallback),
                    "--profile-answers-file",
                    str(profile),
                    "--cognition-answers-file",
                    str(cognition),
                ]
            )

            fallback_answers = cli._load_answers_file(Path(args.answers_file).expanduser())
            profile_answers = fallback_answers
            if args.profile_answers_file:
                profile_answers = cli._load_answers_file(Path(args.profile_answers_file).expanduser())
            cognition_answers = fallback_answers
            if args.cognition_answers_file:
                cognition_answers = cli._load_answers_file(Path(args.cognition_answers_file).expanduser())

            self.assertEqual(profile_answers["planning_strictness"], 4)
            self.assertEqual(cognition_answers["first_principles_depth"], 3)


if __name__ == "__main__":
    unittest.main()
