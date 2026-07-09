"""Tests for the doc/artifact lifecycle engine (Event 147, Mechanism 1).

Red-green discipline: the synthetic-fixture tests below demonstrate ``lint``
FAILING on a marker-less / malformed doc before the corpus test asserts the
real repo is clean. The fixtures build throwaway git repos so ``tracked_docs``'
``git ls-files`` walk exercises the real enumeration path.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from episteme import doc_lifecycle as dl

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)


def _add(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", rel], cwd=root, check=True)


class ParseMarkerTests(unittest.TestCase):
    def test_parse_living(self):
        m = dl.parse_marker_text(
            "<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->"
        )
        assert m is not None
        self.assertEqual(m.status, "living")
        self.assertEqual(m.reviewed_as_of, "E147")
        self.assertIsNone(m.superseded_by)

    def test_parse_design_history_with_superseded_by(self):
        m = dl.parse_marker_text(
            "<!-- episteme-lifecycle: status=design-history; "
            "reviewed_as_of=E147; superseded_by=docs/DESIGN_V2_0_EPISTEMIC_ENGINE.md -->"
        )
        assert m is not None
        self.assertEqual(m.status, "design-history")
        self.assertEqual(m.superseded_by, "docs/DESIGN_V2_0_EPISTEMIC_ENGINE.md")

    def test_parse_scope_on_living(self):
        m = dl.parse_marker_text(
            "<!-- episteme-lifecycle: status=living; reviewed_as_of=E147; "
            "superseded_by=docs/DESIGN_V2_0_EPISTEMIC_ENGINE.md; "
            "scope=enforcement-geometry-framing -->"
        )
        assert m is not None
        self.assertEqual(m.scope, "enforcement-geometry-framing")

    def test_no_marker_returns_none(self):
        self.assertIsNone(dl.parse_marker_text("# Just a heading"))


class LintFixtureTests(unittest.TestCase):
    """RED: lint must flag marker-less / malformed docs in a synthetic repo."""

    def test_missing_marker_is_flagged(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            _add(root, "docs/NO_MARKER.md", "# A doc with no lifecycle marker\n")
            findings = dl.lint(root)
            kinds = {(f.file, f.kind) for f in findings}
            self.assertIn(("docs/NO_MARKER.md", "missing-marker"), kinds)

    def test_invalid_status_is_flagged(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            _add(
                root,
                "docs/BAD_STATUS.md",
                "<!-- episteme-lifecycle: status=archived; reviewed_as_of=E147 -->\n# x\n",
            )
            kinds = {(f.file, f.kind) for f in dl.lint(root)}
            self.assertIn(("docs/BAD_STATUS.md", "invalid-status"), kinds)

    def test_design_history_without_superseded_by_is_flagged(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            _add(
                root,
                "docs/DH.md",
                "<!-- episteme-lifecycle: status=design-history; reviewed_as_of=E147 -->\n# x\n",
            )
            kinds = {(f.file, f.kind) for f in dl.lint(root)}
            self.assertIn(("docs/DH.md", "missing-superseded-by"), kinds)

    def test_missing_reviewed_as_of_is_flagged(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            _add(
                root,
                "docs/NR.md",
                "<!-- episteme-lifecycle: status=living -->\n# x\n",
            )
            kinds = {(f.file, f.kind) for f in dl.lint(root)}
            self.assertIn(("docs/NR.md", "missing-reviewed-as-of"), kinds)

    def test_well_formed_doc_is_clean(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            _add(
                root,
                "docs/OK.md",
                "<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->\n# Good\n",
            )
            self.assertEqual(dl.lint(root), [])

    def test_symlink_is_skipped(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            _add(root, "real/PLAN.md", "# no marker here\n")
            link = root / "docs" / "PLAN.md"
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(root / "real" / "PLAN.md")
            subprocess.run(["git", "add", "docs/PLAN.md"], cwd=root, check=True)
            self.assertEqual(dl.lint(root), [])


class ReportSinkFixtureTests(unittest.TestCase):
    """RED/GREEN: status=report is bounded to the config grandfather list
    (Event 147, Mechanism 4). A non-grandfathered report doc is flagged; a
    grandfathered one passes."""

    def test_non_grandfathered_report_is_flagged(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            _add(
                root,
                "docs/NEW_REPORT.md",
                "<!-- episteme-lifecycle: status=report; reviewed_as_of=E147 -->\n# R\n",
            )
            findings = dl.lint(root)
            kinds = {(f.file, f.kind) for f in findings}
            self.assertIn(("docs/NEW_REPORT.md", "report-sink"), kinds)

    def test_grandfathered_report_is_clean(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            _add(
                root,
                "docs/EVALUATION_METHOD.md",
                "<!-- episteme-lifecycle: status=report; reviewed_as_of=E147 -->\n# R\n",
            )
            # docs/EVALUATION_METHOD.md is in the default grandfather list.
            self.assertEqual(dl.lint(root), [])

    def test_config_can_extend_grandfather_list(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            (root / ".episteme").mkdir()
            (root / ".episteme" / "config.json").write_text(
                '{"report_grandfather": ["docs/NEW_REPORT.md"]}', encoding="utf-8"
            )
            _add(
                root,
                "docs/NEW_REPORT.md",
                "<!-- episteme-lifecycle: status=report; reviewed_as_of=E147 -->\n# R\n",
            )
            # With NEW_REPORT.md grandfathered via config, no report-sink finding.
            kinds = {(f.file, f.kind) for f in dl.lint(root)}
            self.assertNotIn(("docs/NEW_REPORT.md", "report-sink"), kinds)


class GenerateIndexTests(unittest.TestCase):
    def test_index_lists_docs_with_status_and_purpose(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            _add(
                root,
                "docs/ALPHA.md",
                "<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->\n"
                "# Alpha — the first doc\n",
            )
            index = dl.generate_index(root)
            self.assertIn("[`ALPHA.md`](./ALPHA.md)", index)
            self.assertIn("living", index)
            self.assertIn("Alpha — the first doc", index)

    def test_update_readme_index_is_idempotent(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            _init_repo(root)
            _add(
                root,
                "docs/ALPHA.md",
                "<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->\n# Alpha\n",
            )
            _add(
                root,
                "docs/README.md",
                "<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->\n"
                "# Index\n\n" + dl.INDEX_START + "\nOLD\n" + dl.INDEX_END + "\n",
            )
            changed1, _ = dl.update_readme_index(root)
            self.assertTrue(changed1)
            changed2, _ = dl.update_readme_index(root)
            self.assertFalse(changed2)


class ConfigDiscoveryTests(unittest.TestCase):
    def test_defaults(self):
        with TemporaryDirectory() as td:
            cfg = dl.discover_config(Path(td))
            self.assertEqual(cfg.docs_dir, "docs")
            self.assertEqual(
                cfg.report_grandfather, dl._DEFAULT_REPORT_GRANDFATHER
            )

    def test_pyproject_override(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "pyproject.toml").write_text(
                "[tool.episteme]\ndocs_dir = \"documentation\"\n",
                encoding="utf-8",
            )
            cfg = dl.discover_config(root)
            self.assertEqual(cfg.docs_dir, "documentation")


class RepoCorpusTests(unittest.TestCase):
    """GREEN: the real repo corpus is clean once every doc is stamped."""

    def test_repo_corpus_is_clean(self):
        findings = dl.lint(_REPO_ROOT)
        self.assertEqual(
            findings,
            [],
            "doc lifecycle violations in the tracked corpus:\n"
            + dl.format_findings(findings),
        )


if __name__ == "__main__":
    unittest.main()
