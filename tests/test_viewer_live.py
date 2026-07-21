"""Event 174 — viewer revival: live readers, advisory log, HTTP endpoints.

The readers are pure functions over injected roots; the HTTP layer is tested
against a REAL ThreadingHTTPServer on an ephemeral port (no mocked handlers —
the regression this guards is the E172 class, where a surface only ever
worked from one accidental context).
"""

from __future__ import annotations

import io
import json
import subprocess
import threading
import unittest
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.hooks import workflow_guard
from episteme.viewer import live


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TailJsonlTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_missing_file_yields_empty(self):
        self.assertEqual(live.tail_jsonl(self.root / "nope.jsonl", 10), [])

    def test_tail_returns_last_n_parseable_oldest_first(self):
        lines = [json.dumps({"i": i}) for i in range(20)] + ["{broken", ""]
        _write(self.root, "s.jsonl", "\n".join(lines) + "\n")
        out = live.tail_jsonl(self.root / "s.jsonl", 5)
        self.assertEqual([o["i"] for o in out], [15, 16, 17, 18, 19])

    def test_large_file_reads_are_byte_bounded(self):
        # A file far beyond the tail cap must still return the newest lines.
        big = "\n".join(json.dumps({"i": i, "pad": "x" * 200}) for i in range(5000))
        _write(self.root, "big.jsonl", big + "\n")
        out = live.tail_jsonl(self.root / "big.jsonl", 3)
        self.assertEqual([o["i"] for o in out], [4997, 4998, 4999])


class GlobalStatusTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_empty_home_degrades_to_zeroes(self):
        g = live.global_status(self.home)
        self.assertEqual(g["gate_ops_24h"], 0)
        self.assertEqual(g["spot_check_queue"], 0)
        self.assertEqual(g["framework"], {"protocols": 0, "deferred_discoveries": 0})

    def test_counts_come_from_state_files_using_the_real_audit_schema(self):
        # The canonical audit writer emits "status"/"action", NOT
        # decision/verdict — the first version of this test invented a schema
        # and the review caught the panel dead against real records. This
        # test now pins the REAL field names.
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        _write(
            self.home,
            "audit.jsonl",
            "\n".join(
                json.dumps({"timestamp": now, "status": s})
                for s in ["ok", "ok", "incomplete"]
            )
            + "\n",
        )
        _write(self.home, "framework/protocols.jsonl", '{"a":1}\n{"a":2}\n')
        _write(self.home, "state/spot_check_queue.jsonl", '{"q":1}\n')
        _write(self.home, "derived_knobs.json", '{"noise_watch_set": ["status-pressure"]}')
        g = live.global_status(self.home)
        self.assertEqual(g["gate_ops_24h"], 3)
        self.assertEqual(g["gate_verdicts_24h"], {"ok": 2, "incomplete": 1})
        self.assertEqual(g["framework"]["protocols"], 2)
        self.assertEqual(g["spot_check_queue"], 1)
        self.assertEqual(g["noise_watch"], ["status-pressure"])

    def test_real_corpus_verdict_keys_are_not_all_unknown(self):
        # Guard against schema drift between the audit writer and this
        # reader: on the operator's real audit.jsonl (when present and
        # active in the last 24h), the verdict breakdown must contain at
        # least one canonical key — a panel of only 'unknown' means the
        # reader's field names diverged from the writer's again.
        g = live.global_status()
        if g["gate_ops_24h"] == 0:
            self.skipTest("no gated ops in the last 24h on this machine")
        self.assertTrue(
            set(g["gate_verdicts_24h"]) - {"unknown"},
            f"all verdicts unknown: {g['gate_verdicts_24h']}",
        )


class ProjectStatusTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)

    def test_bare_project_degrades(self):
        p = live.project_status(self.root)
        self.assertFalse(p["surface"]["exists"])
        self.assertEqual(p["advisories_recent"], 0)

    def test_naive_surface_timestamp_must_not_raise(self):
        # Review disconfirmation scenario: a hand-edited surface with a
        # zone-less timestamp made `now - ts` raise TypeError, 500 the
        # route, and blank the whole dashboard. _parse_ts now coerces to
        # UTC; this pins the no-raise contract on untrusted input.
        _write(
            self.root,
            ".episteme/reasoning-surface.json",
            json.dumps({"timestamp": "2026-01-01T00:00:00", "core_question": "Q"}),
        )
        p = live.project_status(self.root)
        self.assertTrue(p["surface"]["exists"])
        self.assertFalse(p["surface"]["fresh"])  # months old once coerced
        self.assertIsNotNone(p["surface"]["age_minutes"])

    def test_surface_and_staleness_render(self):
        from datetime import datetime, timezone

        _write(
            self.root,
            ".episteme/reasoning-surface.json",
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "core_question": "Q?",
                    "posture_selected": "patch",
                }
            ),
        )
        _write(self.root, "docs/EVENTS.md", "| E20 | d | x | r |\n")
        _write(
            self.root,
            "docs/OLD.md",
            "<!-- episteme-lifecycle: status=living; reviewed_as_of=E1 -->\n# old\n",
        )
        _write(
            self.root,
            "docs/NEW.md",
            "<!-- episteme-lifecycle: status=living; reviewed_as_of=E20 -->\n# new\n",
        )
        p = live.project_status(self.root)
        self.assertTrue(p["surface"]["exists"])
        self.assertTrue(p["surface"]["fresh"])
        ds = p["doc_staleness"]
        self.assertEqual(ds["latest_event"], 20)
        self.assertEqual(ds["living_docs"], 2)
        self.assertEqual(ds["stale_docs"], 1)  # E1 is 19 events behind
        self.assertEqual(ds["worst_lag_events"], 19)


