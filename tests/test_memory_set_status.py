"""Event 147 · A3 — memory-record status writer + promote auto-transition.

Covers the D11 gap: the status enum {active, archived, superseded} existed on
every ``.memory.json`` record and ``memory list --status`` filtered on it, but
nothing could transition a record. Two mechanisms under test:

1. ``episteme memory set-status <id> <status>`` — the explicit writer
   (``cli._memory_set_status``): the transition persists to disk and
   ``memory list --status`` then filters on the new state.
2. Promote auto-transition — ``_memory_promote.supersede_promoted_sources``
   (and its wiring through ``run_promote(records_dir=...)``) marks a source
   record superseded when a promotion copies its evidence into a proposal.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from episteme import cli
from episteme import _memory_promote as mp


def _record(rec_id: str, cls: str = "episodic", status: str = "active") -> dict:
    return {
        "id": rec_id,
        "memory_class": cls,
        "summary": f"record {rec_id}",
        "details": {},
        "provenance": {
            "source_type": "human",
            "source_ref": "cli",
            "captured_at": "2026-07-08T00:00:00Z",
            "captured_by": "test",
            "confidence": "medium",
            "evidence_refs": [],
        },
        "status": status,
        "version": "memory-contract-v1",
    }


def _write_record(records_dir: Path, rec: dict) -> Path:
    cls_dir = records_dir / rec["memory_class"]
    cls_dir.mkdir(parents=True, exist_ok=True)
    path = cls_dir / f"{rec['id']}.memory.json"
    path.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    return path


class SetStatusWriter(unittest.TestCase):
    def test_transition_persists(self):
        with tempfile.TemporaryDirectory() as td:
            records_dir = Path(td) / "records"
            path = _write_record(records_dir, _record("rec-1"))
            with patch.object(cli, "MEMORY_RECORDS_DIR", records_dir):
                rc = cli._memory_set_status("rec-1", "archived")
            self.assertEqual(rc, 0)
            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["status"], "archived")
            # The rest of the record is preserved verbatim.
            self.assertEqual(persisted["summary"], "record rec-1")

    def test_unknown_id_returns_error(self):
        with tempfile.TemporaryDirectory() as td:
            records_dir = Path(td) / "records"
            _write_record(records_dir, _record("rec-1"))
            with patch.object(cli, "MEMORY_RECORDS_DIR", records_dir):
                rc = cli._memory_set_status("does-not-exist", "archived")
            self.assertEqual(rc, 1)

    def test_list_status_filter_reflects_transition(self):
        with tempfile.TemporaryDirectory() as td:
            records_dir = Path(td) / "records"
            _write_record(records_dir, _record("rec-active"))
            _write_record(records_dir, _record("rec-2"))
            with patch.object(cli, "MEMORY_RECORDS_DIR", records_dir):
                cli._memory_set_status("rec-2", "superseded")
                # After transition, only rec-active is active; rec-2 is superseded.
                import io
                import contextlib

                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    cli._memory_list(memory_class=None, status="active", limit=20)
                active_out = buf.getvalue()
                self.assertIn("rec-active", active_out)
                self.assertNotIn("rec-2", active_out)

                buf2 = io.StringIO()
                with contextlib.redirect_stdout(buf2):
                    cli._memory_list(memory_class=None, status="superseded", limit=20)
                superseded_out = buf2.getvalue()
                self.assertIn("rec-2", superseded_out)


class PromoteAutoTransition(unittest.TestCase):
    def test_supersede_promoted_sources_marks_matches(self):
        with tempfile.TemporaryDirectory() as td:
            records_dir = Path(td) / "records"
            kept = _write_record(records_dir, _record("keep-me"))
            promoted = _write_record(records_dir, _record("promoted-1"))
            proposals = [{"evidence_refs": ["promoted-1", "ghost-id"]}]
            n = mp.supersede_promoted_sources(proposals, records_dir)
            self.assertEqual(n, 1)
            self.assertEqual(
                json.loads(promoted.read_text())["status"], "superseded"
            )
            # A record not referenced stays active.
            self.assertEqual(json.loads(kept.read_text())["status"], "active")

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            records_dir = Path(td) / "records"
            _write_record(records_dir, _record("promoted-1"))
            proposals = [{"evidence_refs": ["promoted-1"]}]
            first = mp.supersede_promoted_sources(proposals, records_dir)
            second = mp.supersede_promoted_sources(proposals, records_dir)
            self.assertEqual(first, 1)
            self.assertEqual(second, 0, "already-superseded records are skipped")

    def test_no_refs_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            records_dir = Path(td) / "records"
            _write_record(records_dir, _record("a"))
            self.assertEqual(mp.supersede_promoted_sources([], records_dir), 0)

    def test_run_promote_wires_transition(self):
        """End-to-end: a clusterable episodic set promotes, and the matching
        source record under records_dir is superseded."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # Build 3 clusterable episodic jsonl records with ids r0..r2.
            episodic = tmp / "episodic"
            episodic.mkdir()
            recs = []
            for i in range(3):
                recs.append({
                    "id": f"r{i}",
                    "memory_class": "episodic",
                    "summary": "bash: git push",
                    "details": {
                        "exit_code": 0,
                        "high_impact_patterns_matched": ["git push"],
                        "reasoning_surface": {"domain": "Complicated"},
                    },
                    "provenance": {"captured_at": "2026-07-08T00:00:00Z"},
                    "status": "active",
                    "version": "memory-contract-v1",
                })
            (episodic / "2026-07-08.jsonl").write_text(
                "\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8"
            )
            # Matching source .memory.json records under a records dir.
            records_dir = tmp / "records"
            for i in range(3):
                _write_record(records_dir, _record(f"r{i}"))

            report, count, path = mp.run_promote(
                episodic_dir=episodic,
                reflective_dir=tmp / "reflective",
                records_dir=records_dir,
            )
            self.assertEqual(count, 1)
            for i in range(3):
                rec_path = records_dir / "episodic" / f"r{i}.memory.json"
                self.assertEqual(
                    json.loads(rec_path.read_text())["status"],
                    "superseded",
                    f"r{i} should be superseded after promotion",
                )

    def test_run_promote_without_records_dir_leaves_records_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            episodic = tmp / "episodic"
            episodic.mkdir()
            (episodic / "e.jsonl").write_text("", encoding="utf-8")
            records_dir = tmp / "records"
            path = _write_record(records_dir, _record("r0"))
            mp.run_promote(
                episodic_dir=episodic,
                reflective_dir=tmp / "reflective",
            )
            self.assertEqual(json.loads(path.read_text())["status"], "active")


if __name__ == "__main__":
    unittest.main()
