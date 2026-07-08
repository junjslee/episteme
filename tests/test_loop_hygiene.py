"""Loop-hygiene — Event 145 §3/§4/§5 (FINAL_PRODUCTIZATION_BLUEPRINT).

Lane B1 tests for the four loop-hygiene mechanisms:

- §3.1 pair-signature fallback ladder: a >5s, no-tool_use_id op still
  pairs Pre→Post via a timestamp-independent signature scan (tier 3),
  oldest-first FIFO, TTL-filtered, delete-on-use; old v1 markers never
  signature-match; ppid is a soft discriminator (probe: Pre/Post share
  PPID) that never fails a legitimate pair closed.
- §3.2 single per-op timestamp: the guard samples ONE wall-clock per
  admitted op and threads it to every correlation-id write, so the
  cascade marker carries the first sample's bucket (not a second
  independent `_marker_ts`).
- §4 concurrency: shared rewrite mutex + lock-order, inode re-verify in
  `_locked` (orphaned-inode append race), retrofit whole-window lock
  into `compact_deferred_discoveries`.
- §5.1 read-side legacy healing: a legacy no-`cascade_hash` record
  suppresses an identical modern emission via the shared
  `_cascade_content_key`.
- §5.2 namespace symmetry: `episteme chain compact --stream protocols`
  and `episteme kernel compact-protocols` produce an identical result.
"""
from __future__ import annotations

import fcntl
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.hooks import reasoning_surface_guard as guard
from core.hooks import _scenario_detector as detector  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _fence_synthesis as fence_synth  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _cascade_synthesis as cascade_synth  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _chain  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _framework  # pyright: ignore[reportAttributeAccessIssue]

_REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# Shared fixtures (mirror the fence / cascade e2e harnesses)
# --------------------------------------------------------------------------

class _EphemeralEpistemeHome:
    def __enter__(self):
        self._home = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("EPISTEME_HOME")
        os.environ["EPISTEME_HOME"] = self._home.name
        detector._reset_trigger_cache_for_tests()
        return Path(self._home.name)

    def __exit__(self, *a):
        if self._prev is None:
            os.environ.pop("EPISTEME_HOME", None)
        else:
            os.environ["EPISTEME_HOME"] = self._prev
        self._home.cleanup()
        detector._reset_trigger_cache_for_tests()


def _valid_fence_surface(constraint: str = "core/hooks/_grounding.py:32") -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "core_question": "Is removing this constraint safe in this context?",
        "knowns": ["CP3 landed 2026-04-21 with 340 tests green"],
        "unknowns": ["if CI returns non-zero exit code, local parity was false"],
        "assumptions": ["hook runner is Claude Code"],
        "disconfirmation": "CI fails on main after push or tag verification rejects",
        "constraint_identified": constraint,
        "origin_evidence": "Commit e1f49c9 added this constraint to close CP3 gap #9.",
        "removal_consequence_prediction": (
            "if the deep-scan returns non-zero exit code after removal, "
            "ungrounded entities slip past Layer 3"
        ),
        "reversibility_classification": "reversible",
        "rollback_path": "git revert HEAD and rerun PYTHONPATH=. pytest -q tests/",
    }


def _valid_cascade_surface(**overrides) -> dict:
    surface = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "core_question": "Does the cascade resolve coherently across its blast radius?",
        "knowns": ["baseline suite green before the edit"],
        "unknowns": ["if the cross-surface orphan-reference detector lands v1.0.1"],
        "assumptions": ["hook runner is Claude Code"],
        "disconfirmation": "CI fails or the test suite regresses below baseline",
        "flaw_classification": "schema-implementation-drift",
        "posture_selected": "refactor",
        "patch_vs_refactor_evaluation": (
            "Refactor required because the drift crosses hooks, schemas, "
            "and the CLI; a patch would entangle module layers."
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
        "deferred_discoveries": [],
    }
    surface.update(overrides)
    return surface


def _run_guard(surface, cwd, command, tool_use_id="test-use-id"):
    (cwd / ".episteme").mkdir(exist_ok=True)
    (cwd / ".episteme" / "reasoning-surface.json").write_text(
        json.dumps(surface), encoding="utf-8"
    )
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(cwd),
    }
    if tool_use_id is not None:
        payload["tool_use_id"] = tool_use_id
    raw = json.dumps(payload)
    with patch("sys.stdin", new=io.StringIO(raw)), \
         patch("sys.stdout", new=io.StringIO()), \
         patch("sys.stderr", new=io.StringIO()) as fake_err:
        rc = guard.main()
    return rc, "", fake_err.getvalue()


