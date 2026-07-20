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

    # ---- CP-DEDUP-01 one-time compaction (compact already-bloated store) ----

    def _dd_path(self) -> Path:
        return _framework._deferred_discoveries_path()

    def _seed_dup(self, payload: dict) -> dict:
        """Write a deferred_discovery bypassing the write-time dedup gate
        (dedup=False) so the store can be deliberately bloated the way the
        pre-Event-49 framework writer did."""
        return _framework.write_deferred_discovery(payload, dedup=False)

    def test_compact_collapses_open_duplicates_first_wins(self):
        with EphemeralHome():
            first = self._seed_dup({
                "flaw_classification": "config-gap",
                "description": "cascade fires on kernel state file edits",
                "observable": "first occurrence",
            })
            self._seed_dup({
                "flaw_classification": "config-gap",
                "description": "cascade fires on kernel state file edits",
                "observable": "second — later duplicate",
            })
            self._seed_dup({
                "flaw_classification": "config-gap",
                "description": "cascade fires on kernel state file edits",
                "observable": "third — later duplicate",
            })
            self.assertEqual(len(_framework.list_deferred_discoveries()), 3)

            result = _framework.compact_deferred_discoveries()
            self.assertEqual(result.status, "compacted")
            self.assertEqual(result.total_before, 3)
            self.assertEqual(result.total_after, 1)
            self.assertEqual(result.removed, 2)
            self.assertIsNotNone(result.backup_path)

            records = _framework.list_deferred_discoveries()
            self.assertEqual(len(records), 1)
            # First-wins: the surviving payload is the FIRST occurrence.
            self.assertEqual(
                records[0]["payload"]["observable"], "first occurrence"
            )
            # The first envelope's ts is preserved byte-stable.
            self.assertEqual(records[0]["ts"], first["ts"])

    def test_compact_preserves_chain_integrity(self):
        with EphemeralHome():
            for i in range(4):
                self._seed_dup({
                    "flaw_classification": "config-gap",
                    "description": "identical bloated finding",
                    "observable": f"copy {i}",
                })
            _framework.compact_deferred_discoveries()
            verdict = _chain.verify_chain(self._dd_path())
            self.assertTrue(verdict.intact)
            self.assertIsNone(verdict.break_index)
            self.assertEqual(verdict.total_entries, 1)

    def test_compact_is_idempotent_no_new_backup(self):
        with EphemeralHome():
            for i in range(3):
                self._seed_dup({
                    "flaw_classification": "config-gap",
                    "description": "identical bloated finding",
                    "observable": f"copy {i}",
                })
            r1 = _framework.compact_deferred_discoveries()
            self.assertEqual(r1.status, "compacted")
            baks_after_first = sorted(self._dd_path().parent.glob("*.compact-*.bak"))
            self.assertEqual(len(baks_after_first), 1)

            r2 = _framework.compact_deferred_discoveries()
            self.assertEqual(r2.status, "noop")
            self.assertEqual(r2.removed, 0)
            self.assertEqual(r2.total_before, r2.total_after)
            self.assertIsNone(r2.backup_path)
            # No second backup written on the noop run.
            baks_after_second = sorted(self._dd_path().parent.glob("*.compact-*.bak"))
            self.assertEqual(len(baks_after_second), 1)

    def test_compact_preserves_distinct_findings_and_order(self):
        with EphemeralHome():
            self._seed_dup({"flaw_classification": "config-gap", "description": "alpha"})
            self._seed_dup({"flaw_classification": "config-gap", "description": "alpha"})  # dup
            self._seed_dup({"flaw_classification": "schema-drift", "description": "beta"})
            self._seed_dup({"flaw_classification": "config-gap", "description": "gamma"})
            self._seed_dup({"flaw_classification": "schema-drift", "description": "beta"})  # dup

            result = _framework.compact_deferred_discoveries()
            self.assertEqual(result.status, "compacted")
            self.assertEqual(result.removed, 2)

            records = _framework.list_deferred_discoveries()
            descs = [r["payload"]["description"] for r in records]
            # Distinct findings preserved in original file order, first-wins.
            self.assertEqual(descs, ["alpha", "beta", "gamma"])

    def test_compact_keeps_non_open_and_non_dd_records_verbatim(self):
        with EphemeralHome():
            # A non-deferred_discovery payload sharing the chain (protocols
            # use a separate file, so seed a resolved dd + a foreign-type
            # record directly into the dd stream to prove both are kept).
            self._seed_dup({
                "flaw_classification": "config-gap",
                "description": "shared key finding",
                "status": "resolved",   # non-open — must be kept verbatim
            })
            self._seed_dup({
                "flaw_classification": "config-gap",
                "description": "shared key finding",
                "status": "pending",
            })
            self._seed_dup({
                "flaw_classification": "config-gap",
                "description": "shared key finding",
                "status": "pending",   # open dup of the pending one — dropped
            })
            # A foreign-type record in the same stream (e.g. a chain_reset
            # genesis) must be preserved regardless of dedup key.
            _chain.append(self._dd_path(), {
                "type": "chain_reset",
                "reason": "x",
            })

            before = _framework.list_deferred_discoveries()
            # 2 dd survive the dd-only listing filter (resolved + pending);
            # the dropped one is the 2nd pending.
            result = _framework.compact_deferred_discoveries()
            self.assertEqual(result.status, "compacted")
            # total_before counts every envelope (3 dd + 1 chain_reset).
            self.assertEqual(result.total_before, 4)
            # Only one open pending dup removed.
            self.assertEqual(result.removed, 1)
            self.assertEqual(result.total_after, 3)

            # Both the resolved dd and the foreign chain_reset survive.
            verdict = _chain.verify_chain(self._dd_path())
            self.assertTrue(verdict.intact)
            kept_payloads = [
                rec["payload"]
                for rec in _chain.iter_records(self._dd_path())
            ]
            statuses = [
                p.get("status") for p in kept_payloads
                if p.get("type") == "deferred_discovery"
            ]
            self.assertIn("resolved", statuses)
            self.assertEqual(statuses.count("pending"), 1)
            self.assertTrue(
                any(p.get("type") == "chain_reset" for p in kept_payloads)
            )
            self.assertGreaterEqual(len(before), 1)

    def test_compact_aborts_on_corrupt_line_leaves_file_unchanged(self):
        with EphemeralHome():
            self._seed_dup({"flaw_classification": "config-gap", "description": "alpha"})
            self._seed_dup({"flaw_classification": "config-gap", "description": "alpha"})
            path = self._dd_path()
            # Corrupt the file with a non-JSON line.
            original = path.read_bytes()
            path.write_bytes(original + b"this-is-not-json\n")
            corrupted = path.read_bytes()

            with self.assertRaises(_framework.ChainError):
                _framework.compact_deferred_discoveries()
            # File byte-unchanged: no partial rewrite, no backup.
            self.assertEqual(path.read_bytes(), corrupted)
            self.assertEqual(
                len(sorted(path.parent.glob("*.compact-*.bak"))), 0
            )

    def test_compact_empty_file_returns_empty_status(self):
        with EphemeralHome():
            path = self._dd_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("")
            result = _framework.compact_deferred_discoveries()
            self.assertEqual(result.status, "empty")
            self.assertEqual(result.total_before, 0)
            self.assertIsNone(result.backup_path)

    def test_compact_missing_file_returns_missing_status(self):
        with EphemeralHome():
            # No file ever written.
            result = _framework.compact_deferred_discoveries()
            self.assertEqual(result.status, "missing")
            self.assertEqual(result.total_before, 0)
            self.assertIsNone(result.backup_path)

    def test_compact_dry_run_does_not_write(self):
        with EphemeralHome():
            for i in range(3):
                self._seed_dup({
                    "flaw_classification": "config-gap",
                    "description": "identical bloated finding",
                    "observable": f"copy {i}",
                })
            path = self._dd_path()
            before = path.read_bytes()
            result = _framework.compact_deferred_discoveries(dry_run=True)
            self.assertEqual(result.status, "compacted")
            self.assertEqual(result.removed, 2)
            self.assertIsNone(result.backup_path)
            # File untouched + no backup on dry-run.
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(
                len(sorted(path.parent.glob("*.compact-*.bak"))), 0
            )

    def test_compact_refuses_tampered_input_chain(self):
        # Event 136 review must-fix: a GENESIS rebuild would silently "heal"
        # a pre-existing break/tamper into a verified chain, laundering a
        # quarantined record into trusted state. Compaction MUST refuse a
        # non-intact input rather than launder it.
        with EphemeralHome():
            # Seed an open duplicate pair so removed > 0 (forces the rewrite
            # path that would otherwise launder).
            for i in range(2):
                self._seed_dup({
                    "flaw_classification": "config-gap",
                    "description": "duplicate finding",
                    "observable": f"copy {i}",
                })
            path = self._dd_path()
            lines = path.read_text(encoding="utf-8").splitlines()
            # Tamper the LAST record's payload in place, leaving its stored
            # entry_hash stale → chain break at that index.
            last = json.loads(lines[-1])
            last["payload"]["observable"] = "TAMPERED — entry_hash now stale"
            lines[-1] = json.dumps(last)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            before = path.read_bytes()

            # Confirm the input is genuinely broken first.
            self.assertFalse(_chain.verify_chain(path).intact)

            # Compaction must REFUSE (raise), not launder.
            with self.assertRaises(_framework.ChainError):
                _framework.compact_deferred_discoveries()
            # Dry-run must refuse identically (cannot safely preview).
            with self.assertRaises(_framework.ChainError):
                _framework.compact_deferred_discoveries(dry_run=True)
            # File untouched + no backup written on refusal.
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(
                len(sorted(path.parent.glob("*.compact-*.bak"))), 0
            )


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


