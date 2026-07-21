"""Event 175 — viewer control plane: defense ladder, tiers, execution.

Every rung of the defense ladder is tested independently against the REAL
server (ephemeral port): non-loopback disable, Host allowlist, session
token. The tier boundary is tested as an ABSENCE: Tier 3 commands must not
exist in the executable registry — the missing endpoint is the enforcement.
"""

from __future__ import annotations

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from episteme.viewer import control, server as viewer_server


class RegistryTests(unittest.TestCase):
    def test_positive_system_tiers(self):
        tiers = {a.tier for a in control.ACTIONS.values()}
        self.assertEqual(tiers, {1, 2})

    def test_tier3_commands_are_not_executable(self):
        # The governance boundary: every Tier 3 catalog command must be
        # absent from the executable registry.
        executable_cmds = {" ".join(a.argv) for a in control.ACTIONS.values()}
        for entry in control.TIER3_CATALOG:
            bare = entry["command"].removeprefix("episteme ").split(" <")[0]
            self.assertNotIn(bare, executable_cmds, entry["command"])

    def test_unknown_action_is_refused(self):
        result = control.run_action("rm_rf_everything", cwd=".")
        self.assertEqual(result["error"], "unknown_action")

    def test_action_failure_returns_clean_json_not_a_traceback(self):
        # Review disconfirmation: docmap_rebuild in a non-git cwd raised
        # RuntimeError straight through do_POST as a raw 500. Every action
        # failure must come back as structured JSON, and the lock must be
        # free afterward.
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            result = control.run_action("docmap_rebuild", cwd=tmp)
        self.assertEqual(result["error"], "action_failed")
        self.assertIn("RuntimeError", result["detail"])
        self.assertTrue(control._run_lock.acquire(blocking=False))
        control._run_lock.release()

    def test_control_enabled_defaults_fail_closed(self):
        # The kill-switch must default OFF; only serve() may enable it after
        # confirming a loopback bind (review finding: fail-open posture).
        # Fresh interpreter — reload() here would remint the shared server's
        # SESSION_TOKEN under the HTTP tests' feet.
        import subprocess as sp

        probe = sp.run(
            [sys.executable, "-c",
             "from episteme.viewer import server; print(server.CONTROL_ENABLED)"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(probe.stdout.strip(), "False", probe.stderr)

    def test_busy_lock_single_flight(self):
        acquired = control._run_lock.acquire()
        try:
            result = control.run_action("doctor", cwd=".")
            self.assertEqual(result["error"], "busy")
        finally:
            if acquired:
                control._run_lock.release()

    def test_truncation_is_marked_never_silent(self):
        oversized = control.OUTPUT_CAP_BYTES + 100
        with patch.object(control, "_cli_argv") as argv:
            argv.return_value = [sys.executable, "-c", f"print('x' * {oversized})"]
            result = control.run_action("doctor", cwd=".")
        self.assertTrue(result["truncated"])
        self.assertIn(control.TRUNCATION_MARKER.strip(), result["output"][-100:])


class HostAllowlistTests(unittest.TestCase):
    def test_loopback_hosts_pass(self):
        for h in ("127.0.0.1:37776", "localhost:37776", "127.0.0.1", "localhost",
                  "[::1]:37776"):
            self.assertTrue(viewer_server._host_allowed(h), h)

    def test_foreign_hosts_fail(self):
        for h in ("evil.example.com:37776", "192.168.1.7:37776", "", "evil.example.com"):
            self.assertFalse(viewer_server._host_allowed(h), h)


class ControlHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fail-closed default means a bare handler has no control plane;
        # these tests opt in the way serve() does on a confirmed loopback
        # bind, and restore the default afterward.
        cls._prev_enabled = viewer_server.CONTROL_ENABLED
        viewer_server.CONTROL_ENABLED = True
        cls._server = ThreadingHTTPServer(("127.0.0.1", 0), viewer_server._Handler)
        cls._port = cls._server.server_address[1]
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()

    @classmethod
    def tearDownClass(cls):
        cls._server.shutdown()
        cls._server.server_close()
        viewer_server.CONTROL_ENABLED = cls._prev_enabled

    def _post(self, path: str, token: str | None = None, host: str | None = None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self._port}{path}", method="POST", data=b""
        )
        if token is not None:
            req.add_header("X-Episteme-Token", token)
        if host is not None:
            # urllib refuses to override Host via add_header on some paths;
            # set it unredirected to simulate a DNS-rebound request.
            req.add_unredirected_header("Host", host)
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return res.status, json.loads(res.read().decode())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read().decode())

    def test_missing_token_is_403(self):
        status, body = self._post("/api/control/doctor")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "token_mismatch")

    def test_wrong_token_is_403(self):
        status, body = self._post("/api/control/doctor", token="stale-token")
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "token_mismatch")

    def test_rebound_host_is_403_even_with_valid_token(self):
        status, body = self._post(
            "/api/control/doctor",
            token=viewer_server.SESSION_TOKEN,
            host="evil.example.com",
        )
        self.assertEqual(status, 403)
        self.assertEqual(body["error"], "host_not_allowed")

    def test_unknown_action_is_404_with_valid_token(self):
        status, body = self._post(
            "/api/control/kernel_update", token=viewer_server.SESSION_TOKEN
        )
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "unknown_action")

    def test_control_disabled_flag_beats_valid_token(self):
        original = viewer_server.CONTROL_ENABLED
        viewer_server.CONTROL_ENABLED = False
        try:
            status, body = self._post(
                "/api/control/doctor", token=viewer_server.SESSION_TOKEN
            )
            self.assertEqual(status, 403)
            self.assertEqual(body["error"], "control_disabled_non_loopback")
        finally:
            viewer_server.CONTROL_ENABLED = original

    def test_catalog_lists_tiers_and_flag(self):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self._port}/api/control/catalog", timeout=10
        ) as res:
            body = json.loads(res.read().decode())
        self.assertIn("control_enabled", body)
        self.assertTrue(any(a["tier"] == 1 for a in body["actions"]))
        self.assertTrue(any(a["tier"] == 2 for a in body["actions"]))
        self.assertTrue(body["tier3"])

    def test_index_page_embeds_the_session_token(self):
        with urllib.request.urlopen(
            f"http://127.0.0.1:{self._port}/", timeout=10
        ) as res:
            page = res.read().decode()
        self.assertIn(viewer_server.SESSION_TOKEN, page)
        self.assertNotIn("{{EPISTEME_TOKEN}}", page)

    def test_tier1_action_runs_end_to_end(self):
        # Asserts the authenticated pipe works — action ran, produced output,
        # and exited with a lint verdict (0 or 1). Pinning exit==0 would make
        # a control-plane test fail for a docs reason (review nit).
        status, body = self._post(
            "/api/control/docs_lint", token=viewer_server.SESSION_TOKEN
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["name"], "docs_lint")
        self.assertIn(body["exit_code"], (0, 1))
        self.assertTrue(body["output"].strip())


if __name__ == "__main__":
    unittest.main()
