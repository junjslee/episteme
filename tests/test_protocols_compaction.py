"""Protocols-ledger compaction — `_framework.compact_protocols` +
`episteme kernel compact-protocols`.

The Pillar-3 protocols chain accumulated a cascade-synthesis spam burst
(Event 143): identical resolution content chained hundreds of times
because per-command op_class variation defeated the signature supersede
before content-hash dedup shipped (commit 1c01f9d). Those legacy spam
records predate the ``payload.cascade_hash`` field, so compaction dedups
on the STORED cascade_hash when present, else the content hash
RECOMPUTED from the payload's own source_fields / op_outcome via the
kernel's own ``_cascade_synthesis.cascade_hash`` — the same function the
emit path uses, so a recomputed legacy key collides exactly with the
stored key of a modern record describing the same resolution.

Mirrors the sanctioned sibling ``compact_deferred_discoveries``:
parse-all-before-write, input chain pre-verify (refuse to launder a
break), keep-first, backup + atomic replace + post-verify, dry_run,
idempotent noop. Adds: whole-window flock (the ledger is append-hot),
content-key dedup, and supersedes remap (incl. re-pointing a supersedes
that referenced a dropped duplicate at the surviving representative).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.hooks import _cascade_synthesis  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _chain  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _framework  # pyright: ignore[reportAttributeAccessIssue]

_REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _cascade_payload(
    *,
    flaw: str = "config-gap",
    posture: str = "patch",
    surfaces: list[str] | None = None,
    observable: str = "exit_code == 0 held",
    cwd: str = "/tmp/example_project",
    correlation_id: str = "cid",
    with_hash: bool = False,
    include_source_fields: bool = True,
    supersedes: str | None = None,
) -> dict:
    """Build a cascade-synthesis protocol payload the way the emit path
    (``_cascade_synthesis._build_protocol``) shapes it. ``with_hash``
    stamps the STORED cascade_hash (modern record, post-1c01f9d);
    without it the record is a legacy spam record whose key must be
    RECOMPUTED. Both forms describing the same resolution collide."""
    if surfaces is None:
        surfaces = ["core/hooks/a.py", "core/hooks/b.py"]
    payload: dict = {
        "type": "protocol",
        "version": 1,
        "blueprint": "architectural_cascade",
        "source": "cascade_resolution",
        "correlation_id": correlation_id,
        "synthesized_protocol": f"resolved without divergence because `{observable}`",
        "op_outcome": {
            "exit_code": 0,
            "cwd": cwd,
            "command_redacted": "make test",
        },
    }
    if include_source_fields:
        payload["source_fields"] = {
            "flaw_classification": flaw,
            "posture_selected": posture,
            "blast_radius_surfaces": surfaces,
            "blast_radius_count": len(surfaces),
            "core_question": "does the flaw recur across surfaces?",
            "observable": observable,
        }
    if with_hash:
        subsystem = _cascade_synthesis._subsystem(surfaces)
        project = Path(cwd).resolve().name or "unknown_project"
        payload["cascade_hash"] = _cascade_synthesis.cascade_hash(
            project, subsystem, flaw, posture, surfaces, observable
        )
    if supersedes is not None:
        payload["supersedes"] = supersedes
    return payload


def _non_cascade_payload(*, correlation_id: str, supersedes: str | None = None) -> dict:
    """A protocol that is NOT a cascade — must always be kept, never a
    dedup candidate."""
    payload: dict = {
        "type": "protocol",
        "version": 1,
        "blueprint": "generic",
        "correlation_id": correlation_id,
        "synthesized_protocol": f"generic protocol {correlation_id}",
    }
    if supersedes is not None:
        payload["supersedes"] = supersedes
    return payload


def _protocols_path() -> Path:
    return _framework._protocols_path()


def _read_payloads() -> list[dict]:
    """Raw read of the protocols chain: list of {ts, entry_hash, payload}
    envelopes in file order (no supersede/dedup filtering)."""
    p = _protocols_path()
    if not p.is_file():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            out.append(json.loads(ln))
    return out


class CompactProtocolsCore(unittest.TestCase):
    # 1. Operator's contract.
    def test_operator_contract_collapses_legacy_spam_keep_first(self):
        with EphemeralHome():
            # 2 non-cascade protocols (always kept).
            _framework.write_protocol(_non_cascade_payload(correlation_id="gen-0"))
            _framework.write_protocol(_non_cascade_payload(correlation_id="gen-1"))
            # 3 distinct legit cascade protocols (with stored cascade_hash).
            for i in range(3):
                _framework.write_protocol(
                    _cascade_payload(
                        flaw=f"distinct-flaw-{i}",
                        observable=f"distinct observable {i}",
                        correlation_id=f"legit-{i}",
                        with_hash=True,
                    )
                )
            # 100 identical-content LEGACY cascade records (NO cascade_hash).
            for i in range(100):
                _framework.write_protocol(
                    _cascade_payload(
                        flaw="spammy-flaw",
                        observable="the spam resolution content",
                        correlation_id=f"legacy-{i:03d}",
                        with_hash=False,
                    )
                )

            before = _read_payloads()
            self.assertEqual(len(before), 105)

            result = _framework.compact_protocols()
            self.assertEqual(result.status, "compacted")
            self.assertEqual(result.removed, 99)
            self.assertEqual(result.total_before, 105)
            self.assertEqual(result.total_after, 6)

            self.assertTrue(_framework.verify_chains()["protocols"].intact)

            after = _read_payloads()
            self.assertEqual(len(after), 105 - 99)
            # Keep-first: exactly one spam survivor, the FIRST (legacy-000).
            spam = [
                e for e in after
                if e["payload"].get("source_fields", {}).get("observable")
                == "the spam resolution content"
            ]
            self.assertEqual(len(spam), 1)
            self.assertEqual(spam[0]["payload"]["correlation_id"], "legacy-000")

    # 2. Mixed cluster: legacy (no field) + modern (with field), same content.
    def test_mixed_cluster_legacy_and_modern_first_legacy_wins(self):
        with EphemeralHome():
            for i in range(5):
                _framework.write_protocol(
                    _cascade_payload(
                        flaw="mixed",
                        observable="one resolution",
                        correlation_id=f"legacy-{i}",
                        with_hash=False,
                    )
                )
            _framework.write_protocol(
                _cascade_payload(
                    flaw="mixed",
                    observable="one resolution",
                    correlation_id="modern",
                    with_hash=True,
                )
            )
            result = _framework.compact_protocols()
            self.assertEqual(result.status, "compacted")
            self.assertEqual(result.removed, 5)
            after = _read_payloads()
            self.assertEqual(len(after), 1)
            # First legacy record is the surviving representative.
            self.assertEqual(after[0]["payload"]["correlation_id"], "legacy-0")

    # 3. supersedes remap (incl. re-pointing a dropped-duplicate target).
    def test_supersedes_remapped_through_dropped_duplicate(self):
        with EphemeralHome():
            # A: cascade key K, kept.
            _framework.write_protocol(
                _cascade_payload(
                    flaw="remap", observable="same", correlation_id="A", with_hash=False
                )
            )
            # B: duplicate of A (key K), dropped.
            b_env = _framework.write_protocol(
                _cascade_payload(
                    flaw="remap", observable="same", correlation_id="B", with_hash=False
                )
            )
            b_old = b_env["entry_hash"]
            # C: a protocol whose supersedes points at B's OLD entry_hash.
            _framework.write_protocol(
                _non_cascade_payload(correlation_id="C", supersedes=b_old)
            )

            result = _framework.compact_protocols()
            self.assertEqual(result.status, "compacted")
            self.assertEqual(result.removed, 1)

            after = _read_payloads()
            new_hashes = {e["entry_hash"] for e in after}
            a_new = next(
                e["entry_hash"] for e in after
                if e["payload"]["correlation_id"] == "A"
            )
            c = next(e for e in after if e["payload"]["correlation_id"] == "C")
            # C's supersedes now points at A's NEW entry_hash (B collapsed
            # into A, and A's hash was recomputed by the GENESIS rebuild).
            self.assertEqual(c["payload"]["supersedes"], a_new)
            # Every supersedes value is resolvable to a live hash, or was
            # verbatim-unresolvable by construction (none such here).
            for e in after:
                sup = e["payload"].get("supersedes")
                if isinstance(sup, str) and sup.startswith("sha256:"):
                    self.assertIn(sup, new_hashes)

    # 4. Derivation failure — cascade record with source_fields missing.
    def test_derivation_failure_record_kept_and_counted(self):
        with EphemeralHome():
            # In-scope cascade record whose key cannot be derived
            # (source_fields absent) — must be kept, never dropped.
            _framework.write_protocol(
                _cascade_payload(
                    correlation_id="broken",
                    with_hash=False,
                    include_source_fields=False,
                )
            )
            # Plus a removable duplicate pair so status == compacted and the
            # derivation-failure count is surfaced in the message.
            for i in range(3):
                _framework.write_protocol(
                    _cascade_payload(
                        flaw="ok", observable="derivable",
                        correlation_id=f"dup-{i}", with_hash=False,
                    )
                )

            result = _framework.compact_protocols()
            self.assertEqual(result.status, "compacted")
            self.assertEqual(result.removed, 2)  # 2 of the 3 dups collapse
            after = _read_payloads()
            cids = {e["payload"]["correlation_id"] for e in after}
            self.assertIn("broken", cids)  # derivation-failure survivor kept
            # The result message surfaces the derivation-failure count.
            self.assertIn("1", result.message)
            self.assertIn("underivable", result.message.lower())

    # 5. Tamper guard — flip one byte, refuse for BOTH dry_run values.
    def test_tamper_refused_for_both_dry_run_and_real(self):
        with EphemeralHome():
            for i in range(3):
                _framework.write_protocol(
                    _cascade_payload(
                        flaw=f"t-{i}",
                        observable=f"OBS_MARKER_{i}",
                        correlation_id=f"t-{i}",
                        with_hash=True,
                    )
                )
            p = _protocols_path()
            text = p.read_text(encoding="utf-8")
            # Flip one char inside a payload string value: JSON still parses,
            # entry_hash no longer matches -> input chain not intact.
            self.assertIn("OBS_MARKER_1", text)
            p.write_text(text.replace("OBS_MARKER_1", "OBS_MARKER_X"), encoding="utf-8")

            with self.assertRaises(_framework.ChainError):
                _framework.compact_protocols(dry_run=True)
            with self.assertRaises(_framework.ChainError):
                _framework.compact_protocols(dry_run=False)

    # 6. dry_run — no backup, bytes unchanged, counts correct.
    def test_dry_run_no_write_no_backup(self):
        with EphemeralHome():
            for i in range(4):
                _framework.write_protocol(
                    _cascade_payload(
                        flaw="dr", observable="same", correlation_id=f"d-{i}",
                        with_hash=False,
                    )
                )
            p = _protocols_path()
            original = p.read_bytes()

            result = _framework.compact_protocols(dry_run=True)
            self.assertEqual(result.status, "compacted")
            self.assertEqual(result.removed, 3)
            self.assertIsNone(result.backup_path)
            self.assertIsNone(result.head_hash)
            self.assertEqual(p.read_bytes(), original)  # bytes unchanged
            self.assertEqual(
                sorted(p.parent.glob("*.compact-*.bak")), []
            )

    # 7. Idempotency — second real run is a noop with no second backup.
    def test_idempotent_second_run_noop(self):
        with EphemeralHome():
            for i in range(3):
                _framework.write_protocol(
                    _cascade_payload(
                        flaw="idem", observable="same", correlation_id=f"i-{i}",
                        with_hash=False,
                    )
                )
            r1 = _framework.compact_protocols()
            self.assertEqual(r1.status, "compacted")
            baks1 = sorted(_protocols_path().parent.glob("*.compact-*.bak"))
            self.assertEqual(len(baks1), 1)

            r2 = _framework.compact_protocols()
            self.assertEqual(r2.status, "noop")
            self.assertEqual(r2.removed, 0)
            self.assertEqual(r2.total_before, r2.total_after)
            self.assertIsNone(r2.backup_path)
            baks2 = sorted(_protocols_path().parent.glob("*.compact-*.bak"))
            self.assertEqual(len(baks2), 1)  # no second backup

    # 8. Backup fidelity — backup bytes == original bytes.
    def test_backup_bytes_match_original(self):
        with EphemeralHome():
            for i in range(3):
                _framework.write_protocol(
                    _cascade_payload(
                        flaw="bak", observable="same", correlation_id=f"b-{i}",
                        with_hash=False,
                    )
                )
            original = _protocols_path().read_bytes()
            result = _framework.compact_protocols()
            self.assertIsNotNone(result.backup_path)
            self.assertEqual(Path(result.backup_path).read_bytes(), original)

    # noop path: no cascade duplicates at all -> untouched, no backup.
    def test_noop_when_no_duplicates(self):
        with EphemeralHome():
            for i in range(3):
                _framework.write_protocol(
                    _cascade_payload(
                        flaw=f"uniq-{i}", observable=f"uniq {i}",
                        correlation_id=f"u-{i}", with_hash=True,
                    )
                )
            result = _framework.compact_protocols()
            self.assertEqual(result.status, "noop")
            self.assertEqual(result.removed, 0)
            self.assertIsNone(result.backup_path)


class CompactProtocolsCLI(unittest.TestCase):
    """9. CLI e2e via subprocess."""

    def _seed(self, home: Path) -> None:
        for i in range(6):
            _framework.write_protocol(
                _cascade_payload(
                    flaw="cli", observable="one cli resolution",
                    correlation_id=f"c-{i}", with_hash=False,
                )
            )

    def _run(self, home: Path, *args: str) -> subprocess.CompletedProcess:
        env = {
            **os.environ,
            "EPISTEME_HOME": str(home),
            "PYTHONPATH": str(_REPO_ROOT / "src"),
        }
        return subprocess.run(
            [sys.executable, "-m", "episteme.cli", "kernel", "compact-protocols", *args],
            env=env,
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )

    def test_non_dry_run_without_confirm_exits_2(self):
        with EphemeralHome() as home:
            self._seed(home)
            proc = self._run(home)
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertIn("confirm", proc.stderr.lower())
            # ledger untouched
            self.assertEqual(len(_read_payloads()), 6)

    def test_dry_run_works_without_confirm(self):
        with EphemeralHome() as home:
            self._seed(home)
            proc = self._run(home, "--dry-run")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(len(_read_payloads()), 6)  # unchanged

    def test_confirm_compacts(self):
        with EphemeralHome() as home:
            self._seed(home)
            proc = self._run(home, "--confirm")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(len(_read_payloads()), 1)  # collapsed

    def test_json_carries_intact_true(self):
        with EphemeralHome() as home:
            self._seed(home)
            proc = self._run(home, "--confirm", "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            obj = json.loads(proc.stdout)
            self.assertEqual(obj["intact"], True)
            self.assertEqual(obj["removed"], 5)
            self.assertEqual(obj["status"], "compacted")


if __name__ == "__main__":
    unittest.main()
