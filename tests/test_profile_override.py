"""Tests for CP-CONTEXT-AWARE-PROFILE-OVERRIDE-01 (Event 85) — per-project
profile override module.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from episteme import _profile_override as po


class ValidateAxisNameTests(unittest.TestCase):
    def test_valid_axis_accepted(self):
        po.validate_axis_name("testing_rigor")

    def test_invalid_axis_rejected(self):
        with self.assertRaises(ValueError):
            po.validate_axis_name("not_an_axis")


class ValidateRationaleTests(unittest.TestCase):
    def test_short_rejected(self):
        with self.assertRaises(ValueError):
            po.validate_rationale("short")

    def test_lazy_rejected(self):
        with self.assertRaises(ValueError):
            po.validate_rationale("n/a")

    def test_substantive_accepted(self):
        po.validate_rationale("Production critical-path; max test discipline.")


class ReadOverrideTests(unittest.TestCase):
    def test_no_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(po.read_project_override(Path(td)), {})

    def test_round_trip_write_then_read(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            po.write_project_override(
                p, "testing_rigor", 5,
                rationale="Production critical-path; max test discipline.",
                evidence_refs=["Event 65"],
            )
            overrides = po.read_project_override(p)
            self.assertIn("testing_rigor", overrides)
            self.assertEqual(overrides["testing_rigor"]["value"], 5)


class ResolveAxisTests(unittest.TestCase):
    def test_resolve_falls_back_to_global(self):
        with tempfile.TemporaryDirectory() as td:
            result = po.resolve_axis("testing_rigor", Path(td), global_value=3)
            self.assertEqual(result["source"], "global")
            self.assertEqual(result["value"], 3)

    def test_resolve_falls_back_to_kernel_default(self):
        with tempfile.TemporaryDirectory() as td:
            result = po.resolve_axis("testing_rigor", Path(td), global_value=None)
            self.assertEqual(result["source"], "kernel_default")
            self.assertIsNone(result["value"])

    def test_resolve_uses_project_override_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            po.write_project_override(
                p, "testing_rigor", 5,
                rationale="Production critical-path; max test discipline.",
            )
            result = po.resolve_axis("testing_rigor", p, global_value=3)
            self.assertEqual(result["source"], "project_override")
            self.assertEqual(result["value"], 5)
            self.assertIn("rationale", result)


class WriteOverrideTests(unittest.TestCase):
    def test_write_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            path = po.write_project_override(
                p, "risk_tolerance", 1,
                rationale="Production migration; lowest-risk posture.",
            )
            self.assertTrue(path.exists())

    def test_write_invalid_rationale_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                po.write_project_override(
                    Path(td), "risk_tolerance", 1, rationale="tbd",
                )

    def test_write_invalid_axis_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                po.write_project_override(
                    Path(td), "fake_axis", 1,
                    rationale="Substantive rationale text here.",
                )

    def test_overwrite_existing_axis(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            po.write_project_override(
                p, "testing_rigor", 3,
                rationale="Initial substantive rationale text.",
            )
            po.write_project_override(
                p, "testing_rigor", 5,
                rationale="Updated substantive rationale text.",
            )
            overrides = po.read_project_override(p)
            self.assertEqual(overrides["testing_rigor"]["value"], 5)


class RemoveOverrideTests(unittest.TestCase):
    def test_remove_returns_true_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            po.write_project_override(
                p, "testing_rigor", 5,
                rationale="Production critical-path; max test discipline.",
            )
            self.assertTrue(po.remove_project_override(p, "testing_rigor"))
            self.assertNotIn("testing_rigor", po.read_project_override(p))

    def test_remove_returns_false_when_absent(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(po.remove_project_override(Path(td), "testing_rigor"))


if __name__ == "__main__":
    unittest.main()