class DeferredCapRelief(unittest.TestCase):
    """Event 158 — the deferred-discovery queue gets the Event 157
    drain: open-cap with at-cap expiry relief (terminal chained
    ``deferred_discovery_expiry`` records), a decline counter, and a
    truthful reset on operator verdict."""

    def test_at_cap_declines_and_bumps_counter(self):
        with EphemeralHome():
            _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "fresh finding one",
                 "logged_at": datetime.now(timezone.utc).isoformat()}
            )
            res = _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "distinct second finding",
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=1,
            )
            self.assertTrue(res.get("declined_at_cap"))
            self.assertEqual(len(_framework.open_deferred_discoveries()), 1)
            self.assertEqual(
                _framework.read_deferred_skip_counter()["skipped_count"], 1
            )

    def test_at_cap_stale_relief_then_appends(self):
        with EphemeralHome():
            old = (
                datetime.now(timezone.utc) - timedelta(days=31)
            ).isoformat()
            _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "ancient finding", "logged_at": old}
            )
            res = _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "distinct new finding",
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=1,
            )
            self.assertIn("entry_hash", res)
            open_now = _framework.open_deferred_discoveries()
            self.assertEqual(len(open_now), 1)
            self.assertEqual(
                open_now[0]["payload"]["description"], "distinct new finding"
            )
            chains = _framework.verify_chains()
            self.assertTrue(chains["deferred_discoveries"].intact)

    def test_expiry_uses_envelope_ts_when_logged_at_missing(self):
        # Entries without a payload stamp age by the envelope's append
        # ts (machine-written, always present) — a young entry without
        # logged_at must NOT be expired.
        with EphemeralHome():
            _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "young unstamped finding"}
            )
            res = _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "distinct newer finding",
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=1,
            )
            self.assertTrue(res.get("declined_at_cap"))
            self.assertEqual(len(_framework.open_deferred_discoveries()), 1)

    def test_operator_verdict_supersedes_expiry(self):
        # Event 158 review — cap relief must not permanently block a
        # real disposition (the Event 152 `accepted` verdict names the
        # cost of ignorance; a machine expiry cannot). Mirrors the
        # Event 157 spot-check semantics.
        with EphemeralHome():
            old = (
                datetime.now(timezone.utc) - timedelta(days=31)
            ).isoformat()
            env = _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "ancient finding", "logged_at": old}
            )
            expired_hash = env["entry_hash"]
            _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "distinct new finding",
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=1,
            )
            self.assertEqual(
                _framework.expired_unverdicted_count(), 1
            )
            verdict_env = _framework.append_discovery_verdict(
                expired_hash, "accepted",
                "real finding, consciously deferred — cost of ignorance named",
            )
            self.assertEqual(
                verdict_env["payload"]["verdict"], "accepted"
            )
            # Verdicted now — no longer open, no longer expired-pending.
            self.assertEqual(len(_framework.open_deferred_discoveries()), 1)
            self.assertEqual(_framework.expired_unverdicted_count(), 0)
            # A second verdict on the same entry is still rejected.
            with self.assertRaises(_framework.ChainError):
                _framework.append_discovery_verdict(
                    expired_hash, "resolved", "double verdict must reject"
                )

    def test_compaction_preserves_expiry_closure(self):
        # Event 158 review BLOCKING finding: compaction rebuilds the
        # chain from GENESIS; an unremapped expiry ref would dangle and
        # silently RE-OPEN a machine-expired discovery. The dropped
        # duplicate sits BEFORE the expired entry so its hash shifts.
        with EphemeralHome():
            now = datetime.now(timezone.utc).isoformat()
            old = (
                datetime.now(timezone.utc) - timedelta(days=31)
            ).isoformat()
            _framework.write_deferred_discovery(
                {"flaw_classification": "config-gap",
                 "description": "dup family finding", "logged_at": now}
            )
            # Duplicate of the first — dedup only scans a tail window,
            # so force-append it to guarantee an open duplicate exists.
            _framework.write_deferred_discovery(
                {"flaw_classification": "config-gap",
                 "description": "dup family finding", "logged_at": now},
                dedup=False,
            )
            _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "ancient distinct finding",
                 "logged_at": old}
            )
            # Trigger relief: the ancient entry expires.
            _framework.write_deferred_discovery(
                {"flaw_classification": "other",
                 "description": "distinct trigger finding",
                 "logged_at": now},
                cap=2,
            )
            open_before = {
                e["payload"]["description"]
                for e in _framework.open_deferred_discoveries()
            }
            self.assertNotIn("ancient distinct finding", open_before)
            result = _framework.compact_deferred_discoveries()
            self.assertEqual(result.status, "compacted")
            open_after = {
                e["payload"]["description"]
                for e in _framework.open_deferred_discoveries()
            }
            self.assertEqual(open_before, open_after)
            self.assertNotIn("ancient distinct finding", open_after)
            chains = _framework.verify_chains()
            self.assertTrue(chains["deferred_discoveries"].intact)

    def test_expiry_via_old_envelope_ts_fallback(self):
        # The live-ledger legacy path: no payload logged_at at all, but
        # an old envelope append ts — MUST be expiry-eligible (this is
        # the shape of the real 178-entry backlog).
        with EphemeralHome():
            old_ts = (
                datetime.now(timezone.utc) - timedelta(days=31)
            ).isoformat()
            _framework._chain_append(
                _framework._deferred_discoveries_path(),
                {"type": "deferred_discovery",
                 "flaw_classification": "other",
                 "description": "legacy unstamped finding",
                 "status": "pending"},
                ts=old_ts,
            )
            res = _framework.write_deferred_discovery(
                {"flaw_classification": "config-gap",
                 "description": "distinct fresh finding",
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=1,
            )
            self.assertIn("entry_hash", res)
            open_now = _framework.open_deferred_discoveries()
            self.assertEqual(len(open_now), 1)
            self.assertEqual(
                open_now[0]["payload"]["description"],
                "distinct fresh finding",
            )

    def test_non_positive_cap_falls_back_to_default(self):
        # Event 158 review: a fat-fingered 0/-1 knob must not silently
        # freeze the write path with the banner suppressed.
        self.assertEqual(
            _framework._resolve_deferred_open_cap(0),
            _framework.DEFAULT_DEFERRED_OPEN_CAP,
        )
        self.assertEqual(
            _framework._resolve_deferred_open_cap(-5),
            _framework.DEFAULT_DEFERRED_OPEN_CAP,
        )
        with patch.dict(os.environ, {"EPISTEME_DEFERRED_OPEN_CAP": "0"}):
            self.assertEqual(
                _framework._resolve_deferred_open_cap(),
                _framework.DEFAULT_DEFERRED_OPEN_CAP,
            )
        with patch.dict(os.environ, {"EPISTEME_DEFERRED_OPEN_CAP": "-1"}):
            self.assertEqual(
                _framework._resolve_deferred_open_cap(),
                _framework.DEFAULT_DEFERRED_OPEN_CAP,
            )
        with patch.dict(os.environ, {"EPISTEME_DEFERRED_OPEN_CAP": "7"}):
            self.assertEqual(_framework._resolve_deferred_open_cap(), 7)

    def test_blueprint_d_writer_does_not_count_declined_entries(self):
        from core.hooks import _blueprint_d  # pyright: ignore[reportAttributeAccessIssue]
        with EphemeralHome():
            # Occupy the cap slot in the SAME scope the Blueprint-D write
            # will land in — post-E163 the cap is per project, so an
            # unattributed seed is a different backlog entirely.
            _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "fresh occupant of the only cap slot",
                 "context_signature": {
                     "project_name": _framework.canonical_project_key(Path("."))
                 },
                 "logged_at": datetime.now(timezone.utc).isoformat()}
            )
            surface = {
                "flaw_classification": "doc-code-drift",
                "deferred_discoveries": [
                    {"description": "a genuinely distinct adjacent gap",
                     "observable": "obs", "log_only_rationale": "why"},
                ],
            }
            with patch.dict(
                os.environ, {"EPISTEME_DEFERRED_OPEN_CAP": "1"}
            ):
                count = _blueprint_d.write_cascade_deferred_discoveries(
                    surface, correlation_id="cid-bd", op_label="git push",
                    cwd=Path("."),
                )
            self.assertEqual(count, 0)
            self.assertEqual(len(_framework.open_deferred_discoveries()), 1)
            self.assertEqual(
                _framework.read_deferred_skip_counter()["skipped_count"], 1
            )

    def test_verdict_resets_deferred_skip_counter(self):
        with EphemeralHome():
            env = _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "fresh finding one",
                 "logged_at": datetime.now(timezone.utc).isoformat()}
            )
            _framework.write_deferred_discovery(
                {"flaw_classification": "doc-code-drift",
                 "description": "distinct second finding",
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=1,
            )
            self.assertEqual(
                _framework.read_deferred_skip_counter()["skipped_count"], 1
            )
            _framework.append_discovery_verdict(
                env["entry_hash"], "resolved",
                "drained by operator in test — resets the window",
            )
            self.assertEqual(
                _framework.read_deferred_skip_counter()["skipped_count"], 0
            )


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


class DeferredProjectScoping(unittest.TestCase):
    """Event 163 — the ledger is GLOBAL across every repo the operator
    works in, but open_deferred_discoveries had no project filter (its
    siblings list_deferred_discoveries/list_protocols both do), so every
    session's banner counted every project's debt. Scope the VIEW; the
    E158 cap stays global (it bounds total operator review load)."""

    def _seed(self, project: str, desc: str, *, via_cwd: bool = False):
        payload = {
            "flaw_classification": "other",
            "description": desc,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        if via_cwd:
            payload["source_op"] = {"cwd": f"/Users/x/{project}"}
        else:
            payload["context_signature"] = {"project_name": project}
        return _framework.write_deferred_discovery(payload)

    def test_scoped_open_returns_only_that_project(self):
        with EphemeralHome():
            self._seed("episteme", "episteme finding one")
            self._seed("sanomap-metabolome-hub", "sanomap finding one")
            self._seed("sanomap-metabolome-hub", "sanomap finding two")
            self.assertEqual(len(_framework.open_deferred_discoveries()), 3)
            scoped = _framework.open_deferred_discoveries(project_name="episteme")
            self.assertEqual(len(scoped), 1)
            self.assertEqual(
                scoped[0]["payload"]["description"], "episteme finding one"
            )

    def test_cwd_basename_fallback_attributes_legacy_entries(self):
        with EphemeralHome():
            self._seed("episteme", "legacy via cwd", via_cwd=True)
            scoped = _framework.open_deferred_discoveries(project_name="episteme")
            self.assertEqual(len(scoped), 1)

    def test_unattributed_entries_are_counted_never_dropped(self):
        # A filter that hides findings is worse than a banner that
        # overcounts — unattributable entries must surface in the tally.
        with EphemeralHome():
            self._seed("episteme", "attributed finding")
            _framework.write_deferred_discovery({
                "flaw_classification": "other",
                "description": "no project signal at all",
                "logged_at": datetime.now(timezone.utc).isoformat(),
            })
            counts = _framework.open_counts_by_project()
            self.assertEqual(counts.get("episteme"), 1)
            self.assertEqual(counts.get(_framework.UNATTRIBUTED_KEY), 1)
            self.assertEqual(sum(counts.values()),
                             len(_framework.open_deferred_discoveries()))

    def test_cap_is_per_project_no_cross_project_starvation(self):
        # E158 made the cap global on the assumption the ledger was one
        # repo's. The E163 drain disproved it empirically: with 118 open
        # findings from another repo, THIS repo could not record a single
        # new finding despite an empty backlog of its own — one repo's
        # activity silently causing finding-loss in every other repo, the
        # same silent-outage class E157 fixed. Storage stays global;
        # backpressure follows the backlog an operator actually drains.
        with EphemeralHome():
            self._seed("other-project", "occupies other-project's only slot")
            res = _framework.write_deferred_discovery(
                {"flaw_classification": "other",
                 "description": "episteme entry must NOT be starved",
                 "context_signature": {"project_name": "episteme"},
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=1,
            )
            self.assertIn("entry_hash", res)
            self.assertEqual(
                len(_framework.open_deferred_discoveries(project_name="episteme")),
                1,
            )

    def test_cap_still_bounds_within_one_project(self):
        with EphemeralHome():
            self._seed("episteme", "occupies episteme's only slot")
            res = _framework.write_deferred_discovery(
                {"flaw_classification": "other",
                 "description": "second episteme entry exceeds its own cap",
                 "context_signature": {"project_name": "episteme"},
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=1,
            )
            self.assertTrue(res.get("declined_at_cap"))

    def test_relief_never_expires_another_projects_findings(self):
        with EphemeralHome():
            old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
            _framework.write_deferred_discovery({
                "flaw_classification": "other",
                "description": "another repo's ancient finding",
                "context_signature": {"project_name": "other-project"},
                "logged_at": old,
            })
            self._seed("episteme", "episteme fresh finding")
            _framework.write_deferred_discovery(
                {"flaw_classification": "other",
                 "description": "episteme second finding triggers its own cap",
                 "context_signature": {"project_name": "episteme"},
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=1,
            )
            # The other project's aged finding must survive: relief is
            # scoped to the backlog that summoned it.
            self.assertEqual(
                len(_framework.open_deferred_discoveries(
                    project_name="other-project")),
                1,
            )


class DeferredScopingReviewFixes(unittest.TestCase):
    """Event 163 independent-review findings, each reproduced before
    being fixed — pinned here so they cannot regress."""

    def test_worktree_and_subdir_resolve_to_the_repo_key(self):
        # BLOCKING 1: Path.cwd().name invented a phantom project per
        # subdir and per agent worktree ('hooks', 'agent-<hex>').
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "MyRepo"
            (repo / ".git").mkdir(parents=True)
            (repo / "core" / "hooks").mkdir(parents=True)
            # Real shape: agent worktrees live INSIDE the repo at
            # .claude/worktrees/agent-<hex>, and their .git is a FILE.
            wt = repo / ".claude" / "worktrees" / "agent-deadbeef"
            wt.mkdir(parents=True)
            (wt / ".git").write_text("gitdir: elsewhere")
            self.assertEqual(_framework.canonical_project_key(repo), "myrepo")
            self.assertEqual(
                _framework.canonical_project_key(repo / "core" / "hooks"),
                "myrepo",
            )
            self.assertEqual(
                _framework.canonical_project_key(wt), "myrepo",
                "an agent worktree must not become its own phantom project",
            )

    def test_project_key_normalization_matches_the_signature_writer(self):
        # NIT 10: the signature writer lowercases + collapses whitespace;
        # the readers did not, so 'MyProject' stored 'myproject' and
        # matched nothing. The operator has a path with a space today.
        self.assertEqual(_framework._normalize_project_key("MyProject"), "myproject")
        self.assertEqual(_framework._normalize_project_key("  mgh   lmic "), "mgh lmic")

    def test_unattributed_write_never_expires_another_projects_findings(self):
        # BLOCKING 3: with project None the cap+relief fell back to
        # GLOBAL scope, so one unattributed write mass-expired another
        # project's aged findings to make room.
        with EphemeralHome():
            old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
            for i in range(3):
                _framework.write_deferred_discovery({
                    "flaw_classification": "other",
                    "description": f"other-project aged finding {i}",
                    "context_signature": {"project_name": "other-project"},
                    "logged_at": old,
                })
            before = len(_framework.open_deferred_discoveries(
                project_name="other-project"))
            self.assertEqual(before, 3)
            _framework.write_deferred_discovery(
                {"flaw_classification": "other",
                 "description": "an entry with no project signal at all",
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=1,
            )
            self.assertEqual(
                len(_framework.open_deferred_discoveries(
                    project_name="other-project")),
                3,
                "an unattributed write expired another project's findings",
            )

    def test_unattributed_entries_are_not_starved_by_other_projects(self):
        with EphemeralHome():
            for i in range(3):
                _framework.write_deferred_discovery({
                    "flaw_classification": "other",
                    "description": f"other-project finding {i}",
                    "context_signature": {"project_name": "other-project"},
                    "logged_at": datetime.now(timezone.utc).isoformat(),
                })
            res = _framework.write_deferred_discovery(
                {"flaw_classification": "other",
                 "description": "unattributed entry must still be admitted",
                 "logged_at": datetime.now(timezone.utc).isoformat()},
                cap=2,
            )
            self.assertIn("entry_hash", res)

    def test_global_ceiling_still_bounds_total_review_load(self):
        # SHOULD-FIX 4: per-project caps silently made the ceiling
        # unbounded. Budgets are code — the global bound is explicit.
        with EphemeralHome():
            for p in range(3):
                for i in range(2):
                    _framework.write_deferred_discovery({
                        "flaw_classification": "other",
                        "description": f"p{p} finding {i}",
                        "context_signature": {"project_name": f"proj-{p}"},
                        "logged_at": datetime.now(timezone.utc).isoformat(),
                    })
            with patch.dict(os.environ, {"EPISTEME_DEFERRED_GLOBAL_CAP": "6"}):
                res = _framework.write_deferred_discovery(
                    {"flaw_classification": "other",
                     "description": "fresh project blocked by GLOBAL ceiling",
                     "context_signature": {"project_name": "proj-new"},
                     "logged_at": datetime.now(timezone.utc).isoformat()},
                    cap=100,
                )
            self.assertTrue(res.get("declined_at_cap"))

    def test_projects_at_cap_names_only_the_paused_ones(self):
        with EphemeralHome():
            for i in range(2):
                _framework.write_deferred_discovery({
                    "flaw_classification": "other",
                    "description": f"busy-project finding {i}",
                    "context_signature": {"project_name": "busy-project"},
                    "logged_at": datetime.now(timezone.utc).isoformat(),
                })
            _framework.write_deferred_discovery({
                "flaw_classification": "other",
                "description": "quiet-project lone finding",
                "context_signature": {"project_name": "quiet-project"},
                "logged_at": datetime.now(timezone.utc).isoformat(),
            })
            with patch.dict(os.environ, {"EPISTEME_DEFERRED_OPEN_CAP": "2"}):
                at_cap = _framework.projects_at_cap()
            self.assertEqual(at_cap, [("busy-project", 2)])
