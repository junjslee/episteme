"""Tests for the block-dangerous PreToolUse Bash gate (Event 136).

The load-bearing regression: a commit-message HEREDOC body (or any quoted
string literal) that MENTIONS a destructive token like `rm -rf` in prose
must be ALLOWED, while an actual destructive command at command position
must still be BLOCKED. See core/hooks/block_dangerous.py _strip_message_bodies.
"""
import io
import json
import unittest
from unittest.mock import patch

from core.hooks import block_dangerous


def _run_main(command: str) -> tuple[int, str]:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    raw = json.dumps(payload)
    with patch("sys.stdin", new=io.StringIO(raw)), patch(
        "sys.stderr", new=io.StringIO()
    ) as fake_err:
        rc = block_dangerous.main()
    return rc, fake_err.getvalue()


class BlockDangerousTests(unittest.TestCase):
    # --- the required regression pair -------------------------------------
    def test_commit_body_with_literal_recursive_delete_prose_is_allowed(self):
        # A real commit-flow heredoc whose body documents that Tier 3 blocks
        # destructive deletes — the literal phrase appears in prose only.
        command = (
            'git commit -m "$(cat <<\'EOF\'\n'
            "feat: tiered gate\n\n"
            "Tier 3 denylist includes rm -rf / and git reset --hard and\n"
            "git push --force to protected branches.\n"
            "EOF\n"
            ')"'
        )
        rc, _ = _run_main(command)
        self.assertEqual(rc, 0, "prose mentioning rm -rf must not be blocked")

    def test_real_recursive_delete_of_root_is_blocked(self):
        rc, err = _run_main("rm -rf /")
        self.assertEqual(rc, 2)
        self.assertIn("recursive delete", err.lower())

    # --- destructive tokens outside quotes/heredocs still blocked ---------
    def test_destructive_token_after_quoted_arg_still_blocked(self):
        rc, _ = _run_main("echo 'done' && rm -rf /tmp/x")
        self.assertEqual(rc, 2)

    def test_destructive_token_after_heredoc_still_blocked(self):
        # The non-greedy heredoc strip stops at the terminator, so a real
        # command AFTER the heredoc body remains visible to the matcher.
        command = (
            'git commit -m "$(cat <<\'EOF\'\nsome message\nEOF\n)" && rm -rf /var/data'
        )
        rc, _ = _run_main(command)
        self.assertEqual(rc, 2)

    def test_reset_hard_still_blocked(self):
        rc, _ = _run_main("git reset --hard origin/master")
        self.assertEqual(rc, 2)

    def test_force_push_still_blocked(self):
        rc, _ = _run_main("git push --force origin master")
        self.assertEqual(rc, 2)

    def test_force_with_lease_still_blocked(self):
        rc, _ = _run_main("git push --force-with-lease origin master")
        self.assertEqual(rc, 2)

    # --- prose in single/double quotes allowed ----------------------------
    def test_double_quoted_prose_allowed(self):
        rc, _ = _run_main('git commit -m "docs: the rm -rf phrase is safe here"')
        self.assertEqual(rc, 0)

    def test_single_quoted_prose_allowed(self):
        rc, _ = _run_main("git commit -m 'docs: rm -rf in prose is fine'")
        self.assertEqual(rc, 0)

    def test_heredoc_bare_delimiter_prose_allowed(self):
        command = "cat <<EOF\nthis mentions rm -rf / harmlessly\nEOF"
        rc, _ = _run_main(command)
        self.assertEqual(rc, 0)

    # --- fail-open on malformed input -------------------------------------
    def test_empty_stdin_returns_0(self):
        with patch("sys.stdin", new=io.StringIO("")), patch(
            "sys.stderr", new=io.StringIO()
        ):
            self.assertEqual(block_dangerous.main(), 0)

    def test_non_json_stdin_returns_0(self):
        with patch("sys.stdin", new=io.StringIO("not json {{{")), patch(
            "sys.stderr", new=io.StringIO()
        ):
            self.assertEqual(block_dangerous.main(), 0)

    # --- other true-positives unaffected by the strip ---------------------
    def test_sudo_still_blocked(self):
        rc, _ = _run_main("sudo rm /etc/hosts")
        self.assertEqual(rc, 2)

    def test_mkfs_still_blocked(self):
        rc, _ = _run_main("mkfs.ext4 /dev/sdb1")
        self.assertEqual(rc, 2)

    # --- EXECUTING shell-interpreter forms MUST stay blocked --------------
    # (Event 136 review: stripping these was a security regression — the
    # heredoc/quoted content is executable, not prose. origin/master blocked
    # all three; the strip must not un-block them.)
    def test_sh_dash_c_destructive_blocked(self):
        rc, _ = _run_main("sh -c 'rm -rf /'")
        self.assertEqual(rc, 2)

    def test_bash_dash_c_destructive_blocked(self):
        rc, _ = _run_main('bash -c "rm -rf /"')
        self.assertEqual(rc, 2)

    def test_bash_heredoc_fed_to_shell_blocked(self):
        rc, _ = _run_main("bash <<EOF\nrm -rf /\nEOF")
        self.assertEqual(rc, 2)

    def test_sh_heredoc_fed_to_shell_blocked(self):
        rc, _ = _run_main("sh <<'EOF'\ngit reset --hard origin/x\nEOF")
        self.assertEqual(rc, 2)

    def test_pipe_to_bash_destructive_blocked(self):
        rc, _ = _run_main("echo 'rm -rf /' | bash")
        self.assertEqual(rc, 2)

    def test_eval_destructive_blocked(self):
        rc, _ = _run_main("eval 'rm -rf /'")
        self.assertEqual(rc, 2)

    def test_opener_line_chained_destructive_blocked(self):
        # `echo <<X && rm -rf /` — the chained command on the opener line
        # executes; the heredoc body strip must NOT swallow it.
        rc, _ = _run_main("echo <<X && rm -rf /tmp/z\nX")
        self.assertEqual(rc, 2)

    # The commit-message prose case (the original motivation) stays allowed
    # even though it shares the heredoc shape — because `cat`/`git commit`
    # do not execute the body.
    def test_git_commit_prose_still_allowed_after_security_fix(self):
        command = (
            'git commit -m "$(cat <<\'EOF\'\n'
            "docs: Tier 3 blocks rm -rf / and git reset --hard\n"
            "EOF\n"
            ')"'
        )
        rc, _ = _run_main(command)
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
