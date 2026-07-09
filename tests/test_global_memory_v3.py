"""Event 147 · Lane B1 — Global Memory v3 generator, fresh-clone fallback,
max-date profile staleness, and volatile-fact (version) stamping.

Covers:
- render_user_claude_md() v3 emission: inline runtime_digest + runtime policy +
  agent feedback; path-reference the four deep profiles (NOT @imports).
- fresh-clone fallback: a missing personal runtime_digest.md resolves to the
  tracked example rather than dangling or crashing.
- _read_last_elicited() takes the max of every parseable elicitation date.
- volatile-fact stamping: idempotent rewrite of the version span from the
  release-please manifest (red-green — stale before, current after).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

from episteme import cli
from episteme.adapters import claude as claude_adapter


# ---------------------------------------------------------------------------
# _read_last_elicited — max of all parseable elicitation dates
# ---------------------------------------------------------------------------


class ReadLastElicitedMaxTests(unittest.TestCase):
    def _prof(self, td: str, body: str) -> Path:
        p = Path(td) / "operator_profile.md"
        p.write_text(body, encoding="utf-8")
        return p

    def test_multi_date_header_returns_newest(self):
        body = (
            "# Operator Profile\n\n"
            "Last elicited: 2026-04-13 (process axes); "
            "2026-04-20 (cognitive-style axes — inferred pending confirmation); "
            "2026-07-08 (asymmetry_posture refinement — operator-directed, Event 147).\n"
        )
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                cli._read_last_elicited(self._prof(td, body)), date(2026, 7, 8)
            )

    def test_last_observed_lines_counted(self):
        body = (
            "# p\n\nLast elicited: 2026-04-13\n\n"
            "```\naxis:\n"
            "  last_observed: 2026-04-20\n"
            "  last_observed: 2026-07-08\n"
            "```\n"
        )
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                cli._read_last_elicited(self._prof(td, body)), date(2026, 7, 8)
            )

    def test_prose_note_dates_are_ignored(self):
        # A `note:` line that merely mentions a (future) date must not count —
        # only declared elicitation-keyed lines drive freshness.
        body = (
            "# p\n\nLast elicited: 2026-04-13\n"
            "  note: corrected 2029-01-01 in a later pass\n"
        )
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                cli._read_last_elicited(self._prof(td, body)), date(2026, 4, 13)
            )

    def test_single_date_line_unchanged(self):
        # Backwards-compat with the pre-147 single-date parser.
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                cli._read_last_elicited(self._prof(td, "# t\n\nLast elicited: 2026-04-20\n")),
                date(2026, 4, 20),
            )

    def test_malformed_only_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(
                cli._read_last_elicited(self._prof(td, "# t\n\nLast elicited: 2026-13-40\n"))
            )

    def test_future_dates_ignored_when_valid_past_date_exists(self):
        # Fail-closed on the drift signal (Event 147 검수 finding): a
        # future-dated typo on one axis must not mask real elicitation dates
        # or silently suppress the stale-profile warning.
        body = (
            "# p\n\nLast elicited: 2026-07-08\n\n"
            "```\naxis:\n  last_observed: 2099-01-01\n```\n"
        )
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(
                cli._read_last_elicited(self._prof(td, body), today=date(2026, 7, 8)),
                date(2026, 7, 8),
            )

    def test_only_future_dates_returns_none(self):
        body = "# t\n\nLast elicited: 2099-01-01\n"
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(
                cli._read_last_elicited(self._prof(td, body), today=date(2026, 7, 8))
            )

    def test_staleness_warns_on_future_only_profile(self):
        # A future-only profile is stale-unknown, not fresh — the warning fires
        # instead of being suppressed by the bogus date.
        body = "# p\n\nLast elicited: 2099-01-01\n"
        with tempfile.TemporaryDirectory() as td:
            status, _age, elicited = cli._profile_staleness(
                profile_path=self._prof(td, body), today=date(2026, 7, 8)
            )
            self.assertEqual(status, "unknown")
            self.assertIsNone(elicited)

    def test_staleness_fresh_from_newest_date(self):
        body = "# p\n\nLast elicited: 2026-04-13; 2026-07-08\n"
        with tempfile.TemporaryDirectory() as td:
            status, age, elicited = cli._profile_staleness(
                profile_path=self._prof(td, body), today=date(2026, 7, 8)
            )
            self.assertEqual(status, "fresh")
            self.assertEqual(elicited, date(2026, 7, 8))
            self.assertEqual(age, 0)

    @unittest.skipUnless(
        (cli.GLOBAL_MEMORY_DIR / "operator_profile.md").exists(),
        "canonical operator_profile.md not present (fresh clone / worktree)",
    )
    def test_real_canonical_profile_sees_current_elicitation(self):
        # On the operator's machine the canonical profile carries the
        # 2026-07-08 Event-147 refinement; the parser must surface it as the
        # newest date. Skipped where the private symlink is absent.
        newest = cli._read_last_elicited(cli.GLOBAL_MEMORY_DIR / "operator_profile.md")
        self.assertIsNotNone(newest)
        assert newest is not None
        self.assertGreaterEqual(newest, date(2026, 7, 8))


# ---------------------------------------------------------------------------
# render_user_claude_md() v3 emission + fresh-clone fallback
# ---------------------------------------------------------------------------


class RenderV3Tests(unittest.TestCase):
    _INLINE = ("runtime_digest", "python_runtime_policy", "agent_feedback")
    _DEEP = ("overview", "operator_profile", "workflow_policy", "cognitive_profile")

    def setUp(self):
        self._orig_dir = cli.GLOBAL_MEMORY_DIR
        self._orig_stale = cli._profile_staleness
        # Neutralise the stale-warning so assertions are about the body.
        cli._profile_staleness = lambda **_k: ("fresh", 1, date(2026, 7, 8))  # type: ignore[assignment]

    def tearDown(self):
        cli.GLOBAL_MEMORY_DIR = self._orig_dir  # type: ignore[assignment]
        cli._profile_staleness = self._orig_stale  # type: ignore[assignment]

    def _setup_mem(self, td: str, *, personal_digest: bool) -> Path:
        mem = Path(td)
        ex = mem / "examples"
        ex.mkdir(parents=True)
        for n in self._INLINE + self._DEEP:
            (ex / f"{n}.example.md").write_text(f"# {n} example\n", encoding="utf-8")
        if personal_digest:
            (mem / "runtime_digest.md").write_text("# personal digest\n", encoding="utf-8")
        cli.GLOBAL_MEMORY_DIR = mem  # type: ignore[assignment]
        return mem

    def test_inlines_exactly_three_imports(self):
        with tempfile.TemporaryDirectory() as td:
            self._setup_mem(td, personal_digest=True)
            md = claude_adapter.render_user_claude_md()
        at_lines = [ln for ln in md.splitlines() if ln.startswith("@")]
        self.assertEqual(len(at_lines), 3)
        joined = "\n".join(at_lines)
        for n in self._INLINE:
            self.assertIn(n, joined)
        # Deep profiles must NOT appear as @imports.
        for n in self._DEEP:
            self.assertNotIn(f"@{n}", md)
            self.assertNotIn(f"/{n}.", joined)

    def test_deep_profiles_path_referenced(self):
        with tempfile.TemporaryDirectory() as td:
            self._setup_mem(td, personal_digest=True)
            md = claude_adapter.render_user_claude_md()
        self.assertIn("## Deep profiles — Read on demand", md)
        # Each deep profile is a bullet line (not an @import).
        for n in self._DEEP:
            self.assertTrue(
                any(ln.startswith("- ") and n in ln for ln in md.splitlines()),
                f"deep profile {n} not path-referenced as a bullet",
            )

    def test_fresh_clone_falls_back_to_example_digest(self):
        with tempfile.TemporaryDirectory() as td:
            self._setup_mem(td, personal_digest=False)
            md = claude_adapter.render_user_claude_md()
        digest_line = next(ln for ln in md.splitlines() if ln.startswith("@") and "runtime_digest" in ln)
        self.assertTrue(
            digest_line.endswith("runtime_digest.example.md"),
            f"expected example fallback, got: {digest_line}",
        )

    def test_personal_digest_preferred_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            self._setup_mem(td, personal_digest=True)
            md = claude_adapter.render_user_claude_md()
        digest_line = next(ln for ln in md.splitlines() if ln.startswith("@") and "runtime_digest" in ln)
        self.assertTrue(digest_line.endswith("runtime_digest.md"))
        self.assertFalse(digest_line.endswith("example.md"))

    def test_shipped_example_digest_exists(self):
        # The tracked template that makes the fresh-clone fallback resolvable.
        example = cli.GLOBAL_MEMORY_DIR / "examples" / "runtime_digest.example.md"
        # setUp/tearDown restore GLOBAL_MEMORY_DIR; check the real repo path.
        real = self._orig_dir / "examples" / "runtime_digest.example.md"
        self.assertTrue(real.exists(), f"missing tracked template: {real}")


# ---------------------------------------------------------------------------
# Volatile-fact (version) stamping
# ---------------------------------------------------------------------------


class VolatileFactStampingTests(unittest.TestCase):
    _SPAN = "<!-- episteme-fact:version -->{v}<!-- /episteme-fact:version -->"

    def _manifest(self, root: Path, version: str = "1.9.0-rc1") -> None:
        (root / ".release-please-manifest.json").write_text(
            json.dumps({".": version}), encoding="utf-8"
        )

    def test_read_release_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._manifest(root)
            self.assertEqual(cli._read_release_version(root), "1.9.0-rc1")

    def test_read_release_version_missing_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(cli._read_release_version(Path(td)))

    def test_read_release_version_single_key_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".release-please-manifest.json").write_text(
                json.dumps({"packages/x": "2.0.0"}), encoding="utf-8"
            )
            self.assertEqual(cli._read_release_version(root), "2.0.0")

    def test_stamps_stale_span_red_green(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._manifest(root)
            doc = root / "ARCH.md"
            doc.write_text(
                "Ships at " + self._SPAN.format(v="0.0.1-stale") + " today.\n",
                encoding="utf-8",
            )
            # RED: the doc holds a stale version before stamping.
            self.assertIn("0.0.1-stale", doc.read_text(encoding="utf-8"))
            changed = cli._stamp_volatile_facts(root, files=[doc])
            # GREEN: the span now carries the manifest version.
            self.assertEqual([p.name for p in changed], ["ARCH.md"])
            after = doc.read_text(encoding="utf-8")
            self.assertNotIn("0.0.1-stale", after)
            self.assertIn(self._SPAN.format(v="1.9.0-rc1"), after)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._manifest(root)
            doc = root / "ARCH.md"
            doc.write_text(self._SPAN.format(v="1.9.0-rc1") + "\n", encoding="utf-8")
            first = cli._stamp_volatile_facts(root, files=[doc])
            self.assertEqual(first, [])  # already current — no rewrite

    def test_doc_without_marker_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._manifest(root)
            doc = root / "PLAIN.md"
            original = "No volatile facts here.\n"
            doc.write_text(original, encoding="utf-8")
            changed = cli._stamp_volatile_facts(root, files=[doc])
            self.assertEqual(changed, [])
            self.assertEqual(doc.read_text(encoding="utf-8"), original)

    def test_no_manifest_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            doc = root / "ARCH.md"
            doc.write_text(self._SPAN.format(v="0.0.1") + "\n", encoding="utf-8")
            changed = cli._stamp_volatile_facts(root, files=[doc])
            self.assertEqual(changed, [])
            self.assertIn("0.0.1", doc.read_text(encoding="utf-8"))

    @unittest.skipUnless(shutil.which("git"), "git not available")
    def test_default_enumeration_stamps_only_tracked_docs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
            self._manifest(root)
            docs = root / "docs"
            docs.mkdir()
            tracked = docs / "TRACKED.md"
            tracked.write_text(self._SPAN.format(v="0.0.1") + "\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "docs/TRACKED.md"], check=True)
            untracked = docs / "UNTRACKED.md"
            untracked.write_text(self._SPAN.format(v="0.0.1") + "\n", encoding="utf-8")
            changed = cli._stamp_volatile_facts(root)
            self.assertEqual([p.name for p in changed], ["TRACKED.md"])
            self.assertIn("1.9.0-rc1", tracked.read_text(encoding="utf-8"))
            # Untracked doc is left alone.
            self.assertIn("0.0.1", untracked.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