_CASCADE_CMD = "python scripts/apply_cascade_edit.py"
_FENCE_CMD = "rm .episteme/advisory-surface"


def _make_fake_datetime(base: datetime):
    """A stand-in for the guard module's `datetime` name whose `.now()`
    returns a strictly increasing sequence (+2s per call) so successive
    samples land in different second-buckets. Subclasses the real class
    so inherited methods (fromisoformat, the constructor) still work; only
    `now` is overridden. Only the guard module's reference is patched —
    other modules keep the real class."""
    counter = {"n": 0}

    class _FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            v = base + timedelta(seconds=2 * counter["n"])
            counter["n"] += 1
            return v

    return _FakeDT


# ==========================================================================
# §3.1 — pair-signature fallback ladder
# ==========================================================================

class PairSignatureLadder(unittest.TestCase):
    def test_normalize_collapses_ws_expands_tilde_and_caps(self):
        self.assertEqual(fence_synth.normalize("  ls    -la   /x "), "ls -la /x")
        home = os.environ.get("HOME") or str(Path.home())
        self.assertEqual(fence_synth.normalize("cat ~/f"), f"cat {home}/f")
        big = "x" * 9000
        self.assertLessEqual(len(fence_synth.normalize(big).encode("utf-8")), 4096)

    def test_pair_signature_is_timestamp_independent_and_deterministic(self):
        a = fence_synth.pair_signature("sess", "/tmp/p", "ls   -la")
        b = fence_synth.pair_signature("sess", "/tmp/p", "ls -la")
        self.assertEqual(a, b)  # normalize collapses the whitespace diff
        self.assertTrue(a.startswith("s_"))
        self.assertNotEqual(
            a, fence_synth.pair_signature("other", "/tmp/p", "ls -la")
        )

    def test_marker_carries_pair_signature_and_ppid(self):
        with _EphemeralEpistemeHome() as home:
            fence_synth.write_pending_marker(
                _valid_fence_surface(), "h_x", Path("/tmp/p"), "ls -la",
                session_scope="sess-1",
            )
            data = json.loads((home / "state" / "fence_pending" / "h_x.json").read_text())
            self.assertEqual(
                data["pair_signature"],
                fence_synth.pair_signature("sess-1", "/tmp/p", "ls -la"),
            )
            self.assertIsInstance(data["ppid"], int)

    def test_signature_scan_pairs_beyond_bucket_window(self):
        """The headline >5s no-tool_use_id case: none of the Post candidate
        ids reach the Pre marker's second-bucket, but the ts-independent
        signature still pairs (tier 3)."""
        with _EphemeralEpistemeHome() as home:
            cwd = Path("/tmp/sig_scan_cwd")
            cmd = _FENCE_CMD
            scope = "sess-XYZ"
            ts_pre = datetime(2026, 7, 6, 4, 30, 0, tzinfo=timezone.utc)
            pre_cands = fence_synth.candidate_correlation_ids(
                {"cwd": str(cwd)}, cmd, ts_pre.isoformat()
            )
            for c in pre_cands:
                fence_synth.write_pending_marker(
                    _valid_fence_surface(), c, cwd, cmd, session_scope=scope
                )
            ts_post = (ts_pre + timedelta(seconds=30)).isoformat()
            post_payload = {"cwd": str(cwd), "tool_use_id": "toolu_LATE", "session_id": scope}
            post_cands = fence_synth.candidate_correlation_ids(
                post_payload, cmd, ts_post,
                lookback_seconds=fence_synth.POST_LOOKBACK_SECONDS,
                lookahead_seconds=fence_synth.POST_LOOKAHEAD_SECONDS,
            )
            self.assertFalse(set(post_cands) & set(pre_cands))  # tiers 1+2 miss
            sig = fence_synth.pair_signature(scope, str(cwd), cmd)
            env = fence_synth.finalize_on_success_with_fallback(
                post_cands, 0, pair_sig=sig, post_ppid=os.getppid()
            )
            self.assertIsNotNone(env, "signature scan must pair across the >5s gap")
            pending = home / "state" / "fence_pending"
            remaining = list(pending.glob("*.json")) if pending.is_dir() else []
            self.assertEqual(remaining, [], "used marker deleted on use")

    def test_signature_scan_fifo_oldest_first(self):
        with _EphemeralEpistemeHome() as home:
            cwd = Path("/tmp/fifo_cwd")
            cmd = _FENCE_CMD
            scope = "s"
            surface = {
                "constraint_identified": "x", "origin_evidence": "e",
                "removal_consequence_prediction": "c",
                "reversibility_classification": "reversible", "rollback_path": "r",
            }
            now = datetime.now(timezone.utc)
            older = {
                "version": 1, "correlation_id": "h_old",
                "written_at": (now - timedelta(seconds=120)).isoformat(),
                "cwd": str(cwd), "command_redacted": cmd,
                "pair_signature": fence_synth.pair_signature(scope, str(cwd), cmd),
                "ppid": 111, "surface": surface,
            }
            newer = dict(older)
            newer["correlation_id"] = "h_new"
            newer["written_at"] = (now - timedelta(seconds=60)).isoformat()
            pending = home / "state" / "fence_pending"
            pending.mkdir(parents=True, exist_ok=True)
            (pending / "h_old.json").write_text(json.dumps(older))
            (pending / "h_new.json").write_text(json.dumps(newer))
            sig = fence_synth.pair_signature(scope, str(cwd), cmd)
            env = fence_synth.finalize_on_success_with_fallback(
                [], 0, pair_sig=sig, post_ppid=111
            )
            self.assertIsNotNone(env)
            # Oldest paired + deleted first; the newer marker survives.
            remaining = sorted(p.stem for p in pending.glob("*.json"))
            self.assertEqual(remaining, ["h_new"])

    def test_signature_scan_ttl_expired_ignored(self):
        with _EphemeralEpistemeHome() as home:
            cwd = Path("/tmp/ttl_cwd")
            cmd = _FENCE_CMD
            scope = "s"
            old_ts = (
                datetime.now(timezone.utc)
                - timedelta(seconds=fence_synth.MARKER_TTL_SECONDS + 60)
            ).isoformat()
            marker = {
                "version": 1, "correlation_id": "h_stale", "written_at": old_ts,
                "cwd": str(cwd), "command_redacted": cmd,
                "pair_signature": fence_synth.pair_signature(scope, str(cwd), cmd),
                "ppid": os.getppid(),
                "surface": {
                    "constraint_identified": "x", "origin_evidence": "e",
                    "removal_consequence_prediction": "c",
                    "reversibility_classification": "reversible", "rollback_path": "r",
                },
            }
            pending = home / "state" / "fence_pending"
            pending.mkdir(parents=True, exist_ok=True)
            (pending / "h_stale.json").write_text(json.dumps(marker))
            sig = fence_synth.pair_signature(scope, str(cwd), cmd)
            env = fence_synth.finalize_on_success_with_fallback(
                [], 0, pair_sig=sig, post_ppid=os.getppid()
            )
            self.assertIsNone(env, "TTL-expired marker must not pair")

    def test_v1_marker_without_signature_never_matches(self):
        with _EphemeralEpistemeHome() as home:
            cwd = Path("/tmp/v1_cwd")
            cmd = _FENCE_CMD
            # A pre-schema-v2 marker (no pair_signature / ppid field).
            marker = {
                "version": 1, "correlation_id": "h_v1",
                "written_at": datetime.now(timezone.utc).isoformat(),
                "cwd": str(cwd), "command_redacted": cmd,
                "surface": {
                    "constraint_identified": "x", "origin_evidence": "e",
                    "removal_consequence_prediction": "c",
                    "reversibility_classification": "reversible", "rollback_path": "r",
                },
            }
            pending = home / "state" / "fence_pending"
            pending.mkdir(parents=True, exist_ok=True)
            (pending / "h_v1.json").write_text(json.dumps(marker))
            sig = fence_synth.pair_signature("s", str(cwd), cmd)
            env = fence_synth.finalize_on_success_with_fallback(
                [], 0, pair_sig=sig, post_ppid=os.getppid()
            )
            self.assertIsNone(env, "v1 markers must never signature-match")

    def test_ppid_discriminator_prefers_match_but_soft_falls_back(self):
        with _EphemeralEpistemeHome() as home:
            cwd = Path("/tmp/ppid_cwd")
            cmd = _FENCE_CMD
            scope = "s"
            sig = fence_synth.pair_signature(scope, str(cwd), cmd)
            surface = {
                "constraint_identified": "x", "origin_evidence": "e",
                "removal_consequence_prediction": "c",
                "reversibility_classification": "reversible", "rollback_path": "r",
            }
            base = datetime.now(timezone.utc)

            def _write(stem, ppid, offset):
                m = {
                    "version": 1, "correlation_id": stem,
                    "written_at": (base + timedelta(seconds=offset)).isoformat(),
                    "cwd": str(cwd), "command_redacted": cmd,
                    "pair_signature": sig, "ppid": ppid, "surface": surface,
                }
                pending = home / "state" / "fence_pending"
                pending.mkdir(parents=True, exist_ok=True)
                (pending / f"{stem}.json").write_text(json.dumps(m))

            # mismatch is OLDER; match is NEWER. ppid preference beats FIFO.
            _write("h_mismatch", 999, 0)
            _write("h_match", 45319, 60)
            env = fence_synth.finalize_on_success_with_fallback(
                [], 0, pair_sig=sig, post_ppid=45319
            )
            self.assertIsNotNone(env)
            pending = home / "state" / "fence_pending"
            remaining = sorted(p.stem for p in pending.glob("*.json"))
            self.assertEqual(remaining, ["h_mismatch"], "ppid-match preferred over FIFO")

            # Soft fallback: only a mismatched-ppid marker → still pairs.
            env2 = fence_synth.finalize_on_success_with_fallback(
                [], 0, pair_sig=sig, post_ppid=7777
            )
            self.assertIsNotNone(env2, "no ppid match → soft-fall back to FIFO, still pairs")


