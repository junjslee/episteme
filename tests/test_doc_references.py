"""Doc-to-code drift linter.

Asserts that file/directory paths cited in the repo's tracked markdown actually
resolve in the working tree, so documentation cannot silently rot when code is
moved, renamed, or deleted.

Design (see src/episteme/doc_references.py):
  * Citing-file set = tracked markdown (`git ls-files '*.md'`) — environment
    stable, auto-excludes the gitignored private-symlink docs and node_modules.
  * Extraction is a PURE string->references step (unit-tested here exhaustively
    against the real citation taxonomy): fence-stripping, an extension+prefix
    positive-system allowlist, and structural exemptions for URLs, tilde/abs
    paths, globs, brace-expansion, templates, env-vars, in-doc anchors, and
    code symbols.
  * A nonexistent citation is drift ONLY if it is not gitignored — git's own
    ignore semantics is the oracle for environment-dependent paths
    (.episteme/, archive/, core/memory/global/ canonicals, private docs).
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from episteme import doc_references as dr

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _refs(text: str, citing: str = "docs/SOME_DOC.md"):
    """Return the set of normalized targets extracted from `text`."""
    return {r.target for r in dr.extract_references(text, citing)}


class ExtractionExtractsRealCitations(unittest.TestCase):
    def test_backtick_file_path_is_extracted(self):
        self.assertIn("core/hooks/block_dangerous.py", _refs("see `core/hooks/block_dangerous.py` for the gate"))

    def test_backtick_directory_with_trailing_slash_is_extracted_as_dir(self):
        refs = dr.extract_references("the `core/hooks/` package", "docs/X.md")
        dirs = [r for r in refs if r.target == "core/hooks"]
        self.assertTrue(dirs, "trailing-slash dir citation should be extracted")
        self.assertEqual(dirs[0].kind, "dir")

    def test_markdown_link_target_is_extracted_not_link_text(self):
        targets = _refs("[`the design doc`](docs/ARCHITECTURE.md)")
        self.assertIn("docs/ARCHITECTURE.md", targets)
        self.assertNotIn("the design doc", targets)

    def test_bare_prose_path_with_allowlisted_ext_and_prefix_is_extracted(self):
        self.assertIn(
            "kernel/FALSIFIABILITY_CONDITIONS.md",
            _refs("the cascade fired (kernel/FALSIFIABILITY_CONDITIONS.md): 49 days later"),
        )

    def test_wellknown_bare_filename_is_extracted(self):
        self.assertIn("AGENTS.md", _refs("our policy lives in `AGENTS.md`"))

    def test_image_asset_path_is_extracted(self):
        self.assertIn("docs/assets/demo.gif", _refs("![demo](docs/assets/demo.gif)"))


class ExtractionNormalizesCitations(unittest.TestCase):
    def test_path_line_suffix_is_stripped(self):
        self.assertIn("core/hooks/checkpoint.py", _refs("see core/hooks/checkpoint.py:34 for the call"))

    def test_path_line_col_suffix_is_stripped(self):
        self.assertIn("src/episteme/cli.py", _refs("at `src/episteme/cli.py:1318:5`"))

    def test_section_marker_keeps_only_the_path_to_its_left(self):
        targets = _refs("see kernel/FALSIFIABILITY_CONDITIONS.md § E1 for detail")
        self.assertIn("kernel/FALSIFIABILITY_CONDITIONS.md", targets)
        self.assertNotIn("kernel/FALSIFIABILITY_CONDITIONS.md § E1", targets)

    def test_query_string_is_stripped_from_asset(self):
        self.assertIn("docs/assets/logo.svg", _refs('<img src="docs/assets/logo.svg?v=2">'))

    def test_fragment_is_stripped_from_link(self):
        self.assertIn("docs/ARCHITECTURE.md", _refs("[x](docs/ARCHITECTURE.md#layer-3)"))

    def test_relative_dotslash_link_resolves_against_citing_dir(self):
        # ./CONSTITUTION.md cited from kernel/FAILURE_MODES.md -> kernel/CONSTITUTION.md
        self.assertIn(
            "kernel/CONSTITUTION.md",
            _refs("[Constitution](./CONSTITUTION.md)", citing="kernel/FAILURE_MODES.md"),
        )

    def test_bare_link_target_resolves_against_citing_dir(self):
        self.assertIn(
            "kernel/CONSTITUTION.md",
            _refs("[Constitution](CONSTITUTION.md)", citing="kernel/FAILURE_MODES.md"),
        )

    def test_parent_relative_link_resolves(self):
        self.assertIn(
            "README.md",
            _refs("[root readme](../README.md)", citing="docs/SOME_DOC.md"),
        )


class ExtractionExemptsNonCitations(unittest.TestCase):
    def test_fenced_code_block_contents_are_not_extracted(self):
        text = "before\n```sh\nrm kernel/FAILURE_MODES.md\npython3 src/episteme/cli.py\n```\nafter `docs/ARCHITECTURE.md`"
        targets = _refs(text)
        self.assertNotIn("kernel/FAILURE_MODES.md", targets)
        self.assertNotIn("src/episteme/cli.py", targets)
        # the real citation outside the fence still comes through
        self.assertIn("docs/ARCHITECTURE.md", targets)

    def test_tilde_fenced_block_contents_are_not_extracted(self):
        text = "~~~\nrm core/hooks/checkpoint.py\n~~~"
        self.assertNotIn("core/hooks/checkpoint.py", _refs(text))

    def test_url_is_not_extracted(self):
        self.assertEqual(set(), _refs("[repo](https://github.com/junjslee/episteme/blob/master/core/x.py)"))

    def test_tilde_home_path_is_not_extracted(self):
        self.assertEqual(set(), _refs("config at `~/.claude/settings.json`"))

    def test_absolute_path_is_not_extracted(self):
        self.assertEqual(set(), _refs("see `/Users/junlee/episteme/core/x.py`"))

    def test_glob_pattern_is_not_extracted(self):
        self.assertEqual(set(), _refs("matches `tests/test_*.py` and `core/schemas/*`"))

    def test_double_star_glob_is_not_extracted(self):
        self.assertEqual(set(), _refs("walks `docs/**/*.md`"))

    def test_brace_expansion_is_not_extracted(self):
        self.assertEqual(set(), _refs("`core/memory/global/{operator_profile, cognitive_profile}.md`"))

    def test_angle_bracket_template_is_not_extracted(self):
        self.assertEqual(set(), _refs("write `docs/<name>.md` for each"))

    def test_numbering_template_is_not_extracted(self):
        self.assertEqual(set(), _refs("checkpoint at `chkpt/YYYY-MM-DD.md`"))

    def test_envvar_prefixed_path_is_not_extracted(self):
        self.assertEqual(set(), _refs("run `${CLAUDE_PLUGIN_ROOT}/hooks/x.sh`"))

    def test_in_document_anchor_is_not_extracted(self):
        self.assertEqual(set(), _refs("[see below](#quick-start)"))

    def test_code_symbol_dotted_call_is_not_extracted(self):
        # subprocess.run / os.system / _framework.write_protocol look path-ish but '.run' etc. is not an allowlisted extension
        self.assertEqual(set(), _refs("we call `subprocess.run(['git','push'])` and `_framework.write_protocol`"))

    def test_concept_enum_with_slashes_is_not_extracted(self):
        self.assertEqual(set(), _refs("separate facts / inferences / preferences cleanly"))

    def test_commit_scope_token_is_not_extracted(self):
        self.assertEqual(set(), _refs("commit `feat(kernel): add gate` and `chore(chkpt): sync`"))

    def test_path_outside_allowlisted_prefix_is_not_extracted(self):
        # 'nonsense/' is not a real source root
        self.assertEqual(set(), _refs("see `nonsense/whatever.md`"))

    def test_ambiguous_bare_filename_is_not_extracted(self):
        # protocols.jsonl / hooks.json have no directory and are not well-known repo-root files
        self.assertEqual(set(), _refs("appended to `protocols.jsonl` and `hooks.json`"))

    def test_runtime_episteme_prefix_is_not_extracted(self):
        # .episteme/ is runtime/gitignored and not an allowlisted source prefix
        self.assertEqual(set(), _refs("the gate reads `.episteme/reasoning-surface.json`"))


class ExtractionRobustnessFromReview(unittest.TestCase):
    """Fixes for false-positives / false-negatives found by adversarial review."""

    def test_data_src_attribute_is_not_matched_as_src(self):
        # the 'src=' inside 'data-src=' (or 'xlink:href') is not an asset citation
        self.assertEqual(set(), _refs('<img data-src="docs/x.md">'))

    def test_real_src_and_href_attributes_still_matched(self):
        self.assertIn("docs/assets/a.svg", _refs('<img src="docs/assets/a.svg">'))
        self.assertIn("docs/ARCHITECTURE.md", _refs('<a href="docs/ARCHITECTURE.md">x</a>'))

    def test_stemless_dotfile_token_is_not_a_file(self):
        # `tests/.py` is a regex/pattern (empty stem), not a real file
        self.assertEqual(set(), _refs("matches `tests/.py` in the scanner"))

    def test_path_glued_to_nonascii_text_is_still_extracted(self):
        # operator writes mixed Korean/English; a path touching CJK must not vanish
        self.assertIn("core/hooks/checkpoint.py", _refs("설명은core/hooks/checkpoint.py 참고"))

    def test_manifest_hurl_dot_extensions_are_recognized(self):
        self.assertIn("benchmarks/x/TASKS.manifest", _refs("the `benchmarks/x/TASKS.manifest` corpus"))
        self.assertIn("contracts/orders.hurl", _refs("run `contracts/orders.hurl`"))
        self.assertIn("docs/graph.dot", _refs("render `docs/graph.dot`"))


class GitResolutionRobustness(unittest.TestCase):
    def test_git_ignored_returns_empty_when_git_binary_missing(self):
        from unittest import mock

        with mock.patch.object(dr.subprocess, "run", side_effect=FileNotFoundError):
            # fail toward flagging: exempt nothing rather than crash
            self.assertEqual(set(), dr.git_ignored(Path("/nowhere"), ["a/b.py"]))


class ResolutionTests(unittest.TestCase):
    """resolve_exists is filesystem truth (follow symlinks); dir-kind must be a dir."""

    def test_existing_file_resolves(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "core").mkdir()
            (root / "core" / "x.py").write_text("# x\n")
            ref = dr.Reference(raw="core/x.py", target="core/x.py", kind="file", line=1)
            self.assertTrue(dr.resolve_exists(root, ref))

    def test_missing_file_does_not_resolve(self):
        with tempfile.TemporaryDirectory() as d:
            ref = dr.Reference(raw="core/gone.py", target="core/gone.py", kind="file", line=1)
            self.assertFalse(dr.resolve_exists(Path(d), ref))

    def test_directory_citation_requires_a_directory(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "core").mkdir()
            (root / "core" / "hooks").mkdir()
            dir_ref = dr.Reference(raw="core/hooks/", target="core/hooks", kind="dir", line=1)
            self.assertTrue(dr.resolve_exists(root, dir_ref))
            # a dir citation that points at a file is drift
            (root / "core" / "afile.py").write_text("x\n")
            file_as_dir = dr.Reference(raw="core/afile.py/", target="core/afile.py", kind="dir", line=1)
            self.assertFalse(dr.resolve_exists(root, file_as_dir))

    def test_resolve_tries_citing_dir_relative_as_fallback(self):
        # A README inside a subdir cites paths relative to that subdir
        # (web/README.md -> `src/lib/x.ts` means web/src/lib/x.ts).
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "web" / "src" / "lib").mkdir(parents=True)
            (root / "web" / "src" / "lib" / "x.ts").write_text("y\n")
            ref = dr.Reference(raw="src/lib/x.ts", target="src/lib/x.ts", kind="file", line=1)
            self.assertFalse(dr.resolve_exists(root, ref))  # root-relative: missing
            self.assertTrue(dr.resolve_exists(root, ref, citing="web/README.md"))  # subdir: exists

    def test_symlink_target_is_followed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            real = root / "real.md"
            real.write_text("# real\n")
            link = root / "docs" / "LINKED.md"
            link.symlink_to(real)
            ref = dr.Reference(raw="docs/LINKED.md", target="docs/LINKED.md", kind="file", line=1)
            self.assertTrue(dr.resolve_exists(root, ref))


class FindDriftTests(unittest.TestCase):
    """find_drift flags nonexistent, non-gitignored citations; gitignore is injectable."""

    def test_subdir_readme_relative_citation_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "web" / "src" / "lib").mkdir(parents=True)
            (root / "web" / "src" / "lib" / "mode.ts").write_text("x\n")
            (root / "web" / "README.md").write_text("config in `src/lib/mode.ts`\n")
            findings = dr.find_drift(
                root, doc_files=["web/README.md"], ignored_checker=lambda p: set()
            )
            self.assertEqual([], findings)

    def test_dangling_reference_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "GUIDE.md").write_text("see `core/hooks/MISSING.py` for details\n")
            findings = dr.find_drift(root, doc_files=["docs/GUIDE.md"], ignored_checker=lambda paths: set())
            self.assertEqual(1, len(findings))
            self.assertEqual("core/hooks/MISSING.py", findings[0].target)
            self.assertEqual("docs/GUIDE.md", findings[0].citing_file)

    def test_resolving_reference_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "core").mkdir(parents=True)
            (root / "core" / "real.py").write_text("# real\n")
            (root / "docs" / "GUIDE.md").write_text("see `core/real.py`\n")
            findings = dr.find_drift(root, doc_files=["docs/GUIDE.md"], ignored_checker=lambda paths: set())
            self.assertEqual([], findings)

    def test_gitignored_dangling_reference_is_exempt(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "GUIDE.md").write_text("history note: `archive/OLD_DESIGN.md`\n")
            # archive/OLD_DESIGN.md does not exist, but the gitignore oracle says it's ignored -> exempt
            findings = dr.find_drift(
                root,
                doc_files=["docs/GUIDE.md"],
                ignored_checker=lambda paths: {p for p in paths if p.startswith("archive/")},
            )
            self.assertEqual([], findings)


class CitingScopeExemptions(unittest.TestCase):
    """Non-authored content (fixtures, scaffolds, install-relative templates,
    append-only ledgers) is excluded from the citing set by a named negative
    list — it references synthetic/destination paths, not the episteme tree."""

    def test_exempt_prefix_citing_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "benchmarks" / "x").mkdir(parents=True)
            (root / "benchmarks" / "x" / "README.md").write_text("cites `core/GONE.py`\n")
            findings = dr.find_drift(
                root, doc_files=["benchmarks/x/README.md"], ignored_checker=lambda p: set()
            )
            self.assertEqual([], findings)

    def test_exempt_citing_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "kernel").mkdir()
            (root / "kernel" / "CHANGELOG.md").write_text("history: `core/since_moved.py`\n")
            findings = dr.find_drift(
                root, doc_files=["kernel/CHANGELOG.md"], ignored_checker=lambda p: set()
            )
            self.assertEqual([], findings)

    def test_non_exempt_citing_file_is_still_scanned(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "REAL.md").write_text("cites `core/GONE.py`\n")
            findings = dr.find_drift(
                root, doc_files=["docs/REAL.md"], ignored_checker=lambda p: set()
            )
            self.assertEqual(1, len(findings))


# Baseline of pre-existing dangling references accepted as known debt at the
# time the linter was introduced. Format: "citing_file<TAB>target" per line.
# The linter enforces NO NEW drift beyond this set; entries are meant to be
# burned down, never grown. See tests/doc_references_baseline.txt.
_BASELINE_PATH = _REPO_ROOT / "tests" / "doc_references_baseline.txt"


def _load_baseline():
    pairs = set()
    if _BASELINE_PATH.exists():
        for line in _BASELINE_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            citing, _, target = line.partition("\t")
            pairs.add((citing.strip(), target.strip()))
    return pairs


class RealCorpusHasNoNewDrift(unittest.TestCase):
    """THE guardrail: no path cited in authored tracked markdown may dangle,
    except the explicitly-recorded pre-existing baseline. This fails when code
    is moved/renamed/deleted and a doc is left pointing at the old location."""

    def test_no_dangling_references_beyond_baseline(self):
        findings = dr.find_drift(_REPO_ROOT)
        baseline = _load_baseline()
        new = [f for f in findings if (f.citing_file, f.target) not in baseline]
        if new:
            lines = "\n".join(
                f"  {f.citing_file}:{f.line}  cites  {f.raw!r}  ->  {f.target} (missing)"
                for f in new
            )
            self.fail(
                f"{len(new)} NEW dangling doc->code reference(s) beyond the baseline:\n{lines}\n\n"
                "Fix the doc or the moved path. If the reference is intentionally "
                "forward-looking (a spec for unbuilt code), add 'citing_file<TAB>target' "
                "to tests/doc_references_baseline.txt with a justifying comment."
            )

    def test_baseline_has_no_stale_entries(self):
        # The baseline may only shrink: once drift is fixed, its entry must be
        # removed. A stale entry means a baselined reference now resolves.
        findings = dr.find_drift(_REPO_ROOT)
        live_pairs = {(f.citing_file, f.target) for f in findings}
        stale = sorted(p for p in _load_baseline() if p not in live_pairs)
        if stale:
            lines = "\n".join(f"  {c}\t{t}" for c, t in stale)
            self.fail(
                f"{len(stale)} stale baseline entr(ies) — the reference now resolves; "
                f"remove from tests/doc_references_baseline.txt:\n{lines}"
            )

    def test_planted_dangling_reference_is_caught_by_the_live_scanner(self):
        # Positive control: prove the scanner fires on real drift, so a passing
        # corpus run means "no new drift", not "scanner silently no-ops".
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            (root / "docs" / "PLANTED.md").write_text(
                "this doc cites `core/hooks/DEFINITELY_NOT_A_REAL_FILE.py`\n"
            )
            findings = dr.find_drift(
                root, doc_files=["docs/PLANTED.md"], ignored_checker=lambda paths: set()
            )
            self.assertTrue(
                any(f.target == "core/hooks/DEFINITELY_NOT_A_REAL_FILE.py" for f in findings),
                "scanner failed to flag a planted dangling reference",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
