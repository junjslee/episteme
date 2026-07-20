"""Event 173 — code→doc reverse index (`docs map`) + targeted DOC ADVISORY.

The reverse index inverts the drift linter's citation walk (one notion of
"what a doc cites" — see test_doc_references.py for the extraction taxonomy),
so these tests cover only what inversion adds:

  * edge construction: exact-file vs directory citations, resolution keying,
    dangling citations creating NO obligation, obligation-exempt citing sets
    (archive/ + the linter's fixture trees), self-citation exclusion
  * query semantics: repo-relative and absolute spellings, paths outside the
    root, NEW (not-yet-existing) files under a cited directory — a Write that
    creates a hook must implicate the hook docs
  * ordering: strongest claim first (file > deeper dir > shallower dir), one
    edge per citing doc
  * the mtime-digest cache: hit, invalidation on edit, corruption tolerance,
    and the positive-system write rule (cache only where .episteme/ exists)
  * the real corpus: at least one live edge this repo relies on
  * workflow_guard: targeted advisory on a citing project, generic fallback on
    no-citations / no-git / no-package
"""

from __future__ import annotations

import io
import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.hooks import workflow_guard
from episteme import doc_references as dr

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ReverseIndexUnitTests(unittest.TestCase):
    """Pure inversion semantics on a synthetic corpus (no git needed)."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_exact_file_citation_creates_obligation(self):
        _write(self.root, "core/hooks/x.py", "pass\n")
        _write(self.root, "docs/HOOKS.md", "The guard is `core/hooks/x.py`.\n")
        docs = dr.docs_for_path(
            self.root, "core/hooks/x.py", doc_files=["docs/HOOKS.md"]
        )
        self.assertEqual(docs, ["docs/HOOKS.md"])

    def test_dir_citation_implicates_files_under_it(self):
        _write(self.root, "core/hooks/y.py", "pass\n")
        _write(self.root, "docs/MAP.md", "Hooks live in `core/hooks/`.\n")
        docs = dr.docs_for_path(
            self.root, "core/hooks/y.py", doc_files=["docs/MAP.md"]
        )
        self.assertEqual(docs, ["docs/MAP.md"])

    def test_dir_citation_implicates_new_not_yet_existing_file(self):
        # A Write that CREATES a file under a cited dir must fire — a new hook
        # needs documenting; this is the feature, not a resolution bug.
        _write(self.root, "core/hooks/existing.py", "pass\n")
        _write(self.root, "docs/MAP.md", "Hooks live in `core/hooks/`.\n")
        docs = dr.docs_for_path(
            self.root, "core/hooks/brand_new.py", doc_files=["docs/MAP.md"]
        )
        self.assertEqual(docs, ["docs/MAP.md"])

    def test_dangling_citation_creates_no_obligation(self):
        _write(self.root, "docs/MAP.md", "See `core/gone.py` for details.\n")
        index = dr.build_reverse_index(self.root, doc_files=["docs/MAP.md"])
        self.assertEqual(index, {})

    def test_archive_and_fixture_trees_are_obligation_exempt(self):
        _write(self.root, "core/hooks/x.py", "pass\n")
        _write(self.root, "archive/old_report.md", "Was `core/hooks/x.py`.\n")
        _write(self.root, "templates/scaffold.md", "Copies `core/hooks/x.py`.\n")
        index = dr.build_reverse_index(
            self.root, doc_files=["archive/old_report.md", "templates/scaffold.md"]
        )
        self.assertEqual(index, {})

    def test_self_citation_is_excluded(self):
        _write(self.root, "docs/MAP.md", "This file is `docs/MAP.md`.\n")
        docs = dr.docs_for_path(self.root, "docs/MAP.md", doc_files=["docs/MAP.md"])
        self.assertEqual(docs, [])

    def test_absolute_query_path_normalizes_into_root(self):
        _write(self.root, "core/hooks/x.py", "pass\n")
        _write(self.root, "docs/HOOKS.md", "The guard is `core/hooks/x.py`.\n")
        docs = dr.docs_for_path(
            self.root,
            str(self.root / "core" / "hooks" / "x.py"),
            doc_files=["docs/HOOKS.md"],
        )
        self.assertEqual(docs, ["docs/HOOKS.md"])

    def test_query_path_outside_root_yields_nothing(self):
        _write(self.root, "docs/HOOKS.md", "The guard is `core/hooks/x.py`.\n")
        self.assertEqual(
            dr.docs_for_path(self.root, "/etc/passwd", doc_files=["docs/HOOKS.md"]),
            [],
        )
        self.assertEqual(
            dr.docs_for_path(self.root, "../outside.py", doc_files=["docs/HOOKS.md"]),
            [],
        )

    def test_edges_order_strongest_claim_first_one_edge_per_doc(self):
        _write(self.root, "core/hooks/x.py", "pass\n")
        _write(self.root, "docs/EXACT.md", "Implements `core/hooks/x.py`.\n")
        _write(self.root, "docs/DEEP.md", "Hooks: `core/hooks/`.\n")
        _write(self.root, "docs/SHALLOW.md", "Everything under `core/`.\n")
        _write(
            self.root,
            "docs/BOTH.md",
            "Cites dir `core/hooks/` and file `core/hooks/x.py`.\n",
        )
        edges = dr.edges_for_path(
            self.root,
            "core/hooks/x.py",
            doc_files=[
                "docs/SHALLOW.md",
                "docs/DEEP.md",
                "docs/EXACT.md",
                "docs/BOTH.md",
            ],
        )
        self.assertEqual(len(edges), 4)  # one edge per citing doc
        kinds = [e.kind for e in edges]
        self.assertEqual(kinds[:2], ["file", "file"])  # BOTH keeps its file edge
        self.assertEqual(
            [e.doc for e in edges],
            ["docs/BOTH.md", "docs/EXACT.md", "docs/DEEP.md", "docs/SHALLOW.md"],
        )
        # deeper dir target sorts before shallower
        self.assertEqual(edges[2].target, "core/hooks")
        self.assertEqual(edges[3].target, "core")


class ReverseIndexCacheTests(unittest.TestCase):
    """The mtime-digest cache behind cached_reverse_index (needs a git repo)."""

    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)
        _write(self.root, "core/hooks/x.py", "pass\n")
        _write(self.root, "docs/HOOKS.md", "The guard is `core/hooks/x.py`.\n")
        subprocess.run(
            ["git", "-C", str(self.root), "init", "-q"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.root), "add", "-A"], check=True
        )

    def _cache_path(self) -> Path:
        return self.root / ".episteme" / "cache" / "doc_map.json"

    def test_no_cache_written_without_episteme_dir(self):
        index = dr.cached_reverse_index(self.root)
        self.assertIn("core/hooks/x.py", index)
        self.assertFalse(self._cache_path().exists())

    def test_cache_written_and_hit_when_episteme_dir_exists(self):
        (self.root / ".episteme").mkdir()
        first = dr.cached_reverse_index(self.root)
        self.assertTrue(self._cache_path().exists())
        # a cache hit must reproduce the same edges without rebuilding
        with patch.object(dr, "build_reverse_index") as rebuild:
            second = dr.cached_reverse_index(self.root)
            rebuild.assert_not_called()
        self.assertEqual(
            {t: [(e.doc, e.kind) for e in es] for t, es in first.items()},
            {t: [(e.doc, e.kind) for e in es] for t, es in second.items()},
        )

    def test_cache_invalidates_when_a_doc_changes(self):
        (self.root / ".episteme").mkdir()
        dr.cached_reverse_index(self.root)
        # touch content AND size so the digest moves even on coarse mtimes
        _write(
            self.root,
            "docs/HOOKS.md",
            "The guard moved to `core/hooks/x.py` — expanded prose.\n",
        )
        with patch.object(
            dr, "build_reverse_index", wraps=dr.build_reverse_index
        ) as rebuild:
            dr.cached_reverse_index(self.root)
            rebuild.assert_called_once()

    def test_corrupt_cache_degrades_to_fresh_build(self):
        (self.root / ".episteme").mkdir()
        self._cache_path().parent.mkdir(parents=True, exist_ok=True)
        self._cache_path().write_text("{not json", encoding="utf-8")
        index = dr.cached_reverse_index(self.root)
        self.assertIn("core/hooks/x.py", index)


class RealCorpusEdges(unittest.TestCase):
    """Live edges this repo's governance actually relies on."""

    def test_hook_edits_implicate_hooks_doc(self):
        docs = dr.docs_for_path(REPO_ROOT, "core/hooks/workflow_guard.py")
        self.assertIn("docs/HOOKS.md", docs)

    def test_dir_citation_from_agents_md_reaches_hooks(self):
        docs = dr.docs_for_path(REPO_ROOT, "core/hooks/workflow_guard.py")
        self.assertIn("AGENTS.md", docs)

    def test_cli_edits_implicate_commands_doc(self):
        # The edge exists because COMMANDS.md names its source of truth —
        # added in E173 so CLI edits surface the doc that documents them.
        docs = dr.docs_for_path(REPO_ROOT, "src/episteme/cli.py")
        self.assertIn("docs/COMMANDS.md", docs)