# ==========================================================================
# §4 — concurrency & filesystem hygiene
# ==========================================================================

def _seed_deferred_dup(home_unused=None):
    """Seed the deferred chain with 2 open duplicates (dedup bypassed) so a
    compaction has something to remove and must take the rewrite path."""
    for obs in ("first occurrence", "second — later duplicate"):
        _framework.write_deferred_discovery(
            {
                "flaw_classification": "config-gap",
                "description": "cascade fires on kernel state file edits",
                "observable": obs,
            },
            dedup=False,
        )


class RewriteMutexAndInode(unittest.TestCase):
    def test_verify_and_reacquire_lands_on_new_inode(self):
        """§4.2 — after a concurrent os.replace orphans the locked fd, the
        re-verify reopens onto the live inode."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.jsonl"
            p.write_text("v1\n", encoding="utf-8")
            fd = open(p, "a+", encoding="utf-8")
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
            orphan_ino = os.fstat(fd.fileno()).st_ino
            swapped = {"done": False}

            def swap():
                if not swapped["done"]:
                    _chain.atomic_replace_file(p, b"v2\n")  # new inode
                    swapped["done"] = True

            newfd = _chain._verify_and_reacquire(fd, p, _after_flock=swap)
            try:
                self.assertEqual(
                    os.fstat(newfd.fileno()).st_ino, os.stat(p).st_ino
                )
                self.assertNotEqual(os.fstat(newfd.fileno()).st_ino, orphan_ino)
            finally:
                try:
                    fcntl.flock(newfd.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
                if not newfd.closed:
                    newfd.close()

    def test_verify_and_reacquire_gives_up_after_max_attempts(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.jsonl"
            p.write_text("v1\n", encoding="utf-8")
            fd = open(p, "a+", encoding="utf-8")
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX)
            n = {"i": 0}

            def always_swap():
                n["i"] += 1
                _chain.atomic_replace_file(p, f"v{n['i']}\n".encode("utf-8"))

            with self.assertRaises(_chain.ChainError):
                _chain._verify_and_reacquire(
                    fd, p, _after_flock=always_swap, max_attempts=3
                )

    def test_locked_reacquires_under_staged_swap(self):
        """The `_locked` contextmanager threads the seam and completes; an
        append inside the block lands in the live (swapped) file and the
        chain stays intact."""
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "c.jsonl"
            _chain.append(p, {"type": "protocol", "n": 0})
            swapped = {"done": False}

            def swap():
                if not swapped["done"]:
                    # Replace with a fresh single-record chain (new inode).
                    tmp = Path(d) / "seed.jsonl"
                    _chain.append(tmp, {"type": "protocol", "n": 99})
                    _chain.atomic_replace_file(p, tmp.read_bytes())
                    swapped["done"] = True

            with _chain._locked(p, _after_first_flock=swap):
                pass  # re-verify happens on flock acquisition
            self.assertTrue(_chain.verify_chain(p).intact)

    def test_rewrite_lock_is_exclusive(self):
        with tempfile.TemporaryDirectory() as d:
            lock_dir = Path(d)
            with _chain.rewrite_lock(lock_dir):
                probe = os.open(str(lock_dir / ".lock"), os.O_CREAT | os.O_RDWR)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    os.close(probe)
            # After release the same lock acquires cleanly.
            probe2 = os.open(str(lock_dir / ".lock"), os.O_CREAT | os.O_RDWR)
            try:
                fcntl.flock(probe2, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(probe2, fcntl.LOCK_UN)
            finally:
                os.close(probe2)

    def _lock_order_spy(self, compaction_call):
        order: list[str] = []
        real_rw = _chain.rewrite_lock
        real_lk = _chain._locked

        @contextmanager
        def spy_rw(lock_dir):
            order.append("rewrite")
            with real_rw(lock_dir):
                yield

        @contextmanager
        def spy_lk(path, **kw):
            order.append("locked")
            with real_lk(path, **kw):
                yield

        with patch.object(_framework, "_rewrite_lock", spy_rw), \
             patch.object(_framework, "_chain_locked", spy_lk):
            result = compaction_call()
        return order, result

    def test_compact_deferred_takes_rewrite_lock_then_file_lock(self):
        with _EphemeralEpistemeHome():
            _seed_deferred_dup()
            order, result = self._lock_order_spy(
                _framework.compact_deferred_discoveries
            )
            self.assertEqual(result.status, "compacted")
            # Lock-order law: rewrite mutex acquired BEFORE the per-file lock.
            self.assertEqual(order[:2], ["rewrite", "locked"])

    def test_compact_protocols_takes_rewrite_lock_then_file_lock(self):
        with _EphemeralEpistemeHome():
            # Two identical legacy cascade records (no cascade_hash) collapse.
            for _ in range(2):
                _framework.write_protocol({
                    "type": "protocol", "blueprint": "architectural_cascade",
                    "source_fields": {
                        "flaw_classification": "config-gap",
                        "posture_selected": "patch",
                        "blast_radius_surfaces": ["core/hooks/a.py"],
                        "observable": "exit_code == 0 held",
                    },
                    "op_outcome": {"exit_code": 0, "cwd": "/tmp/proj", "command_redacted": "x"},
                    "synthesized_protocol": "p",
                })
            order, result = self._lock_order_spy(_framework.compact_protocols)
            self.assertEqual(result.status, "compacted")
            self.assertEqual(order[:2], ["rewrite", "locked"])


# ==========================================================================
# §3.2 — single per-op timestamp
# ==========================================================================

class SinglePerOpTimestamp(unittest.TestCase):
    def test_cascade_marker_uses_single_first_op_ts(self):
        """The guard samples ONE wall-clock per admitted op and threads it
        to every correlation-id write. With now() mocked to increment +2s
        per call, the cascade pending marker must carry the FIRST sample's
        second-bucket (op_ts). Pre-fix the marker used a second independent
        `_marker_ts` (a later now() call) → a different bucket whenever the
        two samples straddle a second boundary."""
        base = datetime(2026, 7, 6, 4, 30, 0, tzinfo=timezone.utc)
        surface = _valid_cascade_surface()
        with _EphemeralEpistemeHome() as home, tempfile.TemporaryDirectory() as d:
            cwd = Path(d)
            cmd = _CASCADE_CMD
            with patch.object(guard, "datetime", _make_fake_datetime(base)):
                rc, _, err = _run_guard(surface, cwd, cmd, tool_use_id=None)
            self.assertEqual(rc, 0, err)
            markers = sorted(
                p.stem for p in (home / "state" / "cascade_pending").glob("*.json")
            )
            self.assertEqual(len(markers), 1, markers)
            expected = fence_synth._h_correlation_for_bucket(
                base.isoformat().split(".")[0], str(cwd), cmd
            )
            self.assertEqual(
                markers[0], expected,
                "cascade marker must derive from the first (single) op_ts sample",
            )


# ==========================================================================
# §5.1 — read-side legacy healing (no payload mutation)
# ==========================================================================

class ReadSideLegacyHealing(unittest.TestCase):
    def test_legacy_no_field_record_suppresses_modern_emission(self):
        """A legacy cascade record with NO stored `cascade_hash` must
        suppress an identical modern emission — via the shared
        `_cascade_content_key` (recompute-on-absence), with zero payload
        mutation. Pre-fix the emit dedup keyed on the raw `cascade_hash`
        field, so the legacy record (field absent) never matched and the
        duplicate re-emitted."""
        with _EphemeralEpistemeHome():
            marker = {
                "version": 1,
                "correlation_id": "h_heal",
                "written_at": datetime.now(timezone.utc).isoformat(),
                "cwd": "/tmp/heal_proj",
                "command_redacted": "make test",
                "surface": {
                    "flaw_classification": "config-gap",
                    "posture_selected": "patch",
                    "core_question": "does the flaw recur across surfaces?",
                    "needs_update_surfaces": ["core/hooks/a.py", "core/hooks/b.py"],
                    "observable": "exit_code == 0 held",
                },
            }
            # The exact payload the emit path would write (carries cascade_hash).
            modern = cascade_synth.build_protocol_for_tests(marker, 0)
            self.assertIn("cascade_hash", modern)
            # Seed a LEGACY twin: identical content, cascade_hash field absent.
            legacy = {k: v for k, v in modern.items() if k != "cascade_hash"}
            _framework.write_protocol(legacy)
            self.assertEqual(len(_read_protocol_lines()), 1)

            # Stage the pending marker + finalize on success.
            pd = cascade_synth.pending_dir_for_tests()
            pd.mkdir(parents=True, exist_ok=True)
            (pd / "h_heal.json").write_text(json.dumps(marker), encoding="utf-8")
            env = cascade_synth.finalize_on_success_with_fallback(["h_heal"], 0)

            self.assertIsNone(
                env, "identical modern emission must be suppressed by the legacy twin"
            )
            self.assertEqual(
                len(_read_protocol_lines()), 1,
                "no duplicate appended — read-side healing keyed on content",
            )


def _read_protocol_lines():
    p = _framework._protocols_path()
    if not p.is_file():
        return []
    return [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ==========================================================================
# §5.2 — namespace symmetry (both compaction entry points)
# ==========================================================================

class NamespaceSymmetry(unittest.TestCase):
    def _run_cli(self, home: Path, *args: str) -> subprocess.CompletedProcess:
        env = {
            **os.environ,
            "EPISTEME_HOME": str(home),
            "PYTHONPATH": str(_REPO_ROOT / "src"),
        }
        return subprocess.run(
            [sys.executable, "-m", "episteme.cli", *args],
            env=env, cwd=str(_REPO_ROOT), capture_output=True, text=True,
        )

    def _seed(self):
        for i in range(4):
            _framework.write_protocol({
                "type": "protocol", "blueprint": "architectural_cascade",
                "correlation_id": f"c-{i}",
                "source_fields": {
                    "flaw_classification": "config-gap",
                    "posture_selected": "patch",
                    "blast_radius_surfaces": ["core/hooks/a.py"],
                    "observable": "one cli resolution",
                },
                "op_outcome": {"exit_code": 0, "cwd": "/tmp/proj", "command_redacted": "x"},
                "synthesized_protocol": "p",
            })

    def test_both_entry_points_produce_identical_result(self):
        with _EphemeralEpistemeHome() as home:
            self._seed()
            k = self._run_cli(home, "kernel", "compact-protocols", "--dry-run", "--json")
            self.assertEqual(k.returncode, 0, k.stderr)
            c = self._run_cli(home, "chain", "compact", "--stream", "protocols",
                              "--dry-run", "--json")
            self.assertEqual(c.returncode, 0, c.stderr)
            kobj, cobj = json.loads(k.stdout), json.loads(c.stdout)
            for field in ("status", "total_before", "total_after", "removed"):
                self.assertEqual(kobj[field], cobj[field], field)
            self.assertEqual(cobj["status"], "compacted")
            self.assertEqual(cobj["removed"], 3)

    def test_chain_compact_default_stream_unchanged(self):
        """`chain compact` with no --stream still targets deferred_discoveries."""
        with _EphemeralEpistemeHome() as home:
            _seed_deferred_dup()
            c = self._run_cli(home, "chain", "compact", "--dry-run")
            self.assertEqual(c.returncode, 0, c.stderr)
            self.assertIn("total_before=2", c.stdout)


if __name__ == "__main__":
    unittest.main()
