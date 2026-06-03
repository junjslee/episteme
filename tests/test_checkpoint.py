"""Tests for the checkpoint auto-commit hook (Event 136).

Asserts the commit-title prefix is Conventional-Commits-valid
(`chore(chkpt):`) so release-please's parser stops 500-ing on merge-commit
walks (CP-RELEASE-PLEASE-CHKPT-FILTER-01), and that the ISO timestamp body
is preserved.
"""
import unittest
from unittest.mock import patch

from core.hooks import checkpoint


class _FakeProc:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


class CheckpointPrefixTests(unittest.TestCase):
    def test_commit_prefix_is_conventional(self):
        calls = []

        def fake_run(args, *, cwd):
            calls.append(args)
            if args[:2] == ["git", "rev-parse"]:
                return _FakeProc(stdout="/repo", returncode=0)
            if args[:2] == ["git", "status"]:
                return _FakeProc(stdout=" M file.py\n", returncode=0)
            return _FakeProc(stdout="", returncode=0)

        with patch.object(checkpoint, "_run", side_effect=fake_run):
            rc = checkpoint.main()

        self.assertEqual(rc, 0)
        commit_calls = [c for c in calls if c[:2] == ["git", "commit"]]
        self.assertEqual(len(commit_calls), 1)
        msg = commit_calls[0][-1]
        self.assertTrue(
            msg.startswith("chore(chkpt): "),
            f"expected Conventional prefix, got {msg!r}",
        )
        self.assertFalse(msg.startswith("chkpt: "), "bare chkpt: prefix must be gone")

    def test_timestamp_body_preserved(self):
        captured = {}

        def fake_run(args, *, cwd):
            if args[:2] == ["git", "rev-parse"]:
                return _FakeProc(stdout="/repo", returncode=0)
            if args[:2] == ["git", "status"]:
                return _FakeProc(stdout=" M file.py\n", returncode=0)
            if args[:2] == ["git", "commit"]:
                captured["msg"] = args[-1]
            return _FakeProc(stdout="", returncode=0)

        with patch.object(checkpoint, "_run", side_effect=fake_run):
            checkpoint.main()

        self.assertRegex(
            captured["msg"],
            r"^chore\(chkpt\): \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$",
        )

    def test_no_commit_when_tree_clean(self):
        def fake_run(args, *, cwd):
            if args[:2] == ["git", "rev-parse"]:
                return _FakeProc(stdout="/repo", returncode=0)
            if args[:2] == ["git", "status"]:
                return _FakeProc(stdout="", returncode=0)  # clean
            return _FakeProc(stdout="", returncode=0)

        with patch.object(checkpoint, "_run", side_effect=fake_run) as m:
            rc = checkpoint.main()
        self.assertEqual(rc, 0)
        self.assertNotIn(
            ["git", "commit"], [c.args[0][:2] for c in m.call_args_list]
        )

    def test_no_commit_when_not_a_repo(self):
        def fake_run(args, *, cwd):
            if args[:2] == ["git", "rev-parse"]:
                return _FakeProc(stdout="", returncode=128)  # not a repo
            return _FakeProc(stdout="", returncode=0)

        with patch.object(checkpoint, "_run", side_effect=fake_run):
            rc = checkpoint.main()
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
