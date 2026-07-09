"""Marker GC reaper — Event 146.

Tests the TTL-based unlink of orphaned pairing markers in
``state/cascade_pending`` + ``state/fence_pending``, and its SessionStart
wiring. The live failure this guards against: pairing markers leaked
unbounded (cascade_pending ~689 files, fence_pending 235, oldest 75x past
TTL) because ``MARKER_TTL_SECONDS`` gated marker READS only — a Pre marker
whose Post never pairs was orphaned forever, and ``_signature_scan``
re-globbed + parsed every leaked file on each admitted Post hook.

Single-handler (Event 145 B1): ``core/hooks/_marker_reaper.py`` is the one
sweep implementation shared by the SessionStart hook
(``session_context._reaper_line``) and the CLI tool
(``tools/fence_marker_cleanup.py``). These tests exercise the shared
implementation and the hook seam; the tool's entry-point wiring is
covered by a subprocess smoke test.

All state is written under a tmp ``EPISTEME_HOME`` — never ``~/.episteme``.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from core.hooks import _marker_reaper as reaper  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import _fence_synthesis as fence_synth  # pyright: ignore[reportAttributeAccessIssue]
from core.hooks import session_context as sc  # pyright: ignore[reportAttributeAccessIssue]

_TTL = fence_synth.MARKER_TTL_SECONDS
_REPO_ROOT = Path(__file__).resolve().parents[1]


class _TmpHome:
    """Point EPISTEME_HOME at a fresh tmp dir for the duration."""

    def __enter__(self) -> Path:
        self._td = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("EPISTEME_HOME")
        os.environ["EPISTEME_HOME"] = self._td.name
        return Path(self._td.name)

    def __exit__(self, *a) -> None:
        if self._prev is None:
            os.environ.pop("EPISTEME_HOME", None)
        else:
            os.environ["EPISTEME_HOME"] = self._prev
        self._td.cleanup()


def _fence_dir() -> Path:
    return reaper.fence_pending_dir_for_tests()


def _cascade_dir() -> Path:
    return reaper.cascade_pending_dir_for_tests()


def _write_marker(d: Path, name: str, written_at: datetime) -> Path:
    """Write a well-formed marker whose payload ``written_at`` sets its age."""
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    p.write_text(
        json.dumps(
            {
                "version": 2,
                "correlation_id": name,
                "written_at": written_at.isoformat(),
                "cwd": "/x",
                "pair_signature": f"s_{name}",
            }
        ),
        encoding="utf-8",
    )
    return p


def _write_malformed(d: Path, name: str, mtime_epoch: float) -> Path:
    """Write an unparseable-JSON marker and stamp its mtime for age-by-mtime."""
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.json"
    p.write_text("{ this is not valid json", encoding="utf-8")
    os.utime(p, (mtime_epoch, mtime_epoch))
    return p


# ---------------------------------------------------------------------------
# TTL boundary (well-formed markers, age from written_at)
# ---------------------------------------------------------------------------


class TTLBoundary(unittest.TestCase):
    def test_just_under_ttl_stays_just_over_reaped(self):
        with _TmpHome():
            now = datetime.now(timezone.utc)
            d = _fence_dir()
            under = _write_marker(d, "under", now - timedelta(seconds=_TTL - 1))
            over = _write_marker(d, "over", now - timedelta(seconds=_TTL + 1))
            res = reaper.reap_dir(d, now=now)
            self.assertTrue(under.exists(), "marker just under TTL must survive")
            self.assertFalse(over.exists(), "marker just over TTL must be unlinked")
            self.assertEqual(res.reaped, 1)
            self.assertEqual(res.kept, 1)
            self.assertEqual(res.malformed_reaped, 0)


# ---------------------------------------------------------------------------
# Fresh + stale mix
# ---------------------------------------------------------------------------


class FreshStaleMix(unittest.TestCase):
    def test_only_stale_reaped_fresh_untouched(self):
        with _TmpHome():
            now = datetime.now(timezone.utc)
            d = _fence_dir()
            fresh = _write_marker(d, "fresh", now - timedelta(minutes=5))
            stale1 = _write_marker(d, "stale1", now - timedelta(days=3))
            stale2 = _write_marker(d, "stale2", now - timedelta(days=75))
            res = reaper.reap_dir(d, now=now)
            self.assertTrue(fresh.exists(), "pairing-eligible fresh marker untouched")
            self.assertFalse(stale1.exists())
            self.assertFalse(stale2.exists())
            self.assertEqual(res.reaped, 2)
            self.assertEqual(res.kept, 1)


# ---------------------------------------------------------------------------
# Concurrency — vanishing file mid-sweep
# ---------------------------------------------------------------------------


class VanishingFile(unittest.TestCase):
    def test_age_probe_on_missing_file_no_crash(self):
        with _TmpHome():
            d = _fence_dir()
            d.mkdir(parents=True, exist_ok=True)
            missing = d / "gone.json"
            age, malformed = reaper._marker_age_seconds(
                missing, datetime.now(timezone.utc)
            )
            self.assertIsNone(age)
            self.assertFalse(malformed)

    def test_delete_between_scan_and_unlink_no_exception(self):
        with _TmpHome():
            now = datetime.now(timezone.utc)
            d = _fence_dir()
            _write_marker(d, "racey", now - timedelta(days=2))

            def _boom(self, *a, **k):  # a parallel session paired/removed it
                raise FileNotFoundError(self)

            with patch.object(Path, "unlink", _boom):
                res = reaper.reap_dir(d, now=now)  # must not raise
            self.assertEqual(res.reaped, 0)
            self.assertGreaterEqual(res.vanished, 1)


# ---------------------------------------------------------------------------
# Malformed markers (unparseable JSON)
# ---------------------------------------------------------------------------


class MalformedMarkers(unittest.TestCase):
    def test_malformed_old_by_mtime_reaped_and_counted(self):
        with _TmpHome():
            d = _fence_dir()
            old_mtime = (
                datetime.now(timezone.utc) - timedelta(seconds=_TTL + 3600)
            ).timestamp()
            p = _write_malformed(d, "bad", old_mtime)
            res = reaper.reap_dir(d)
            self.assertFalse(p.exists())
            self.assertEqual(res.reaped, 1)
            self.assertEqual(res.malformed_reaped, 1)

    def test_malformed_fresh_by_mtime_kept(self):
        # Refinement over the pre-Event-146 tool, which reaped malformed
        # markers unconditionally: a malformed file younger than TTL by
        # mtime is KEPT (loss-averse — do not unlink a recent artifact).
        with _TmpHome():
            d = _fence_dir()
            fresh_mtime = (
                datetime.now(timezone.utc) - timedelta(minutes=10)
            ).timestamp()
            p = _write_malformed(d, "bad_fresh", fresh_mtime)
            res = reaper.reap_dir(d)
            self.assertTrue(p.exists(), "fresh malformed marker must survive")
            self.assertEqual(res.reaped, 0)
            self.assertEqual(res.kept, 1)


# ---------------------------------------------------------------------------
# Empty / missing dirs
# ---------------------------------------------------------------------------


class EmptyAndMissing(unittest.TestCase):
    def test_missing_dir_is_noop(self):
        with _TmpHome():
            d = _fence_dir()  # never created
            self.assertFalse(d.exists())
            res = reaper.reap_dir(d)
            self.assertEqual((res.reaped, res.kept, res.vanished), (0, 0, 0))

    def test_empty_dir_is_noop(self):
        with _TmpHome():
            d = _fence_dir()
            d.mkdir(parents=True, exist_ok=True)
            res = reaper.reap_dir(d)
            self.assertEqual((res.reaped, res.kept, res.vanished), (0, 0, 0))


# ---------------------------------------------------------------------------
# reap_all — both dirs + single-source TTL
# ---------------------------------------------------------------------------


class ReapAll(unittest.TestCase):
    def test_both_dirs_swept(self):
        with _TmpHome():
            now = datetime.now(timezone.utc)
            stale = now - timedelta(days=2)
            fresh = now - timedelta(minutes=1)
            _write_marker(_cascade_dir(), "c_stale", stale)
            _write_marker(_cascade_dir(), "c_fresh", fresh)
            _write_marker(_fence_dir(), "f_stale", stale)
            results = reaper.reap_all(now=now)
            self.assertEqual(results["cascade"].reaped, 1)
            self.assertEqual(results["cascade"].kept, 1)
            self.assertEqual(results["fence"].reaped, 1)
            self.assertFalse((_cascade_dir() / "c_stale.json").exists())
            self.assertTrue((_cascade_dir() / "c_fresh.json").exists())
            self.assertFalse((_fence_dir() / "f_stale.json").exists())

    def test_ttl_is_single_source(self):
        # The reaper reuses the constant from _fence_synthesis — one age
        # boundary, no divergent copy.
        self.assertEqual(reaper.MARKER_TTL_SECONDS, fence_synth.MARKER_TTL_SECONDS)

    def test_format_summary_wording(self):
        with _TmpHome():
            now = datetime.now(timezone.utc)
            stale = now - timedelta(days=2)
            _write_marker(_cascade_dir(), "c1", stale)
            _write_marker(_fence_dir(), "f1", stale)
            results = reaper.reap_all(now=now)
            summary = reaper.format_summary(results)
            self.assertIn("1 cascade", summary)
            self.assertIn("1 fence", summary)


# ---------------------------------------------------------------------------
# SessionStart invocation path
# ---------------------------------------------------------------------------


class SessionContextInvocation(unittest.TestCase):
    def test_reaper_line_executes_sweep_and_reports(self):
        with _TmpHome():
            now = datetime.now(timezone.utc)
            f_stale = _write_marker(_fence_dir(), "f_stale", now - timedelta(days=2))
            c_stale = _write_marker(
                _cascade_dir(), "c_stale", now - timedelta(days=2)
            )
            line = sc._reaper_line()
            # The sweep is the load-bearing side effect: both stale markers
            # are unlinked, not merely reported.
            self.assertFalse(f_stale.exists())
            self.assertFalse(c_stale.exists())
            assert line is not None
            self.assertIn("marker-gc", line)
            self.assertIn("1 cascade", line)
            self.assertIn("1 fence", line)

    def test_reaper_line_silent_on_zero(self):
        with _TmpHome():
            # No markers → nothing reaped → banner silent (return None),
            # matching the other producers' silent-on-zero convention.
            self.assertIsNone(sc._reaper_line())

    def test_reaper_line_silent_when_only_fresh(self):
        with _TmpHome():
            now = datetime.now(timezone.utc)
            _write_marker(_fence_dir(), "fresh", now - timedelta(minutes=1))
            self.assertIsNone(sc._reaper_line())


# ---------------------------------------------------------------------------
# CLI tool entry point (single-handler seam)
# ---------------------------------------------------------------------------


class CliTool(unittest.TestCase):
    def test_tool_sweeps_via_shared_reaper(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            now = datetime.now(timezone.utc)
            stale = home / "state" / "fence_pending" / "old.json"
            stale.parent.mkdir(parents=True, exist_ok=True)
            stale.write_text(
                json.dumps(
                    {"written_at": (now - timedelta(days=2)).isoformat()}
                ),
                encoding="utf-8",
            )
            env = dict(os.environ, EPISTEME_HOME=str(home))
            proc = subprocess.run(
                [sys.executable, str(_REPO_ROOT / "tools" / "fence_marker_cleanup.py")],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertFalse(stale.exists(), "tool must reap the stale marker")
            self.assertIn("marker_cleanup:", proc.stderr)

    def _run_with_stale_marker(self, args):
        """Run the tool with `args` against a temp home holding one stale
        marker; return (proc, marker_path). The caller asserts on whether the
        marker survived (survived ⇒ no sweep ran)."""
        td = tempfile.mkdtemp()
        home = Path(td)
        now = datetime.now(timezone.utc)
        stale = home / "state" / "fence_pending" / "old.json"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text(
            json.dumps({"written_at": (now - timedelta(days=2)).isoformat()}),
            encoding="utf-8",
        )
        env = dict(os.environ, EPISTEME_HOME=str(home))
        proc = subprocess.run(
            [sys.executable, str(_REPO_ROOT / "tools" / "fence_marker_cleanup.py"), *args],
            capture_output=True,
            text=True,
            env=env,
        )
        return proc, stale

    def test_help_flag_prints_usage_and_does_not_sweep(self):
        # Event 148 · smallfix #3: --help must exit 0 without running the sweep.
        proc, stale = self._run_with_stale_marker(["--help"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("usage", proc.stdout.lower())
        self.assertTrue(stale.exists(), "--help must NOT reap markers (no sweep)")
        self.assertNotIn("vanished=", proc.stderr)  # sweep-summary token, absent ⇒ no sweep

    def test_short_help_flag_does_not_sweep(self):
        proc, stale = self._run_with_stale_marker(["-h"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(stale.exists(), "-h must NOT reap markers (no sweep)")

    def test_unknown_flag_exits_2_and_does_not_sweep(self):
        proc, stale = self._run_with_stale_marker(["--bogus"])
        self.assertEqual(proc.returncode, 2, proc.stdout)
        self.assertTrue(stale.exists(), "unknown flag must NOT reap markers (no sweep)")
        self.assertNotIn("vanished=", proc.stderr)  # sweep-summary token, absent ⇒ no sweep


if __name__ == "__main__":
    unittest.main()