class AdvisoryLogTests(unittest.TestCase):
    """workflow_guard's JSONL feed: footprint rule, shape, rotation cap."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)

    def _log_path(self) -> Path:
        return self.root / ".episteme" / "state" / "doc_advisories.jsonl"

    def test_no_log_without_episteme_dir(self):
        workflow_guard._log_advisory(self.root, "src/a.py", ["docs/A.md"])
        self.assertFalse(self._log_path().exists())

    def test_appends_shape_and_reads_back_via_live(self):
        (self.root / ".episteme").mkdir()
        workflow_guard._log_advisory(self.root, "src/a.py", ["docs/A.md", "docs/B.md"])
        records = live.advisories(self.root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["path"], "src/a.py")
        self.assertEqual(records[0]["docs"], ["docs/A.md", "docs/B.md"])
        self.assertEqual(records[0]["doc_count"], 2)
        self.assertIn("ts", records[0])

    def test_rotation_keeps_newest_lines(self):
        (self.root / ".episteme").mkdir()
        with patch.object(workflow_guard, "_ADVISORY_LOG_MAX_BYTES", 2_000), patch.object(
            workflow_guard, "_ADVISORY_LOG_KEEP_LINES", 5
        ):
            for i in range(50):
                workflow_guard._log_advisory(self.root, f"src/f{i}.py", ["docs/A.md"])
        lines = self._log_path().read_text(encoding="utf-8").strip().splitlines()
        self.assertLessEqual(len(lines), 6)  # keep-lines + at most one append
        self.assertIn("f49", lines[-1])

    def test_hook_end_to_end_writes_the_feed(self):
        # Real main(): a citing doc + a git repo + .episteme -> advisory + log.
        _write(self.root, "AGENTS.md", "# agents\n")
        _write(self.root, "src/app.py", "pass\n")
        _write(self.root, "docs/APP.md", "Entry point: `src/app.py`.\n")
        (self.root / ".episteme").mkdir()
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        payload = json.dumps(
            {
                "tool_name": "Edit",
                "tool_input": {"file_path": str(self.root / "src" / "app.py")},
                "session_type": "main",
                "cwd": str(self.root),
            }
        )
        with patch("sys.stdin", new=io.StringIO(payload)), patch(
            "sys.stdout", new=io.StringIO()
        ):
            self.assertEqual(workflow_guard.main(), 0)
        records = live.advisories(self.root)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["docs"], ["docs/APP.md"])


class ParentWatchTests(unittest.TestCase):
    """--exit-with-parent: the viewer must die when its spawner dies (E176).

    Reproduces the orphan the app-shell smoke found: SIGKILL on the shell
    bypasses window-close cleanup, so the CHILD must notice the reparenting.
    A middleman process spawns the viewer with the flag and exits; the
    viewer must shut down within the watch poll interval.
    """

    def test_orphaned_viewer_shuts_down(self):
        import os
        import socket
        import sys
        import time

        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

        middleman = (
            "import subprocess, sys, time\n"
            "subprocess.Popen([sys.executable, '-c', "
            "'from episteme.viewer.server import serve; "
            f"serve(port={port}, open_browser=False, exit_with_parent=True)'])\n"
            "time.sleep(2.5)\n"  # boot + real-ppid sample margin (CI-load headroom)
        )
        env = dict(os.environ)
        src = str(Path(__file__).resolve().parents[1] / "src")
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
        subprocess.run([sys.executable, "-c", middleman], env=env, timeout=30)
        # middleman has exited; the viewer is now orphaned

        def port_open() -> bool:
            with socket.socket() as probe:
                probe.settimeout(0.3)
                return probe.connect_ex(("127.0.0.1", port)) == 0

        deadline = time.time() + 8  # watch polls every 2s
        was_up = port_open()
        while port_open() and time.time() < deadline:
            time.sleep(0.5)
        self.assertTrue(was_up, "viewer never came up — test setup broken")
        self.assertFalse(port_open(), "orphaned viewer still serving after 8s")


class HttpEndpointTests(unittest.TestCase):
    """The real server on an ephemeral port — routes, JSON shape, index.html."""

    @classmethod
    def setUpClass(cls):
        from episteme.viewer import server as viewer_server
        from http.server import ThreadingHTTPServer

        cls._server = ThreadingHTTPServer(("127.0.0.1", 0), viewer_server._Handler)
        cls._port = cls._server.server_address[1]
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()

    def _get(self, path: str):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self._port}{path}", timeout=5
        ) as res:
            return res.status, res.read().decode("utf-8"), res.headers

    def test_index_html_is_served_not_the_missing_stub(self):
        status, body, _ = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("operator console", body)
        self.assertNotIn("index.html missing", body)

    def test_live_global_returns_json_shape(self):
        status, body, headers = self._get("/api/live/global")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        payload = json.loads(body)
        for key in ("gate_ops_24h", "spot_check_queue", "framework", "noise_watch"):
            self.assertIn(key, payload)

    def test_live_project_returns_json_shape(self):
        status, body, _ = self._get("/api/live/project")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        for key in ("name", "branch", "surface", "doc_map", "doc_staleness"):
            self.assertIn(key, payload)

    def test_live_advisories_returns_list(self):
        status, body, _ = self._get("/api/live/advisories")
        self.assertEqual(status, 200)
        self.assertIsInstance(json.loads(body), list)


if __name__ == "__main__":
    unittest.main()