class WorkflowGuardTargetedAdvisoryTests(unittest.TestCase):
    """The hook end-to-end: targeted when edges exist, generic otherwise."""

    def _run_hook(self, payload: dict) -> str:
        raw = json.dumps(payload)
        with patch("sys.stdin", new=io.StringIO(raw)), patch(
            "sys.stdout", new=io.StringIO()
        ) as fake_out:
            rc = workflow_guard.main()
        self.assertEqual(rc, 0)
        out = fake_out.getvalue()
        if not out:
            return ""
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]

    def _project(self, with_git: bool, with_citation: bool) -> Path:
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve()
        _write(root, "AGENTS.md", "# agents\n")  # authoritative-docs trigger
        _write(root, "src/app.py", "pass\n")
        if with_citation:
            _write(root, "docs/APP.md", "Entry point: `src/app.py`.\n")
        if with_git:
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        return root

    def _payload(self, root: Path) -> dict:
        return {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(root / "src" / "app.py")},
            "session_type": "main",
            "cwd": str(root),
        }

    def test_targeted_advisory_names_the_citing_doc(self):
        root = self._project(with_git=True, with_citation=True)
        context = self._run_hook(self._payload(root))
        self.assertIn("DOC ADVISORY", context)
        self.assertIn("docs/APP.md", context)
        self.assertNotIn("WORKFLOW ADVISORY", context)

    def test_no_citations_falls_back_to_generic(self):
        root = self._project(with_git=True, with_citation=False)
        context = self._run_hook(self._payload(root))
        self.assertIn("WORKFLOW ADVISORY", context)

    def test_non_git_project_falls_back_to_generic(self):
        root = self._project(with_git=False, with_citation=True)
        context = self._run_hook(self._payload(root))
        self.assertIn("WORKFLOW ADVISORY", context)

    def test_unimportable_package_falls_back_to_generic(self):
        root = self._project(with_git=True, with_citation=True)
        with patch.object(workflow_guard, "_load_doc_references", return_value=None):
            context = self._run_hook(self._payload(root))
        self.assertIn("WORKFLOW ADVISORY", context)

    def test_symlinked_doc_edit_is_suppressed_not_resolved_away(self):
        # docs/NEXT_STEPS.md-style setup: the authoritative doc is a symlink
        # into a tree OUTSIDE the project. resolve() would follow it out of
        # cwd and defeat the doc-path suppression; the textual prefix-strip
        # must keep the repo-relative spelling and stay silent.
        root = self._project(with_git=True, with_citation=False)
        outside = TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        real = Path(outside.name) / "NEXT_STEPS.md"
        real.write_text("# next\n", encoding="utf-8")
        link = root / "docs" / "NEXT_STEPS.md"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(real)
        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(link)},
            "session_type": "main",
            "cwd": str(root),
        }
        raw = json.dumps(payload)
        with patch("sys.stdin", new=io.StringIO(raw)), patch(
            "sys.stdout", new=io.StringIO()
        ) as fake_out:
            rc = workflow_guard.main()
        self.assertEqual(rc, 0)
        self.assertEqual(fake_out.getvalue(), "")  # suppressed, no advisory

    def test_overflow_is_counted_never_silent(self):
        root = self._project(with_git=True, with_citation=True)
        for i in range(8):
            _write(root, f"docs/D{i}.md", "Covers `src/app.py`.\n")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        context = self._run_hook(self._payload(root))
        self.assertIn("DOC ADVISORY", context)
        self.assertIn("more", context)  # "… and N more"


if __name__ == "__main__":
    unittest.main()
