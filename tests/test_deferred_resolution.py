"""Deferred-discovery resolution layer — the drain the ledger never had.

The 2026-07-03 recon: 233/233 entries permanently 'pending' with no
resolve API anywhere (OPEN_STATUSES held only 'pending'; the only
lifecycle op was dedup compaction). Resolution is APPEND-ONLY: a
`deferred_discovery_verdict` chain record references the discovery's
entry_hash; the discovery record is never mutated, the chain stays
verifiable, and openness is derived (pending AND unverdicted). The
SessionStart banner and `episteme guide --deferred` read the derived
count, so a verdict is what stops a finding re-firing every session.
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from core.hooks import _framework

# NOTE: _framework raises the ChainError from the sys.path-shimmed
# top-level `_chain` module, which is a DIFFERENT class object from
# core.hooks._chain.ChainError (dual-import identity — the recon's
# named architecture gap around bare underscore imports). Bind the
# exception from _framework's own namespace so assertRaises matches
# what actually propagates.
ChainError = _framework.ChainError

from episteme import cli  # noqa: E402


def _write_discovery(path: Path, description: str) -> dict:
    return _framework.write_deferred_discovery(
        {
            "description": description,
            "observable": f"if {description} recurs, the linter flags it",
            "log_only_rationale": "test fixture",
            "status": "pending",
        },
        path=path,
    )


class ResolutionSemantics(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "deferred_discoveries.jsonl"
        self.addCleanup(self._tmp.cleanup)

    def test_verdict_closes_a_discovery(self):
        a = _write_discovery(self.path, "alpha finding")
        _write_discovery(self.path, "beta finding")
        self.assertEqual(
            len(_framework.open_deferred_discoveries(path=self.path)), 2
        )
        _framework.append_discovery_verdict(
            a["entry_hash"], "resolved",
            "fixed in commit abc123 with a regression test",
            path=self.path,
        )
        open_now = _framework.open_deferred_discoveries(path=self.path)
        self.assertEqual(len(open_now), 1)
        self.assertEqual(
            open_now[0]["payload"]["description"], "beta finding"
        )

    def test_bare_hex_prefix_matches_scheme_prefixed_hash(self):
        # Event 152: entries are stored as `sha256:<hex>` but `episteme
        # deferred list` also shows the bare hex; a copy-paste of EITHER
        # must resolve. Pre-fix the scheme-only startswith rejected bare
        # hex, forcing operators to hand-prepend `sha256:`.
        a = _write_discovery(self.path, "alpha finding")
        full = a["entry_hash"]
        self.assertTrue(full.startswith("sha256:"))
        bare = full.split(":", 1)[1]
        _framework.append_discovery_verdict(
            bare[:12], "resolved",
            "resolved via a bare-hex prefix ref (no sha256: scheme)",
            path=self.path,
        )
        self.assertEqual(
            len(_framework.open_deferred_discoveries(path=self.path)), 0
        )

    def test_scheme_prefixed_ref_still_matches(self):
        # The fix must not regress the scheme-prefixed path.
        a = _write_discovery(self.path, "alpha finding")
        _framework.append_discovery_verdict(
            a["entry_hash"][:19], "noise",
            "still resolves with the full sha256: scheme prefix",
            path=self.path,
        )
        self.assertEqual(
            len(_framework.open_deferred_discoveries(path=self.path)), 0
        )

    def test_chain_remains_verifiable_after_verdicts(self):
        a = _write_discovery(self.path, "alpha finding")
        _framework.append_discovery_verdict(
            a["entry_hash"], "noise",
            "pattern cannot occur: input is enum-validated upstream",
            path=self.path,
        )
        verdict = _framework.verify_chains(
            deferred_discoveries_path=self.path,
            protocols_path=self.path.with_name("protocols.jsonl"),
        )["deferred_discoveries"]
        self.assertTrue(
            verdict.intact,
            f"chain broken after verdict append: {verdict}",
        )
        self.assertEqual(verdict.total_entries, 2)

    def test_accepted_verdict_closes_a_discovery(self):
        # Event 152: `accepted` is a fourth first-class verdict — a REAL
        # finding the operator consciously decides NOT to act on, closed
        # with the cost of ignorance named. It must close an open
        # discovery exactly like resolved/noise/duplicate (openness =
        # has-any-verdict), and still enforce the rationale floor so the
        # cost of ignorance cannot be an empty gesture.
        a = _write_discovery(self.path, "alpha finding")
        _write_discovery(self.path, "beta finding")
        self.assertEqual(
            len(_framework.open_deferred_discoveries(path=self.path)), 2
        )
        _framework.append_discovery_verdict(
            a["entry_hash"], "accepted",
            "real gap; not acting this cycle — cost: stale doc ref lingers",
            path=self.path,
        )
        open_now = _framework.open_deferred_discoveries(path=self.path)
        self.assertEqual(len(open_now), 1)
        self.assertEqual(
            open_now[0]["payload"]["description"], "beta finding"
        )
        # Too-short rationale is rejected for `accepted` just like the
        # other verdicts (the cost of ignorance must actually be named).
        b = _write_discovery(self.path, "gamma finding")
        with self.assertRaises(ChainError):
            _framework.append_discovery_verdict(
                b["entry_hash"], "accepted", "meh", path=self.path,
            )

    def test_chain_remains_verifiable_after_accepted_verdict(self):
        a = _write_discovery(self.path, "alpha finding")
        _framework.append_discovery_verdict(
            a["entry_hash"], "accepted",
            "real finding; deferred by decision — cost of ignorance named",
            path=self.path,
        )
        verdict = _framework.verify_chains(
            deferred_discoveries_path=self.path,
            protocols_path=self.path.with_name("protocols.jsonl"),
        )["deferred_discoveries"]
        self.assertTrue(
            verdict.intact,
            f"chain broken after accepted verdict: {verdict}",
        )
        self.assertEqual(verdict.total_entries, 2)

    def test_double_verdict_rejected(self):
        a = _write_discovery(self.path, "alpha finding")
        _framework.append_discovery_verdict(
            a["entry_hash"], "resolved", "fixed and covered by tests",
            path=self.path,
        )
        with self.assertRaises(ChainError):
            _framework.append_discovery_verdict(
                a["entry_hash"], "noise", "contradictory second verdict",
                path=self.path,
            )

    def test_unknown_ref_rejected(self):
        _write_discovery(self.path, "alpha finding")
        with self.assertRaises(ChainError):
            _framework.append_discovery_verdict(
                "deadbeef0000", "resolved", "no such entry exists here",
                path=self.path,
            )

    def test_ambiguous_and_short_prefixes_rejected(self):
        a = _write_discovery(self.path, "alpha finding")
        with self.assertRaises(ChainError):
            _framework.append_discovery_verdict(
                a["entry_hash"][:4], "resolved", "prefix is too short",
                path=self.path,
            )

    def test_prefix_resolution_works(self):
        a = _write_discovery(self.path, "alpha finding")
        env = _framework.append_discovery_verdict(
            a["entry_hash"][:12], "duplicate",
            "covered by the beta entry recorded the same day",
            path=self.path,
        )
        self.assertEqual(env["payload"]["ref"], a["entry_hash"])

    def test_invalid_verdict_and_lazy_rationale_rejected(self):
        a = _write_discovery(self.path, "alpha finding")
        with self.assertRaises(ChainError):
            _framework.append_discovery_verdict(
                a["entry_hash"], "wontfix", "not an allowed verdict value",
                path=self.path,
            )
        with self.assertRaises(ChainError):
            _framework.append_discovery_verdict(
                a["entry_hash"], "resolved", "done", path=self.path,
            )

    def test_legacy_statusless_records_count_as_open(self):
        from core.hooks._chain import append as chain_append
        chain_append(self.path, {
            "type": _framework.DEFERRED_DISCOVERY_TYPE,
            "description": "historical writer emitted no status",
        })
        self.assertEqual(
            len(_framework.open_deferred_discoveries(path=self.path)), 1
        )

    def test_verdict_records_never_listed_as_discoveries(self):
        a = _write_discovery(self.path, "alpha finding")
        _framework.append_discovery_verdict(
            a["entry_hash"], "resolved", "fixed; see regression test",
            path=self.path,
        )
        for env in _framework.open_deferred_discoveries(path=self.path):
            self.assertEqual(
                env["payload"].get("type"),
                _framework.DEFERRED_DISCOVERY_TYPE,
            )

    def test_verdicts_survive_compaction(self):
        # Review finding: `episteme chain compact` rebuilds the chain
        # from GENESIS, recomputing every entry_hash. Without ref
        # remapping + verdict-aware dedup, a resolved discovery re-opens
        # and its verdict ref dangles. Build a chain with duplicate
        # pending findings (so compaction actually removes something)
        # plus a verdict, compact, and assert the resolved one stays
        # resolved and the chain verifies.
        # write_deferred_discovery dedups at write time (Event 49), so
        # reproduce the pre-Event-49 bloat by appending duplicates
        # directly to the chain.
        from core.hooks._chain import append as chain_append
        for _ in range(3):
            chain_append(self.path, {
                "type": _framework.DEFERRED_DISCOVERY_TYPE,
                "description": "dup finding",
                "observable": "if dup finding recurs the linter flags it",
                "log_only_rationale": "test fixture",
                "status": "pending",
            })
        keep = _write_discovery(self.path, "unique finding")
        _framework.append_discovery_verdict(
            keep["entry_hash"], "resolved",
            "addressed; must not re-open after compaction",
            path=self.path,
        )
        before_open = {
            e["payload"]["description"]
            for e in _framework.open_deferred_discoveries(path=self.path)
        }
        # 'unique finding' is verdicted -> not open; 'dup finding' open.
        self.assertNotIn("unique finding", before_open)

        result = _framework.compact_deferred_discoveries(path=self.path)
        self.assertEqual(result.status, "compacted")
        self.assertGreater(result.removed, 0)

        verdict = _framework.verify_chains(
            deferred_discoveries_path=self.path,
            protocols_path=self.path.with_name("protocols.jsonl"),
        )["deferred_discoveries"]
        self.assertTrue(verdict.intact, f"chain broken after compaction: {verdict}")

        after_open = {
            e["payload"]["description"]
            for e in _framework.open_deferred_discoveries(path=self.path)
        }
        # The verdicted discovery must NOT have re-opened.
        self.assertNotIn("unique finding", after_open)
        # And the verdict must still reject a contradictory second one
        # (ref resolves to the surviving, remapped entry_hash).
        surviving = [
            e for e in _framework.list_deferred_discoveries(path=self.path)
            if e["payload"]["description"] == "unique finding"
        ]
        self.assertEqual(len(surviving), 1)
        with self.assertRaises(ChainError):
            _framework.append_discovery_verdict(
                surviving[0]["entry_hash"], "noise",
                "contradictory verdict after compaction must be rejected",
                path=self.path,
            )

    def test_verdicting_first_member_still_dedups_the_rest(self):
        # Second review round: verdicting the FIRST of an open
        # duplicate-set must NOT keep its later unverdicted duplicates
        # alive. Two identical open findings; verdict the first; compact
        # must still drop the second, leaving zero open.
        from core.hooks._chain import append as chain_append
        payload = {
            "type": _framework.DEFERRED_DISCOVERY_TYPE,
            "description": "identical finding",
            "observable": "if identical finding recurs the linter flags it",
            "log_only_rationale": "test fixture",
            "status": "pending",
        }
        e1 = chain_append(self.path, dict(payload))
        chain_append(self.path, dict(payload))  # exact duplicate
        _framework.append_discovery_verdict(
            e1["entry_hash"], "resolved",
            "resolved; its duplicate must not survive compaction",
            path=self.path,
        )
        result = _framework.compact_deferred_discoveries(path=self.path)
        self.assertEqual(result.status, "compacted")
        self.assertEqual(result.removed, 1)
        self.assertEqual(
            _framework.open_deferred_discoveries(path=self.path), []
        )
        verdict = _framework.verify_chains(
            deferred_discoveries_path=self.path,
            protocols_path=self.path.with_name("protocols.jsonl"),
        )["deferred_discoveries"]
        self.assertTrue(verdict.intact)


class CliDrain(unittest.TestCase):
    """episteme deferred list|resolve against a sandboxed HOME."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self._env = patch.dict(
            "os.environ",
            {"HOME": str(home), "EPISTEME_HOME": str(home / ".episteme")},
        )
        self._env.start()
        self.addCleanup(self._env.stop)
        self.ledger = home / ".episteme" / "framework" / "deferred_discoveries.jsonl"
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.entry = _write_discovery(self.ledger, "cli fixture finding")

    def _main(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_list_shows_open_with_ref(self):
        rc, out, _ = self._main(["deferred", "list"])
        self.assertEqual(rc, 0)
        self.assertIn(self.entry["entry_hash"][:12], out)
        self.assertIn("1 open deferred discovery", out)

    def test_resolve_then_list_empty(self):
        rc, out, err = self._main([
            "deferred", "resolve", self.entry["entry_hash"][:12],
            "--verdict", "resolved",
            "--why", "fixed tonight; covered by a regression test",
        ])
        self.assertEqual(rc, 0, err)
        self.assertIn("[ok] verdict 'resolved' chained", out)
        self.assertIn("0 open deferred discoveries remain", out)
        rc2, out2, _ = self._main(["deferred", "list", "--json"])
        self.assertEqual(rc2, 0)
        self.assertEqual(json.loads(out2), [])

    def test_resolve_accepted_verdict(self):
        # Event 152: the CLI must admit `--verdict accepted` and chain it
        # like any other verdict, dropping the entry from the open count.
        rc, out, err = self._main([
            "deferred", "resolve", self.entry["entry_hash"][:12],
            "--verdict", "accepted",
            "--why", "real gap; consciously not acting — cost of ignorance named",
        ])
        self.assertEqual(rc, 0, err)
        self.assertIn("[ok] verdict 'accepted' chained", out)
        self.assertIn("0 open deferred discoveries remain", out)
        rc2, out2, _ = self._main(["deferred", "list", "--json"])
        self.assertEqual(rc2, 0)
        self.assertEqual(json.loads(out2), [])

    def test_resolve_error_paths_exit_nonzero(self):
        rc, _, err = self._main([
            "deferred", "resolve", "deadbeef0000",
            "--verdict", "noise", "--why", "no such reference exists",
        ])
        self.assertEqual(rc, 1)
        self.assertIn("no verdictable deferred discovery matches", err)


if __name__ == "__main__":
    unittest.main()
