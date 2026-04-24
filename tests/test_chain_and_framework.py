"""CP7 tests — Pillar 2 hash chain + Pillar 3 substrate.

Covers:

- ``_chain.py`` — canonical serialization, hash determinism, append
  semantics, verify_chain tamper detection, iter_records chain-stop,
  reset_stream archive-and-reseed.
- ``_context_signature.py`` — conservative six-field dict, stable
  across runs, project-tier detection, governance marker detection,
  match-overlap counter.
- ``_pending_contracts.py`` — write + round-trip, expiry, idempotent
  re-write, collision rejection, TTL grace cap, archive rotation.
- ``_framework.py`` — write_protocol / write_deferred_discovery,
  per-stream independence, list filtering, retroactive
  ``upgrade_cp5_prechain`` (upgrade + idempotence + mixed-file
  rejection + atomic backup + post-verify).
- Phase 12 precondition — ``run_audit`` emits ``chain_integrity`` in
  its output; per-stream isolation (framework break does not halt
  episodic audit).
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.hooks import _chain  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _context_signature  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _framework  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _pending_contracts  # pyright: ignore[reportAttributeAccessIssue]


# ---------- _chain.py ----------------------------------------------------


class ChainCanonicalization(unittest.TestCase):
    def test_canonical_bytes_deterministic_across_key_order(self):
        a = {"a": 1, "b": 2, "nested": {"x": 1, "y": 2}}
        b = {"nested": {"y": 2, "x": 1}, "b": 2, "a": 1}
        self.assertEqual(
            _chain.canonical_payload_bytes(a),
            _chain.canonical_payload_bytes(b),
        )

    def test_canonical_bytes_distinguish_different_payloads(self):
        a = {"type": "protocol", "x": 1}
        b = {"type": "protocol", "x": 2}
        self.assertNotEqual(
            _chain.canonical_payload_bytes(a),
            _chain.canonical_payload_bytes(b),
        )

    def test_compute_entry_hash_deterministic(self):
        h1 = _chain.compute_entry_hash(
            "sha256:GENESIS", "2026-04-21T00:00:00+00:00", {"type": "x", "n": 1}
        )
        h2 = _chain.compute_entry_hash(
            "sha256:GENESIS", "2026-04-21T00:00:00+00:00", {"type": "x", "n": 1}
        )
        self.assertEqual(h1, h2)
        self.assertTrue(h1.startswith("sha256:"))

    def test_compute_entry_hash_depends_on_ts(self):
        p = {"type": "x", "n": 1}
        h1 = _chain.compute_entry_hash("sha256:GENESIS", "2026-04-21T00:00:00+00:00", p)
        h2 = _chain.compute_entry_hash("sha256:GENESIS", "2026-04-21T00:00:01+00:00", p)
        self.assertNotEqual(h1, h2)


class ChainAppendAndVerify(unittest.TestCase):
    def test_first_append_uses_genesis_prev(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.jsonl"
            env = _chain.append(p, {"type": "t", "n": 1})
        self.assertEqual(env["prev_hash"], _chain.GENESIS_PREV_HASH)

    def test_second_append_chains_to_first_entry_hash(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.jsonl"
            e1 = _chain.append(p, {"type": "t", "n": 1})
            e2 = _chain.append(p, {"type": "t", "n": 2})
            self.assertEqual(e2["prev_hash"], e1["entry_hash"])
            self.assertNotEqual(e2["entry_hash"], e1["entry_hash"])

    def test_verify_chain_intact_on_clean_writes(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.jsonl"
            for i in range(5):
                _chain.append(p, {"type": "t", "n": i})
            verdict = _chain.verify_chain(p)
        self.assertTrue(verdict.intact)
        self.assertEqual(verdict.total_entries, 5)

    def test_verify_chain_detects_payload_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.jsonl"
            _chain.append(p, {"type": "t", "n": 1})
            _chain.append(p, {"type": "t", "n": 2})
            # Mutate record 1's payload in place. On-disk JSON uses
            # default json.dumps separators (", "/": " with spaces);
            # canonical bytes for hashing use no-space separators.
            text = p.read_text()
            tampered = text.replace('"n": 2', '"n": 99')
            self.assertNotEqual(text, tampered, "tamper replace must actually change text")
            p.write_text(tampered)
            verdict = _chain.verify_chain(p)
        self.assertFalse(verdict.intact)
        self.assertEqual(verdict.break_index, 1)
        assert verdict.reason is not None
        self.assertIn("entry_hash", verdict.reason)

    def test_verify_chain_detects_prev_hash_swap(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.jsonl"
            _chain.append(p, {"type": "t", "n": 1})
            _chain.append(p, {"type": "t", "n": 2})
            lines = p.read_text().splitlines()
            # Swap prev_hash of record 1 to GENESIS — breaks linkage.
            rec = json.loads(lines[1])
            rec["prev_hash"] = _chain.GENESIS_PREV_HASH
            lines[1] = json.dumps(rec, ensure_ascii=False)
            p.write_text("\n".join(lines) + "\n")
            verdict = _chain.verify_chain(p)
        self.assertFalse(verdict.intact)
        self.assertEqual(verdict.break_index, 1)

    def test_verify_empty_file_is_intact(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "empty.jsonl"
            p.write_text("")
            verdict = _chain.verify_chain(p)
        self.assertTrue(verdict.intact)
        self.assertEqual(verdict.total_entries, 0)

    def test_verify_missing_file_is_intact(self):
        verdict = _chain.verify_chain(Path("/nonexistent/path/x.jsonl"))
        self.assertTrue(verdict.intact)
        self.assertEqual(verdict.total_entries, 0)


class ChainIterRecords(unittest.TestCase):
    def test_iter_stops_at_first_break_when_verify_true(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.jsonl"
            _chain.append(p, {"type": "t", "n": 1})
            _chain.append(p, {"type": "t", "n": 2})
            _chain.append(p, {"type": "t", "n": 3})
            lines = p.read_text().splitlines()
            rec = json.loads(lines[1])
            rec["payload"]["n"] = 99
            lines[1] = json.dumps(rec, ensure_ascii=False)
            p.write_text("\n".join(lines) + "\n")
            yielded = list(_chain.iter_records(p, verify=True))
        self.assertEqual(len(yielded), 1)
        self.assertEqual(yielded[0]["payload"]["n"], 1)


class ChainReset(unittest.TestCase):
    def test_reset_archives_existing_file_and_writes_genesis(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.jsonl"
            _chain.append(p, {"type": "t", "n": 1})
            _chain.append(p, {"type": "t", "n": 2})
            prior_head = _chain.verify_chain(p).head_hash
            result = _chain.reset_stream(
                p,
                reason="fresh clone",
                operator_confirmation="I ACKNOWLEDGE CHAIN RESET",
                previous_head=prior_head,
            )
            # Assertions inside the with-block — the tempdir's files
            # vanish on __exit__.
            self.assertEqual(result.status, "archived_and_reset")
            self.assertIsNotNone(result.archived_path)
            assert result.archived_path is not None
            self.assertTrue(result.archived_path.is_file())
            new_verdict = _chain.verify_chain(p)
            self.assertTrue(new_verdict.intact)
            self.assertEqual(new_verdict.total_entries, 1)
            # The genesis record is a chain_reset with prior head.
            first = next(_chain.iter_records(p))
            self.assertEqual(first["payload"]["type"], "chain_reset")
            self.assertEqual(first["payload"]["previous_head"], prior_head)

    def test_reset_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.jsonl"
            with self.assertRaises(_chain.ChainError):
                _chain.reset_stream(p, reason="x", operator_confirmation="")


# ---------- _context_signature.py ----------------------------------------


class ContextSignatureDeterminism(unittest.TestCase):
    def test_same_inputs_produce_identical_dict(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            sig1 = _context_signature.build(
                cwd, "fence_reconstruction", "fence:constraint-removal", "a/b.py:10"
            )
            sig2 = _context_signature.build(
                cwd, "fence_reconstruction", "fence:constraint-removal", "a/b.py:10"
            )
        self.assertEqual(sig1.as_dict(), sig2.as_dict())

    def test_different_blueprints_produce_different_signatures(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            a = _context_signature.build(cwd, "fence_reconstruction", "x")
            b = _context_signature.build(cwd, "generic", "x")
        self.assertNotEqual(a.as_dict(), b.as_dict())

    def test_project_tier_python_detected(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            (cwd / "pyproject.toml").write_text("[build-system]\n")
            # Clear the Layer 3 fingerprint cache so tier detection
            # sees the freshly-seeded file.
            from core.hooks import _grounding  # pyright: ignore[reportAttributeAccessIssue]
            _grounding._clear_cache_for_tests()
            sig = _context_signature.build(cwd, "generic", "git push")
        self.assertEqual(sig.project_tier, "python")

    def test_runtime_marker_governed_detected_via_agents_md(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            (cwd / "AGENTS.md").write_text("# governed\n")
            sig = _context_signature.build(cwd, "generic", "git push")
        self.assertEqual(sig.runtime_marker, "governed")

    def test_runtime_marker_ad_hoc_without_governance_files(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            sig = _context_signature.build(cwd, "generic", "git push")
        self.assertEqual(sig.runtime_marker, "ad_hoc")

    def test_field_overlap_counts_matching_fields(self):
        with tempfile.TemporaryDirectory() as td:
            cwd = Path(td)
            sig = _context_signature.build(cwd, "fence_reconstruction", "rm x")
            stored = {"context_signature": sig.as_dict()}
            self.assertEqual(_context_signature.field_overlap(sig, stored), 6)
            # Different blueprint → one field differs.
            modified = dict(sig.as_dict())
            modified["blueprint"] = "generic"
            stored_mod = {"context_signature": modified}
            self.assertEqual(_context_signature.field_overlap(sig, stored_mod), 5)


# ---------- _pending_contracts.py ----------------------------------------


class EphemeralHome:
    """Point EPISTEME_HOME at a tmp dir for the duration of a test."""
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


class PendingContractsWrite(unittest.TestCase):
    def _trace(self, window: int = 600) -> dict:
        return {
            "command": "grep -n error /tmp/log.txt",
            "or_dashboard": None,
            "or_test": None,
            "window_seconds": window,
            "threshold_observable": "exit_code == 0",
        }

    def _signature(self) -> dict:
        return {
            "project_name": "example",
            "project_tier": "python",
            "blueprint": "generic",
            "op_class": "git push",
            "constraint_head": None,
            "runtime_marker": "governed",
        }

    def test_write_contract_round_trip(self):
        with EphemeralHome():
            res = _pending_contracts.write_contract(
                correlation_id="abc",
                op_label="git push",
                blueprint="generic",
                context_signature=self._signature(),
                verification_trace=self._trace(),
                surface_provenance={"core_question": "x", "disconfirmation": "y"},
            )
            self.assertEqual(res.correlation_id, "abc")
            self.assertTrue(res.entry_hash.startswith("sha256:"))
            active = _pending_contracts.list_active()
            self.assertEqual(len(active), 1)
            self.assertEqual(
                active[0]["payload"]["correlation_id"], "abc"
            )

    def test_window_seconds_required(self):
        with EphemeralHome():
            trace = self._trace()
            trace.pop("window_seconds")
            with self.assertRaises(_pending_contracts.ChainError):
                _pending_contracts.write_contract(
                    correlation_id="abc",
                    op_label="git push",
                    blueprint="generic",
                    context_signature=self._signature(),
                    verification_trace=trace,
                    surface_provenance={"core_question": "x", "disconfirmation": "y"},
                )

    def test_same_correlation_id_identical_payload_idempotent(self):
        with EphemeralHome():
            r1 = _pending_contracts.write_contract(
                correlation_id="abc",
                op_label="git push",
                blueprint="generic",
                context_signature=self._signature(),
                verification_trace=self._trace(),
                surface_provenance={"core_question": "x", "disconfirmation": "y"},
            )
            r2 = _pending_contracts.write_contract(
                correlation_id="abc",
                op_label="git push",
                blueprint="generic",
                context_signature=self._signature(),
                verification_trace=self._trace(),
                surface_provenance={"core_question": "x", "disconfirmation": "y"},
            )
            self.assertEqual(r1.entry_hash, r2.entry_hash)
            self.assertEqual(len(_pending_contracts.list_active()), 1)

    def test_same_correlation_id_different_payload_rejects(self):
        with EphemeralHome():
            _pending_contracts.write_contract(
                correlation_id="abc",
                op_label="git push",
                blueprint="generic",
                context_signature=self._signature(),
                verification_trace=self._trace(),
                surface_provenance={"core_question": "x", "disconfirmation": "y"},
            )
            with self.assertRaises(_pending_contracts.ChainError):
                _pending_contracts.write_contract(
                    correlation_id="abc",
                    op_label="npm publish",  # different!
                    blueprint="generic",
                    context_signature=self._signature(),
                    verification_trace=self._trace(),
                    surface_provenance={"core_question": "x", "disconfirmation": "y"},
                )

    def test_sweep_expired_returns_past_ttl_only(self):
        with EphemeralHome():
            now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
            with patch(
                "core.hooks._pending_contracts.datetime"
            ) as dtmock:
                dtmock.now.return_value = now
                dtmock.side_effect = datetime
                _pending_contracts.write_contract(
                    correlation_id="soon",
                    op_label="git push",
                    blueprint="generic",
                    context_signature=self._signature(),
                    verification_trace=self._trace(window=60),
                    surface_provenance={"core_question": "x", "disconfirmation": "y"},
                    now=now,
                )
                _pending_contracts.write_contract(
                    correlation_id="later",
                    op_label="git push",
                    blueprint="generic",
                    context_signature=self._signature(),
                    verification_trace=self._trace(window=3600),
                    surface_provenance={"core_question": "x", "disconfirmation": "y"},
                    now=now,
                )
            # 120s into the future: `soon` expired, `later` not yet.
            expired = _pending_contracts.sweep_expired(
                now=now + timedelta(seconds=120)
            )
            self.assertEqual(len(expired), 1)
            self.assertEqual(expired[0]["payload"]["correlation_id"], "soon")


# ---------- _framework.py ------------------------------------------------


class FrameworkWrite(unittest.TestCase):
    def test_write_protocol_chained(self):
        with EphemeralHome():
            env1 = _framework.write_protocol(
                {"blueprint": "fence_reconstruction", "synthesized_protocol": "p1"}
            )
            env2 = _framework.write_protocol(
                {"blueprint": "fence_reconstruction", "synthesized_protocol": "p2"}
            )
            self.assertEqual(env2["prev_hash"], env1["entry_hash"])
            self.assertEqual(env1["payload"]["type"], "protocol")

    def test_write_deferred_discovery_separate_chain(self):
        with EphemeralHome():
            _framework.write_protocol(
                {"blueprint": "fence_reconstruction", "synthesized_protocol": "p1"}
            )
            d1 = _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift", "description": "d1"}
            )
            # Deferred-discovery stream is independent: its first record
            # uses GENESIS, regardless of protocol writes.
            self.assertEqual(d1["prev_hash"], _chain.GENESIS_PREV_HASH)

    def test_list_protocols_filters_by_blueprint(self):
        with EphemeralHome():
            _framework.write_protocol(
                {"blueprint": "fence_reconstruction", "synthesized_protocol": "p1"}
            )
            _framework.write_protocol(
                {"blueprint": "axiomatic_judgment", "synthesized_protocol": "p2"}
            )
            fences = _framework.list_protocols(blueprint="fence_reconstruction")
            axs = _framework.list_protocols(blueprint="axiomatic_judgment")
            self.assertEqual(len(fences), 1)
            self.assertEqual(len(axs), 1)

    def test_list_deferred_discoveries_filters_by_flaw_class(self):
        with EphemeralHome():
            _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift", "description": "d1"}
            )
            _framework.write_deferred_discovery(
                {"flaw_classification": "schema-implementation-drift", "description": "d2"}
            )
            drifts = _framework.list_deferred_discoveries(
                flaw_classification="doc-code-drift"
            )
            self.assertEqual(len(drifts), 1)

    def test_type_tag_mismatch_rejected(self):
        with EphemeralHome():
            with self.assertRaises(_framework.ChainError):
                _framework.write_protocol({"type": "deferred_discovery"})

    def test_verify_chains_reports_per_stream(self):
        with EphemeralHome():
            _framework.write_protocol(
                {"blueprint": "fence_reconstruction", "synthesized_protocol": "p1"}
            )
            _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift", "description": "d1"}
            )
            chains = _framework.verify_chains()
            self.assertIn("protocols", chains)
            self.assertIn("deferred_discoveries", chains)
            self.assertTrue(chains["protocols"].intact)
            self.assertTrue(chains["deferred_discoveries"].intact)

    def test_cp_dedup_01_suppresses_identical_deferred_discoveries(self):
        """Event 49 · CP-DEDUP-01 — same (class, desc[:120]) key must
        not write a new chain entry; first write wins, subsequent
        identical payloads return suppressed_duplicate marker."""
        with EphemeralHome():
            env1 = _framework.write_deferred_discovery({
                "flaw_classification": "config-gap",
                "description": "cascade fires on kernel state file edits",
                "observable": "exit 2 emitted on writes",
            })
            self.assertNotIn("suppressed_duplicate", env1)
            env2 = _framework.write_deferred_discovery({
                "flaw_classification": "config-gap",
                "description": "cascade fires on kernel state file edits",
                "observable": "different observable — doesn't disambiguate",
            })
            self.assertTrue(env2.get("suppressed_duplicate"))
            self.assertEqual(
                env2.get("matched_entry_hash"), env1.get("entry_hash")
            )
            records = _framework.list_deferred_discoveries()
            self.assertEqual(len(records), 1)

    def test_cp_dedup_01_allows_distinct_findings(self):
        """Different (class, desc) keys MUST persist independently."""
        with EphemeralHome():
            _framework.write_deferred_discovery({
                "flaw_classification": "config-gap",
                "description": "finding alpha affects startup",
            })
            _framework.write_deferred_discovery({
                "flaw_classification": "schema-implementation-drift",
                "description": "finding alpha affects startup",  # same desc, different class
            })
            _framework.write_deferred_discovery({
                "flaw_classification": "config-gap",
                "description": "finding beta affects teardown",  # same class, different desc
            })
            records = _framework.list_deferred_discoveries()
            self.assertEqual(len(records), 3)

    def test_cp_dedup_01_opt_out_flag_preserved_write_path(self):
        """Callers that need old behavior can pass dedup=False."""
        with EphemeralHome():
            _framework.write_deferred_discovery({
                "flaw_classification": "config-gap",
                "description": "repeatable finding",
            })
            env2 = _framework.write_deferred_discovery(
                {
                    "flaw_classification": "config-gap",
                    "description": "repeatable finding",
                },
                dedup=False,
            )
            self.assertNotIn("suppressed_duplicate", env2)
            records = _framework.list_deferred_discoveries()
            self.assertEqual(len(records), 2)


# ---------- Retroactive CP5 upgrade --------------------------------------


def _write_cp5_prechain_fixture(path: Path, count: int = 3) -> None:
    """Write `count` synthetic CP5 pre-chain records for upgrade tests."""
    recs = [
        {
            "format_version": "cp5-pre-chain",
            "written_at": f"2026-04-21T17:4{i}:00.000000+00:00",
            "correlation_id": f"c{i}",
            "blueprint": "fence_reconstruction",
            "context_signature": f"cs_{i}",
            "synthesized_protocol": f"protocol {i}",
            "prev_hash": None,
            "entry_hash": None,
        }
        for i in range(count)
    ]
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n")


class Cp5RetroactiveUpgrade(unittest.TestCase):
    def test_upgrade_wraps_prechain_records_in_cp7_envelope(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "protocols.jsonl"
            _write_cp5_prechain_fixture(p, count=3)
            result = _framework.upgrade_cp5_prechain(path=p)
            # Assertions inside the with-block — tempdir cleanup
            # on __exit__ removes the backup file too.
            self.assertEqual(result.status, "upgraded")
            self.assertEqual(result.entries_processed, 3)
            self.assertIsNotNone(result.backup_path)
            assert result.backup_path is not None
            self.assertTrue(result.backup_path.is_file())

    def test_upgrade_preserves_original_timestamps_and_fields(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "protocols.jsonl"
            _write_cp5_prechain_fixture(p, count=2)
            _framework.upgrade_cp5_prechain(path=p)
            records = list(_chain.iter_records(p))
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["ts"], "2026-04-21T17:40:00.000000+00:00")
            self.assertEqual(records[0]["payload"]["correlation_id"], "c0")
            self.assertEqual(
                records[0]["payload"]["synthesized_protocol"], "protocol 0"
            )
            self.assertEqual(
                records[0]["payload"]["legacy_format"], "cp5-pre-chain"
            )

    def test_upgrade_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "protocols.jsonl"
            _write_cp5_prechain_fixture(p, count=3)
            _framework.upgrade_cp5_prechain(path=p)
            bytes_after_first = p.read_bytes()
            result2 = _framework.upgrade_cp5_prechain(path=p)
            bytes_after_second = p.read_bytes()
        self.assertEqual(result2.status, "already_upgraded")
        self.assertEqual(bytes_after_first, bytes_after_second)

    def test_upgrade_rejects_mixed_prechain_and_chained(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "protocols.jsonl"
            _write_cp5_prechain_fixture(p, count=2)
            _framework.upgrade_cp5_prechain(path=p)
            # Append a raw cp5-pre-chain record on top of the upgraded file.
            with open(p, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "format_version": "cp5-pre-chain",
                    "written_at": "2026-04-21T17:50:00.000000+00:00",
                    "correlation_id": "cX",
                    "blueprint": "fence_reconstruction",
                    "context_signature": "cs_X",
                    "synthesized_protocol": "rogue",
                    "prev_hash": None,
                    "entry_hash": None,
                }) + "\n")
            with self.assertRaises(_framework.UpgradeError):
                _framework.upgrade_cp5_prechain(path=p)

    def test_upgrade_missing_file_returns_missing_status(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "does_not_exist.jsonl"
            result = _framework.upgrade_cp5_prechain(path=p)
        self.assertEqual(result.status, "missing")
        self.assertEqual(result.entries_processed, 0)

    def test_upgrade_rejects_missing_written_at_field(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "protocols.jsonl"
            rec = {
                "format_version": "cp5-pre-chain",
                "correlation_id": "c0",
                "blueprint": "fence_reconstruction",
                "synthesized_protocol": "x",
                "prev_hash": None,
                "entry_hash": None,
            }
            p.write_text(json.dumps(rec) + "\n")
            with self.assertRaises(_framework.UpgradeError):
                _framework.upgrade_cp5_prechain(path=p)


# ---------- Phase 12 precondition integration ---------------------------


class Phase12ChainIntegrity(unittest.TestCase):
    """The audit output gains a ``chain_integrity`` field reporting
    per-stream verdict. Per-stream isolation — a framework break does
    NOT halt episodic-derived axis verdicts."""

    def test_audit_emits_chain_integrity_field(self):
        from episteme._profile_audit import run_audit  # pyright: ignore[reportMissingImports]
        with EphemeralHome():
            result = run_audit(since_days=1)
        self.assertIn("chain_integrity", result)
        self.assertIn("protocols", result["chain_integrity"])
        self.assertIn("deferred_discoveries", result["chain_integrity"])
        self.assertIn("pending_contracts", result["chain_integrity"])

    def test_audit_proceeds_when_all_chains_intact(self):
        from episteme._profile_audit import run_audit  # pyright: ignore[reportMissingImports]
        with EphemeralHome():
            _framework.write_protocol(
                {"blueprint": "fence_reconstruction", "synthesized_protocol": "p1"}
            )
            result = run_audit(since_days=1)
        self.assertTrue(result["chain_integrity"]["protocols"]["intact"])
        # Axis verdicts still populated (insufficient_evidence in
        # cold-start; the point is the audit didn't fail).
        self.assertIsInstance(result["axes"], list)
        self.assertGreater(len(result["axes"]), 0)

    def test_audit_reports_break_when_chain_tampered(self):
        from episteme._profile_audit import run_audit  # pyright: ignore[reportMissingImports]
        with EphemeralHome():
            _framework.write_protocol(
                {"blueprint": "fence_reconstruction", "synthesized_protocol": "p1"}
            )
            _framework.write_protocol(
                {"blueprint": "fence_reconstruction", "synthesized_protocol": "p2"}
            )
            # Tamper with the protocols chain.
            protocols_path = Path(os.environ["EPISTEME_HOME"]) / "framework" / "protocols.jsonl"
            text = protocols_path.read_text()
            tampered = text.replace('"p2"', '"pX"')
            protocols_path.write_text(tampered)
            result = run_audit(since_days=1)
        self.assertFalse(result["chain_integrity"]["protocols"]["intact"])
        # Per-stream isolation: other streams unaffected.
        self.assertTrue(result["chain_integrity"]["deferred_discoveries"]["intact"])
        # Axis verdicts still populated.
        self.assertIsInstance(result["axes"], list)


if __name__ == "__main__":
    unittest.main()
