"""Tests for CP-OPERATOR-COGNITIVE-BUDGET-01 (Event 88) — operator
approval-time history hash-chained stream + D11 fatigue detector.

Coverage:
- blueprint validation (must be one of declared blueprint slugs)
- op_class validation (must be one of declared classes)
- elapsed_seconds validation (must be ≥ 0; bool / non-numeric rejected)
- correlation_id validation (must be non-empty string)
- reason validation (lazy-token + min-char rejection)
- record_approval writes valid cp7-chained-v1 envelope
- walk_approvals returns chronological observations + filters
- detect_fatigue threshold logic — both p50 and sub-second-rate triggers
- summarize stats shape
- chain integrity across multiple writes
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from episteme import _cognitive_budget as cb


class ValidateBlueprintTests(unittest.TestCase):
    def test_valid_blueprint_accepted(self):
        for bp in cb.VALID_BLUEPRINTS:
            cb.validate_blueprint(bp)
        # Should NOT raise

    def test_unknown_blueprint_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            cb.validate_blueprint("not_a_real_blueprint")
        self.assertIn("unknown blueprint", str(ctx.exception))

    def test_empty_blueprint_rejected(self):
        with self.assertRaises(ValueError):
            cb.validate_blueprint("")
        with self.assertRaises(ValueError):
            cb.validate_blueprint("   ")

    def test_non_string_blueprint_rejected(self):
        with self.assertRaises(ValueError):
            cb.validate_blueprint(None)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            cb.validate_blueprint(123)  # type: ignore[arg-type]


class ValidateOpClassTests(unittest.TestCase):
    def test_valid_op_class_accepted(self):
        for oc in cb.VALID_OP_CLASSES:
            cb.validate_op_class(oc)

    def test_unknown_op_class_rejected(self):
        with self.assertRaises(ValueError):
            cb.validate_op_class("xterm")

    def test_empty_op_class_rejected(self):
        with self.assertRaises(ValueError):
            cb.validate_op_class("")


class ValidateElapsedSecondsTests(unittest.TestCase):
    def test_zero_accepted(self):
        cb.validate_elapsed_seconds(0)
        cb.validate_elapsed_seconds(0.0)

    def test_positive_accepted(self):
        cb.validate_elapsed_seconds(0.5)
        cb.validate_elapsed_seconds(120)

    def test_negative_rejected(self):
        with self.assertRaises(ValueError):
            cb.validate_elapsed_seconds(-0.001)

    def test_bool_rejected(self):
        with self.assertRaises(ValueError):
            cb.validate_elapsed_seconds(True)  # type: ignore[arg-type]

    def test_non_numeric_rejected(self):
        with self.assertRaises(ValueError):
            cb.validate_elapsed_seconds("0.5")  # type: ignore[arg-type]


class ValidateCorrelationIdTests(unittest.TestCase):
    def test_valid_correlation_id_accepted(self):
        cb.validate_correlation_id("h_abc123")

    def test_empty_correlation_id_rejected(self):
        with self.assertRaises(ValueError):
            cb.validate_correlation_id("")
        with self.assertRaises(ValueError):
            cb.validate_correlation_id("   ")

    def test_non_string_correlation_id_rejected(self):
        with self.assertRaises(ValueError):
            cb.validate_correlation_id(None)  # type: ignore[arg-type]


class ValidateReasonTests(unittest.TestCase):
    def test_lazy_token_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            cb.validate_reason("n/a")
        self.assertIn("lazy-token", str(ctx.exception))

    def test_lazy_token_korean_rejected(self):
        with self.assertRaises(ValueError):
            cb.validate_reason("해당 없음")

    def test_short_reason_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            cb.validate_reason("too short")
        self.assertIn("at least", str(ctx.exception))

    def test_substantive_reason_accepted(self):
        cb.validate_reason("Smoke-test approval observation for ablation.")


class RecordApprovalTests(unittest.TestCase):
    def test_writes_valid_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            envelope = cb.record_approval(
                "h_abc123",
                "fence_reconstruction",
                "edit",
                0.42,
                "Manual record from tests for envelope shape verification.",
                recorder="testuser",
                reflective_dir=Path(td),
            )
            self.assertEqual(envelope["schema_version"], "cp7-chained-v1")
            payload = envelope["payload"]
            self.assertEqual(payload["type"], "approval_record")
            self.assertEqual(payload["correlation_id"], "h_abc123")
            self.assertEqual(payload["blueprint"], "fence_reconstruction")
            self.assertEqual(payload["op_class"], "edit")
            self.assertEqual(payload["elapsed_seconds"], 0.42)
            self.assertEqual(payload["recorder"], "testuser")
            self.assertIn("recorded_at", payload)
            self.assertTrue(envelope["entry_hash"].startswith("sha256:"))

    def test_invalid_blueprint_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                cb.record_approval(
                    "h_x", "fake_blueprint", "edit", 0.5,
                    "Substantive reason for the approval observation.",
                    reflective_dir=Path(td),
                )

    def test_invalid_op_class_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                cb.record_approval(
                    "h_x", "fence_reconstruction", "wat", 0.5,
                    "Substantive reason for the approval observation.",
                    reflective_dir=Path(td),
                )

    def test_negative_elapsed_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                cb.record_approval(
                    "h_x", "fence_reconstruction", "edit", -0.1,
                    "Substantive reason for the approval observation.",
                    reflective_dir=Path(td),
                )

    def test_lazy_reason_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                cb.record_approval(
                    "h_x", "fence_reconstruction", "edit", 0.5, "tbd",
                    reflective_dir=Path(td),
                )


class WalkApprovalsTests(unittest.TestCase):
    def test_walk_empty_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(cb.walk_approvals(reflective_dir=Path(td)), [])

    def test_walk_returns_chronological(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            base = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)
            for i in range(3):
                cb.record_approval(
                    f"h_{i}", "fence_reconstruction", "edit", 0.1 * (i + 1),
                    f"Observation entry {i} for chronological ordering check.",
                    recorder="t",
                    reflective_dir=d,
                    _now=base + timedelta(seconds=i),
                )
            entries = cb.walk_approvals(reflective_dir=d)
            self.assertEqual(len(entries), 3)
            self.assertEqual(entries[0]["payload"]["correlation_id"], "h_0")
            self.assertEqual(entries[2]["payload"]["correlation_id"], "h_2")

    def test_walk_filters_by_blueprint(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            cb.record_approval(
                "h_a", "fence_reconstruction", "edit", 0.5,
                "Fence reconstruction observation for filter test.",
                recorder="t", reflective_dir=d,
            )
            cb.record_approval(
                "h_b", "axiomatic_judgment", "edit", 0.5,
                "Axiomatic judgment observation for filter test.",
                recorder="t", reflective_dir=d,
            )
            fence = cb.walk_approvals(blueprint="fence_reconstruction", reflective_dir=d)
            self.assertEqual(len(fence), 1)
            self.assertEqual(fence[0]["payload"]["correlation_id"], "h_a")

    def test_walk_filters_by_op_class(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            cb.record_approval(
                "h_a", "fence_reconstruction", "edit", 0.5,
                "Edit observation for op_class filter test.",
                recorder="t", reflective_dir=d,
            )
            cb.record_approval(
                "h_b", "fence_reconstruction", "bash", 0.5,
                "Bash observation for op_class filter test.",
                recorder="t", reflective_dir=d,
            )
            edits = cb.walk_approvals(op_class="edit", reflective_dir=d)
            self.assertEqual(len(edits), 1)
            self.assertEqual(edits[0]["payload"]["correlation_id"], "h_a")

    def test_walk_limit_returns_last_n(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            base = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)
            for i in range(5):
                cb.record_approval(
                    f"h_{i}", "fence_reconstruction", "edit", 0.1,
                    f"Observation {i} for limit test (must be ≥ 15 chars).",
                    recorder="t", reflective_dir=d,
                    _now=base + timedelta(seconds=i),
                )
            tail = cb.walk_approvals(limit=2, reflective_dir=d)
            self.assertEqual(len(tail), 2)
            self.assertEqual(tail[0]["payload"]["correlation_id"], "h_3")
            self.assertEqual(tail[1]["payload"]["correlation_id"], "h_4")


class ListBlueprintsWithHistoryTests(unittest.TestCase):
    def test_returns_recorded_blueprints(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            cb.record_approval(
                "h_a", "fence_reconstruction", "edit", 0.5,
                "Fence reconstruction observation for list test.",
                recorder="t", reflective_dir=d,
            )
            cb.record_approval(
                "h_b", "cascade_escalation", "cascade", 1.0,
                "Cascade escalation observation for list test.",
                recorder="t", reflective_dir=d,
            )
            bps = cb.list_blueprints_with_history(reflective_dir=d)
            self.assertEqual(bps, {"fence_reconstruction", "cascade_escalation"})

    def test_empty_when_no_history(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(cb.list_blueprints_with_history(reflective_dir=Path(td)), set())


class DetectFatigueTests(unittest.TestCase):
    def test_no_history_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(cb.detect_fatigue(reflective_dir=Path(td)))

    def test_p50_threshold_fires_signal(self):
        """20 sub-second observations → p50 ≈ 0.5s < 1.5s threshold → fires."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            base = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)
            for i in range(20):
                cb.record_approval(
                    f"h_{i}", "fence_reconstruction", "edit", 0.5,
                    f"Sub-second observation {i} for p50-fires fatigue test.",
                    recorder="t", reflective_dir=d,
                    _now=base + timedelta(seconds=i),
                )
            sig = cb.detect_fatigue(reflective_dir=d)
            self.assertIsNotNone(sig)
            assert sig is not None  # for type-checker
            self.assertEqual(sig["signal"], "attention_bottleneck")
            self.assertIn("p50_below_threshold", sig["triggers"])
            self.assertIn("sub_second_rate_above_threshold", sig["triggers"])
            self.assertEqual(sig["sample_size"], 20)
            self.assertAlmostEqual(sig["p50"], 0.5, places=3)
            self.assertAlmostEqual(sig["sub_second_rate"], 1.0, places=3)

    def test_slow_pattern_no_signal(self):
        """20 slow approvals (3s each) → p50 = 3s > 1.5s; sub_second_rate = 0 → no signal."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            base = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)
            for i in range(20):
                cb.record_approval(
                    f"h_{i}", "fence_reconstruction", "edit", 3.0,
                    f"Slow approval observation {i} for no-fatigue path test.",
                    recorder="t", reflective_dir=d,
                    _now=base + timedelta(seconds=i),
                )
            sig = cb.detect_fatigue(reflective_dir=d)
            self.assertIsNone(sig)

    def test_sub_second_rate_only_fires(self):
        """Mix: 11 sub-second + 9 slow → p50 ≈ 0.5s (still below threshold) AND
        sub_second_rate = 0.55 > 0.5 → both triggers fire. Test that it
        fires under the rate condition specifically by checking trigger list."""
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            base = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)
            for i in range(11):
                cb.record_approval(
                    f"h_fast_{i}", "fence_reconstruction", "edit", 0.5,
                    f"Fast observation {i} for mixed-pattern test.",
                    recorder="t", reflective_dir=d,
                    _now=base + timedelta(seconds=i),
                )
            for i in range(9):
                cb.record_approval(
                    f"h_slow_{i}", "fence_reconstruction", "edit", 5.0,
                    f"Slow observation {i} for mixed-pattern test.",
                    recorder="t", reflective_dir=d,
                    _now=base + timedelta(seconds=20 + i),
                )
            sig = cb.detect_fatigue(reflective_dir=d)
            self.assertIsNotNone(sig)
            assert sig is not None
            self.assertIn("sub_second_rate_above_threshold", sig["triggers"])

    def test_invalid_window_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                cb.detect_fatigue(window=0, reflective_dir=Path(td))

    def test_invalid_threshold_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                cb.detect_fatigue(p50_threshold_seconds=-1, reflective_dir=Path(td))
            with self.assertRaises(ValueError):
                cb.detect_fatigue(sub_second_rate_threshold=1.5, reflective_dir=Path(td))


class SummarizeTests(unittest.TestCase):
    def test_empty_summary(self):
        with tempfile.TemporaryDirectory() as td:
            summ = cb.summarize(reflective_dir=Path(td))
            self.assertEqual(summ["count"], 0)
            self.assertIsNone(summ["p50"])
            self.assertEqual(summ["by_blueprint"], {})
            self.assertIsNone(summ["fatigue"])

    def test_summary_shape(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for i in range(3):
                cb.record_approval(
                    f"h_{i}", "fence_reconstruction", "edit", 1.0,
                    f"Observation {i} for summary shape test (≥ 15 chars).",
                    recorder="t", reflective_dir=d,
                )
            summ = cb.summarize(reflective_dir=d)
            self.assertEqual(summ["count"], 3)
            self.assertAlmostEqual(summ["p50"], 1.0, places=3)
            self.assertEqual(summ["by_blueprint"], {"fence_reconstruction": 3})


class ChainIntegrityTests(unittest.TestCase):
    def test_chain_intact_after_writes(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for i in range(5):
                cb.record_approval(
                    f"h_{i}", "fence_reconstruction", "edit", 0.5,
                    f"Chain integrity test observation {i}.",
                    recorder="t", reflective_dir=d,
                )
            verdict = cb.verify_chain(reflective_dir=d)
            self.assertTrue(verdict.intact)
            self.assertEqual(verdict.total_entries, 5)


class LoadThresholdsTests(unittest.TestCase):
    def test_defaults_when_no_override(self):
        with tempfile.TemporaryDirectory() as td:
            window, p50, rate = cb.load_thresholds(Path(td))
            self.assertEqual(window, cb.DEFAULT_WINDOW)
            self.assertEqual(p50, cb.DEFAULT_P50_THRESHOLD_SECONDS)
            self.assertEqual(rate, cb.DEFAULT_SUB_SECOND_RATE_THRESHOLD)

    def test_override_file_parsed(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            ep = cwd / ".episteme"
            ep.mkdir()
            (ep / "cognitive_budget_thresholds").write_text(
                "window=50\np50=2.0\nsub_second_rate=0.3\n"
            )
            window, p50, rate = cb.load_thresholds(cwd)
            self.assertEqual(window, 50)
            self.assertEqual(p50, 2.0)
            self.assertEqual(rate, 0.3)

    def test_malformed_falls_back(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            ep = cwd / ".episteme"
            ep.mkdir()
            (ep / "cognitive_budget_thresholds").write_text("not parseable\n")
            window, p50, rate = cb.load_thresholds(cwd)
            self.assertEqual(window, cb.DEFAULT_WINDOW)


if __name__ == "__main__":
    unittest.main()
