"""Doc budget — the compaction linter (blueprint §1.4).

Enforces bounded working memory as code, the doc-layer analog of the ledger's
content-key dedup + compaction. Two invariants:

  * Tracked top-level ``docs/*.md`` count stays under a ceiling. Raising it means
    editing the constant here — the edit IS the conscious decision, which is the
    whole point of a budget-as-code (accretion cannot happen silently).
  * Planning-state / operational-record docs (PROGRESS / NEXT_STEPS / ROADMAP)
    never re-enter the tracked tree — they are private-only working memory
    (symlinked to ``~/episteme-private``, gitignored).

Registered against FAILURE_MODES: unbounded-accumulation (Event 145). The
generation rate of doc artifacts had exceeded their consumption rate at every
class; this test is the standing counter for the tracked-doc class.

Event 147 reseat: the doc-lifecycle marker contract (``src/episteme/doc_lifecycle.py``)
subsumes the ad-hoc corpus walk. This module now BOUNDS that engine — it runs
``doc_lifecycle.lint()`` over the tracked corpus as the standing gate that every
tracked ``docs/*.md`` carries a valid lifecycle marker (positive system), rather
than duplicating a second parallel walk. The 32-file ceiling and the
no-planning-state invariant are retained unchanged.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from episteme import doc_lifecycle  # noqa: E402

# Ceiling for tracked top-level ``docs/*.md``. Current tracked count is 31.
# Bumping this is a deliberate act — change the number here and the edit is the
# conscious decision the budget exists to force.
_TRACKED_DOCS_CEILING = 32

# Planning-state docs are private-only. Anchored at the basename START so
# ``kernel/MODEL_PROGRESS_RISK_MODEL.md`` (contains "PROGRESS" mid-name) and any
# other legitimate doc that merely embeds one of these words is NOT flagged.
_FORBIDDEN_BASENAME = re.compile(r"^(PROGRESS|NEXT_STEPS|ROADMAP)", re.IGNORECASE)

# Named non-authored trees — scaffolds/fixtures that SHIP empty PROGRESS/
# NEXT_STEPS starter stubs for fork users (`episteme init` copies them). These
# are product scaffolding, not the operator's live planning state, so they are
# a conscious negative-system exemption. Same tree set the doc-reference linter
# names non-authored (src/episteme/doc_references.py).
_NON_AUTHORED_PREFIXES = ("templates/", "demos/", "benchmarks/")


def _git_tracked(*pathspec: str) -> list[str]:
    """Tracked paths (optionally filtered by pathspec), repo-root relative."""
    out = subprocess.run(
        ["git", "ls-files", *pathspec],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


class TrackedDocCountUnderCeiling(unittest.TestCase):
    def test_tracked_top_level_docs_md_under_ceiling(self):
        # Top-level docs/<name>.md only (exactly one slash); asset/subdir files
        # are not planning docs and are out of scope for the doc-zoo budget.
        tracked = [p for p in _git_tracked("docs/*.md") if p.count("/") == 1]
        self.assertLessEqual(
            len(tracked),
            _TRACKED_DOCS_CEILING,
            f"tracked docs/*.md = {len(tracked)} exceeds ceiling "
            f"{_TRACKED_DOCS_CEILING}. The doc-compaction budget is breached: "
            f"archive or privatize a doc before adding one, or raise "
            f"_TRACKED_DOCS_CEILING here as a conscious decision. Tracked set:\n  "
            + "\n  ".join(sorted(tracked)),
        )


class NoPlanningStateInTrackedTree(unittest.TestCase):
    def test_no_tracked_progress_nextsteps_roadmap(self):
        offenders = [
            p
            for p in _git_tracked()
            if _FORBIDDEN_BASENAME.match(Path(p).name)
            and not p.startswith(_NON_AUTHORED_PREFIXES)
        ]
        self.assertEqual(
            offenders,
            [],
            "planning-state docs (PROGRESS / NEXT_STEPS / ROADMAP) must be "
            "private-only working memory (symlink to ~/episteme-private/docs, "
            "gitignore the symlink) — they may not be tracked anywhere in the "
            "tree. Found tracked:\n  " + "\n  ".join(offenders),
        )


class TrackedDocsCarryLifecycleMarker(unittest.TestCase):
    """Reseat (Event 147): every tracked ``docs/*.md`` carries a valid marker.

    This runs the portable lifecycle linter over the real corpus. A missing or
    malformed marker (positive system — only the five enumerated statuses
    validate) is a hard failure, so a new tracked doc cannot enter the tree
    without a conscious lifecycle classification at creation.
    """

    def test_corpus_lint_is_clean(self):
        findings = doc_lifecycle.lint(_REPO_ROOT)
        self.assertEqual(
            findings,
            [],
            "doc lifecycle marker violations in the tracked corpus:\n"
            + doc_lifecycle.format_findings(findings),
        )


if __name__ == "__main__":
    unittest.main()
