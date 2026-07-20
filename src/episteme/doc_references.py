"""Doc-to-code drift linter — pure extraction + injectable resolution.

Detects dangling path references in the repo's tracked markdown: a documentation
file that cites a code/doc artifact (``core/hooks/x.py``, ``docs/ARCHITECTURE.md``,
``kernel/``) which no longer resolves because the artifact was moved, renamed, or
deleted.

Two layers, deliberately separated so the hard part is pure and unit-testable:

  extract_references(text, citing)  ->  list[Reference]      (pure; no I/O)
  resolve_exists(repo_root, ref)    ->  bool                 (filesystem truth)
  find_drift(repo_root, ...)        ->  list[Finding]        (orchestration)

Extraction is a *positive system* (operator's positive/negative-system rule): a
token is treated as a checkable path ONLY if it carries an allowlisted extension
and sits under an allowlisted source-root prefix (or is a well-known repo-root
file). Everything else — URLs, ``~``/absolute paths, globs, brace-expansion,
``<name>`` templates, env-vars, in-document ``#anchors``, code symbols, and the
contents of fenced code blocks — is exempt by construction. Named negative
exceptions (e.g. historical ledgers) are enumerated, not inferred.

Resolution treats git's own ignore semantics as the oracle for environment-
dependent paths: a citation that does not exist on disk is drift ONLY if it is
not gitignored. That single rule covers the runtime ``.episteme/`` artifacts, the
local-only ``archive/`` sink, the gitignored ``core/memory/global/`` canonicals,
and the 14 private-symlink docs (which resolve on the maintainer's machine but
are absent in a clean CI clone) without hard-coding any of them.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Set

# --------------------------------------------------------------------------- #
# Positive-system configuration                                               #
# --------------------------------------------------------------------------- #

# Real source-root prefixes a documentation path citation may legitimately
# point into. A slashed candidate must start with one of these to be checked.
ALLOWLIST_PREFIXES: tuple[str, ...] = (
    "docs/",
    "kernel/",
    "core/",
    "src/",
    "tests/",
    "skills/",
    "adapters/",
    "templates/",
    "scripts/",
    "tools/",
    "hooks/",
    "web/",
    "benchmarks/",
    "contracts/",
    "demos/",
    "examples/",
    "labs/",
    "archive/",
    ".claude-plugin/",
    ".github/",
)

# Bare (no-directory) filenames that resolve at the repo root. Any other
# directory-less token is too ambiguous to validate and is skipped.
BARE_WELLKNOWN: frozenset[str] = frozenset(
    {
        "README.md",
        "README.ko.md",
        "README.es.md",
        "README.zh.md",
        "AGENTS.md",
        "INSTALL.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
        "LICENSE",
        "llms.txt",
        "pyproject.toml",
        "release-please-config.json",
    }
)

# Final-segment extensions that mark a token as a file-path candidate. Gating on
# this set rejects code symbols like ``subprocess.run`` and ``_framework.write``
# in one move (``run`` / ``write`` are not extensions).
FILE_EXTENSIONS: frozenset[str] = frozenset(
    {
        "md", "py", "json", "jsonl", "yaml", "yml", "txt", "sh", "svg",
        "gif", "png", "toml", "sha256", "cfg", "ini", "lock", "ts", "tsx", "js",
        # artifact extensions in this repo's ARTIFACT_TAXONOMY vocabulary
        "manifest", "hurl", "dot",
    }
)

# Named negative exceptions to the citing set. The linter validates *authored
# documentation about the episteme codebase*. The trees below are NOT that:
# they reference synthetic-scenario paths, fork-install destinations, or paths
# that have intentionally moved. Each is enumerated consciously, with evidence
# from the first corpus run, not inferred.
#
#   benchmarks/                    benchmark fixtures + generated run artifacts
#                                  describe synthetic repos, not this tree.
#   templates/                     project scaffolds reference the destination
#                                  project's paths (docs/REQUIREMENTS.md, ...),
#                                  created when the template is instantiated.
#   demos/                         captured demo transcripts/handoffs are
#                                  illustrative scenario fixtures.
#   core/memory/global/examples/   fork-install templates whose relative links
#                                  are written for the post-copy location (one
#                                  directory up), not the example's own depth.
EXEMPT_CITING_PREFIXES: tuple[str, ...] = (
    "benchmarks/",
    "templates/",
    "demos/",
    "core/memory/global/examples/",
)

# Individual citing files whose references are intentionally historical: they
# cite since-moved/deleted paths on purpose, and AGENTS.md forbids editing the
# entries (revisionism). Append-only ledger.
EXEMPT_CITING_FILES: frozenset[str] = frozenset(
    {
        "kernel/CHANGELOG.md",
    }
)


# --------------------------------------------------------------------------- #
# Data model                                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Reference:
    """A single validatable path citation found in a document."""

    raw: str        # the token exactly as it appeared
    target: str     # normalized repo-root-relative path (no trailing slash)
    kind: str       # "file" | "dir"
    line: int       # 1-based line number in the citing file


@dataclass(frozen=True)
class Finding:
    """A citation that does not resolve and is not environment-exempt."""

    citing_file: str
    line: int
    raw: str
    target: str


# --------------------------------------------------------------------------- #
# Extraction (pure)                                                           #
# --------------------------------------------------------------------------- #

_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
_LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*([^)\s]+?)\s*\)")
# Require an attribute-name boundary so `src=` inside `data-src=` / `xlink:href`
# (typically lazy-loaded runtime paths) does not match a real src/href attribute.
_HTML_SRC_RE = re.compile(r"""(?<![\w:-])(?:src|href)\s*=\s*["']([^"']+)["']""")
# Matches real AND prefixed (data-src, xlink:href) attributes — used to strip
# ALL of them from the line so a rejected attribute's value cannot fall through
# to the bare-path scan as a phantom citation.
_HTML_ANY_ATTR_RE = re.compile(r"""[\w:-]*(?:src|href)\s*=\s*["'][^"']*["']""")
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
# A bare prose path: a contiguous run of path characters ending in ``.ext``, not
# starting mid-token. The lookbehind is ASCII-only (not \w) so a path glued to
# non-ASCII text — e.g. Korean prose `설명은core/x.py` — is still seen.
_BARE_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_./~$-])([A-Za-z0-9_.][A-Za-z0-9_./-]*\.[A-Za-z0-9]+/?)"
)
_LINE_SUFFIX_RE = re.compile(r"^(.*\.[A-Za-z0-9]+):\d+(?::\d+)?$")
_TEMPLATE_RE = re.compile(r"YYYY|(?<![A-Za-z])NN(?![A-Za-z])|MM-DD")

# A GitHub-style ``owner/repo`` slug: two path-name segments. Used only to
# recognize *external-project* citations (Event 146 false-positive): a path
# that belongs to an upstream repo named on the same line is not a citation of
# THIS tree. ``owner`` must NOT be one of our own source roots
# (:data:`ALLOWLIST_PREFIXES`), so an in-repo path like ``core/hooks/x.py``
# (owner ``core`` is a real root) is never mistaken for an external slug.
_SLUG_SEG = r"[A-Za-z0-9][A-Za-z0-9._-]*"
_EXTERNAL_SLUG_PREFIX_RE = re.compile(rf"^({_SLUG_SEG})/{_SLUG_SEG}/")
_EXTERNAL_SLUG_BEFORE_RE = re.compile(rf"({_SLUG_SEG})/{_SLUG_SEG}[\s/`'\"(]*$")


def _cites_external_repo(line_text: str, raw: str) -> bool:
    """True if ``raw`` belongs to an upstream project cited by its
    ``owner/repo`` slug, not to this repo (Event 148 · smallfix #4).

    Two shapes are recognized, both conservative (they only ever suppress a
    finding, never create one, so the drift baseline cannot grow):

    * **slug-prefixed token** — the token itself begins ``owner/repo/…``
      (e.g. ``googleapis/release-please/README.md``); as a markdown link this
      would otherwise be joined onto the citing dir and flagged as a phantom
      local path.
    * **slug immediately preceding** — a bare source-root path (``src/foo.ts``)
      that appears right after an ``owner/repo`` slug on the line
      (``… facebook/react src/foo.ts``).

    In both shapes the slug ``owner`` must not be one of our allowlisted source
    roots, so genuine in-repo citations are never suppressed.
    """
    tok = raw.strip().strip("\"'")
    m = _EXTERNAL_SLUG_PREFIX_RE.match(tok)
    if m is not None and (m.group(1) + "/") not in ALLOWLIST_PREFIXES:
        return True
    idx = line_text.find(raw)
    if idx > 0:
        mb = _EXTERNAL_SLUG_BEFORE_RE.search(line_text[:idx])
        if mb is not None and (mb.group(1) + "/") not in ALLOWLIST_PREFIXES:
            return True
    return False


def extract_references(text: str, citing: str) -> List[Reference]:
    """Return the validatable path/directory citations in ``text``.

    ``citing`` is the repo-root-relative path of the document being scanned; it
    is used to resolve relative links against the citing file's directory.
    """
    out: List[Reference] = []
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        _scan_line(line, citing, lineno, out)
    return out


def _scan_line(line: str, citing: str, lineno: int, out: List[Reference]) -> None:
    residual = line
    # Markdown links / images first (link context resolves relative to citing dir).
    for m in _LINK_RE.finditer(line):
        _consider(m.group(1), citing, lineno, link=True, out=out, line_text=line)
    residual = _LINK_RE.sub(" ", residual)
    for m in _HTML_SRC_RE.finditer(residual):
        _consider(m.group(1), citing, lineno, link=True, out=out, line_text=line)
    residual = _HTML_ANY_ATTR_RE.sub(" ", residual)
    # Inline code spans: only a single whitespace-free token is a citation; a
    # span with spaces is an example command/expression, not a path.
    for m in _INLINE_CODE_RE.finditer(residual):
        content = m.group(1).strip()
        if content and not any(c.isspace() for c in content):
            _consider(content, citing, lineno, link=False, out=out, line_text=line)
    residual = _INLINE_CODE_RE.sub(" ", residual)
    # Bare prose paths in what remains.
    for m in _BARE_PATH_RE.finditer(residual):
        _consider(m.group(1), citing, lineno, link=False, out=out, line_text=line)


def _consider(
    raw: str, citing: str, lineno: int, link: bool, out: List[Reference],
    line_text: str = "",
) -> None:
    # Event 148 · smallfix #4: a path that belongs to an upstream project cited
    # by its owner/repo slug on the same line is not a citation of THIS tree.
    if _cites_external_repo(line_text, raw):
        return
    ref = _classify(raw, citing, link, lineno)
    if ref is not None and not any(
        r.target == ref.target and r.line == ref.line and r.kind == ref.kind
        for r in out
    ):
        out.append(ref)


def _classify(raw: str, citing: str, link: bool, lineno: int) -> Optional[Reference]:
    tok = raw.strip().strip("\"'")
    if not tok or "://" in tok or tok.startswith("#"):
        return None
    if tok[0] in "~/$" or "${" in tok:
        return None
    # Drop #fragment and ?query (cache-busters on assets).
    tok = tok.split("#", 1)[0]
    tok = re.sub(r"\?[\w=&.%-]*$", "", tok)
    if not tok:
        return None
    # Globs, brace-expansion, angle-bracket / date templates -> not literal paths.
    if any(c in tok for c in "*?[]{}<>"):
        return None
    if _TEMPLATE_RE.search(tok):
        return None

    is_dir = tok.endswith("/")
    norm = tok[:-1] if is_dir else tok

    # Resolution policy (standard markdown semantics):
    #   * ./ or ../          -> relative to the citing file's directory
    #   * already under a     -> root-relative, as written
    #     real source root
    #   * other link targets  -> relative to the citing dir (sibling/parent ref)
    #   * other prose tokens   -> root-relative (will fail the allowlist test)
    probe = norm + "/" if is_dir else norm
    if norm.startswith("./") or norm.startswith("../"):
        norm = os.path.normpath(os.path.join(os.path.dirname(citing), norm))
    elif _under_allowlist(probe):
        norm = os.path.normpath(norm)
    elif link:
        norm = os.path.normpath(os.path.join(os.path.dirname(citing), norm))
    else:
        norm = os.path.normpath(norm)
    norm = norm.replace(os.sep, "/")
    if norm.startswith("..") or norm.startswith("/") or norm in (".", ""):
        return None

    # Strip a :line(:col) suffix, but only when a real extension precedes it.
    m = _LINE_SUFFIX_RE.match(norm)
    if m:
        norm = m.group(1)

    if is_dir:
        if not _under_allowlist(norm + "/"):
            return None
        return Reference(raw=raw, target=norm, kind="dir", line=lineno)

    basename = norm.rsplit("/", 1)[-1]
    if "." in basename:
        stem, ext = basename.rsplit(".", 1)
        ext = ext.lower()
    else:
        stem, ext = basename, ""
    # An empty stem (`tests/.py`) is a regex/pattern, not a real file.
    if not stem or ext not in FILE_EXTENSIONS:
        return None
    if "/" not in norm:
        if norm in BARE_WELLKNOWN:
            return Reference(raw=raw, target=norm, kind="file", line=lineno)
        return None
    if not _under_allowlist(norm):
        return None
    return Reference(raw=raw, target=norm, kind="file", line=lineno)


def _under_allowlist(path: str) -> bool:
    return any(path.startswith(p) for p in ALLOWLIST_PREFIXES)


# --------------------------------------------------------------------------- #
# Resolution (filesystem + git)                                               #
# --------------------------------------------------------------------------- #


def resolve_exists(repo_root: Path, ref: Reference, citing: Optional[str] = None) -> bool:
    """True if the reference resolves in the working tree (symlinks followed).

    A citation resolves if it exists relative to the repo root OR relative to the
    citing file's directory. The second interpretation covers a README inside a
    sub-package (web/README.md) that cites paths relative to its own directory
    (``src/lib/x.ts`` meaning ``web/src/lib/x.ts``). The fallback only ever turns
    a *missing* path into a *present* one, so it removes false positives without
    masking real drift — a genuinely dead path exists under neither root.
    """
    root = Path(repo_root)
    candidates = [root / ref.target]
    if citing:
        citing_dir = os.path.dirname(citing)
        if citing_dir:
            candidates.append(root / citing_dir / ref.target)
    if ref.kind == "dir":
        return any(c.is_dir() for c in candidates)
    return any(c.exists() for c in candidates)


def tracked_markdown(repo_root: Path) -> List[str]:
    """Repo-root-relative paths of git-tracked ``*.md`` files.

    Tracked-only is what makes the citing-file set environment-stable: it
    excludes the gitignored private-symlink docs and any vendored markdown under
    node_modules, so the linter yields the same verdict locally and in CI.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z", "*.md"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "doc_references requires git to enumerate tracked markdown; "
            "pass an explicit doc_files list to run without it"
        ) from exc
    return [p for p in proc.stdout.split("\0") if p]


def git_ignored(repo_root: Path, paths: Iterable[str]) -> Set[str]:
    """The subset of ``paths`` that git considers ignored (batched, one call)."""
    items = [p for p in paths]
    if not items:
        return set()
    # Query each path in both bare and trailing-slash form: a dir-only
    # pattern (`archive/`) matches the bare spelling only while the
    # directory exists on disk, so the bare form alone gives a different
    # answer on a machine that has the local-only dir than on a fresh
    # clone. The slash form pins the directory interpretation regardless
    # of on-disk state, keeping the oracle machine-independent.
    queries = [q for p in items for q in (p, p.rstrip("/") + "/")]
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "check-ignore", "--stdin"],
            input="\n".join(queries),
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        # git binary absent: exempt nothing (fail toward flagging, not crashing).
        return set()
    # 0 = some ignored, 1 = none ignored; anything else is a git error, in which
    # case we exempt nothing (fail toward flagging rather than hiding drift).
    if proc.returncode not in (0, 1):
        return set()
    matched = {p.rstrip("/") for p in proc.stdout.split("\n") if p}
    return {p for p in items if p in matched or p.rstrip("/") in matched}


def find_drift(
    repo_root: Path,
    doc_files: Optional[Sequence[str]] = None,
    ignored_checker: Optional[Callable[[Iterable[str]], Set[str]]] = None,
) -> List[Finding]:
    """Return every dangling, non-gitignored path citation in tracked markdown."""
    root = Path(repo_root)
    if doc_files is None:
        doc_files = tracked_markdown(root)
    if ignored_checker is None:
        ignored_checker = lambda paths: git_ignored(root, paths)

    unresolved: List[tuple[str, Reference]] = []
    for rel in doc_files:
        if rel in EXEMPT_CITING_FILES or rel.startswith(EXEMPT_CITING_PREFIXES):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError):
            continue
        for ref in extract_references(text, rel):
            if not resolve_exists(root, ref, citing=rel):
                unresolved.append((rel, ref))

    ignored = ignored_checker({ref.target for _, ref in unresolved})
    return [
        Finding(citing_file=rel, line=ref.line, raw=ref.raw, target=ref.target)
        for rel, ref in unresolved
        if ref.target not in ignored
    ]


def _format_findings(findings: Sequence[Finding]) -> str:
    return "\n".join(
        f"  {f.citing_file}:{f.line}  cites  {f.raw!r}  ->  {f.target} (missing)"
        for f in findings
    )


# --------------------------------------------------------------------------- #
# Stale-citation cascade gate (Event 147, Mechanism 2)                         #
# --------------------------------------------------------------------------- #
#
# Counters FAILURE_MODES: stale-citation-cascade — a doc gets reclassified as
# design-history or tombstone, but the living docs that cite it keep pointing
# at it as though it were current, so a reader following the reference lands on
# a superseded artifact with no signal that it was retired. The lifecycle
# marker (Mechanism 1) makes each doc's status machine-readable; this gate makes
# the *edges* honor it: a status=living doc may not cite a status ∈
# {design-history, tombstone} doc unless the referencing line itself carries a
# historical qualifier that tells the reader the target is not current.
#
# Mechanically checkable, no operator judgment (M1): the qualifier test is a
# case-insensitive substring scan of the citing line against a fixed word set.
# Reuses the same citation walk as the drift linter (``extract_references``) so
# there is no second, divergent notion of "what a doc cites".

#: Lifecycle statuses whose docs must not be cited bare by a living doc.
HISTORICAL_STATUSES: frozenset[str] = frozenset({"design-history", "tombstone"})

#: Words that, present anywhere on the citing line, mark the reference as a
#: deliberate historical pointer (case-insensitive substring match). ``archive``
#: also covers ``archived``; ``supersede`` covers ``superseded``/``supersedes``.
HISTORICAL_QUALIFIERS: tuple[str, ...] = (
    "supersede",
    "retired",
    "historical",
    "archive",
    "design-history",
)


@dataclass(frozen=True)
class StaleCitation:
    """A living doc citing a design-history/tombstone doc without a qualifier."""

    citing_file: str
    line: int
    raw: str
    target: str
    target_status: str


def _line_has_qualifier(line_text: str) -> bool:
    """True iff the citing line carries a historical qualifier word."""
    low = line_text.lower()
    return any(q in low for q in HISTORICAL_QUALIFIERS)


def _lifecycle_status_map(repo_root: Path) -> dict:
    """Map tracked top-level doc paths -> lifecycle status (via doc_lifecycle).

    Imported lazily so ``doc_references`` stays importable without the lifecycle
    engine present, and so callers can inject an explicit ``status_map`` in tests
    without touching git or the filesystem.
    """
    from episteme import doc_lifecycle  # local import: avoid import-time coupling

    root = Path(repo_root)
    out: dict = {}
    for rel in doc_lifecycle.tracked_docs(root):
        marker = doc_lifecycle.parse_marker(root / rel)
        out[rel] = marker.status if marker is not None else None
    return out


def find_stale_citations(
    repo_root: Path,
    doc_files: Optional[Sequence[str]] = None,
    status_map: Optional[dict] = None,
) -> List[StaleCitation]:
    """Return every living-doc citation of a historical doc lacking a qualifier.

    Rule (Mechanism 2): a ``status=living`` doc may cite a doc whose status is in
    :data:`HISTORICAL_STATUSES` only if the citing line carries a word from
    :data:`HISTORICAL_QUALIFIERS`. Otherwise the citation is a ``stale-citation``
    finding.

    ``status_map`` (doc path -> status) is injectable for tests; when ``None`` it
    is derived from the lifecycle markers of the tracked corpus. ``doc_files``
    (the citing set) defaults to the docs that carry a ``living`` status in the
    map — the only docs the rule constrains.
    """
    root = Path(repo_root)
    smap = status_map if status_map is not None else _lifecycle_status_map(root)
    historical = {
        rel for rel, st in smap.items() if st in HISTORICAL_STATUSES
    }
    if doc_files is None:
        doc_files = sorted(rel for rel, st in smap.items() if st == "living")

    findings: List[StaleCitation] = []
    for rel in doc_files:
        if smap.get(rel) != "living":
            continue
        if rel in EXEMPT_CITING_FILES or rel.startswith(EXEMPT_CITING_PREFIXES):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError):
            continue
        lines = text.splitlines()
        for ref in extract_references(text, rel):
            if ref.target not in historical:
                continue
            line_text = lines[ref.line - 1] if 0 <= ref.line - 1 < len(lines) else ""
            if _line_has_qualifier(line_text):
                continue
            findings.append(
                StaleCitation(
                    citing_file=rel,
                    line=ref.line,
                    raw=ref.raw,
                    target=ref.target,
                    target_status=smap[ref.target],
                )
            )
    return findings


def _format_stale_citations(findings: Sequence[StaleCitation]) -> str:
    return "\n".join(
        f"  {f.citing_file}:{f.line}  cites  {f.raw!r}  ->  {f.target} "
        f"({f.target_status}, no historical qualifier)"
        for f in findings
    )


# --------------------------------------------------------------------------- #
# Code→doc reverse index (Event 173)                                           #
# --------------------------------------------------------------------------- #
#
# Counters FAILURE_MODES: doc-code drift discovered late — a code edit lands,
# the docs that claim to describe that code stay unchanged, and the divergence
# is only found by a later batch sweep (the E172 class of repair). The citation
# walk above already materializes every doc→code edge, and CI keeps those edges
# non-dangling; INVERTING them answers "which docs claim to describe this code
# path" with zero hand-maintained state, so the map itself cannot rot.
#
# Rule-shape (operator's positive/negative-system rule): positive system — an
# obligation exists ONLY where a live authored doc cites the path (exact file,
# or an enclosing directory via a ``dir`` citation). Uncited code carries no
# obligation. The citing set excludes the fixture/scaffold trees
# (:data:`EXEMPT_CITING_PREFIXES`), the historical ledgers
# (:data:`EXEMPT_CITING_FILES`), and ``archive/`` — frozen history must not
# generate present-tense obligations.
#
# Replaces (anti-accretion): the path-blind static advisory in
# ``core/hooks/workflow_guard.py``. That hook now consumes
# :func:`docs_for_path` and names the actual citing docs, keeping the generic
# string only as fallback when this module is unimportable (plugin context,
# non-git project) or the edited path has no citing docs.

#: Citing prefixes that never generate edit-time obligations. Extends the
#: linter's exemptions with ``archive/``: archived reports legitimately cite
#: code (they are validated for drift above), but a frozen point-in-time
#: artifact must not obligate present-day edits.
OBLIGATION_EXEMPT_CITING_PREFIXES: tuple[str, ...] = EXEMPT_CITING_PREFIXES + (
    "archive/",
)


@dataclass(frozen=True)
class DocEdge:
    """One inverted citation: ``doc`` claims to describe ``target``."""

    doc: str      # citing doc, repo-root-relative
    target: str   # resolved cited path, repo-root-relative, no trailing slash
    kind: str     # "file" | "dir"
    line: int     # 1-based line in the citing doc


def _edge_target(root: Path, ref: Reference, citing: str) -> str:
    """The repo-relative path this citation claims to describe.

    Mirrors :func:`resolve_exists`'s two-root policy and returns WHICH
    interpretation resolved — the reverse index must key edges by the real
    on-disk path (``web/src/lib/x.ts``), not the citing-relative spelling
    (``src/lib/x.ts``). An UNRESOLVED citation keeps its root-relative
    spelling rather than vanishing: a citation is a CLAIM, and a doc that
    cites a not-yet-existing file must still obligate the Write that creates
    it (E173 review finding — dropping these made the index depend on target
    existence, which the markdown-only cache digest cannot observe, so the
    cache served stale empty answers for pre-documented new files). Dangling
    claims remain :func:`find_drift`'s findings; here they are edges.
    """
    probe = root / ref.target
    if probe.is_dir() if ref.kind == "dir" else probe.exists():
        return ref.target
    citing_dir = os.path.dirname(citing)
    if citing_dir:
        alt = os.path.normpath(os.path.join(citing_dir, ref.target)).replace(
            os.sep, "/"
        )
        alt_probe = root / alt
        if alt_probe.is_dir() if ref.kind == "dir" else alt_probe.exists():
            return alt
    return ref.target


def build_reverse_index(
    repo_root: Path,
    doc_files: Optional[Sequence[str]] = None,
) -> dict:
    """Map claimed cited path → list[:class:`DocEdge`] over the live corpus.

    ``doc_files`` is injectable for tests (same contract as :func:`find_drift`);
    when ``None`` the tracked-markdown corpus is used. One edge per
    (doc, target, kind) — repeated citations of the same path by the same doc
    collapse to the first occurrence. Unresolved citations are indexed as
    claims (see :func:`_edge_target`), keeping the index a pure function of
    the markdown corpus — the property the cache digest relies on.
    """
    root = Path(repo_root)
    if doc_files is None:
        doc_files = tracked_markdown(root)
    index: dict = {}
    for rel in doc_files:
        if rel in EXEMPT_CITING_FILES or rel.startswith(
            OBLIGATION_EXEMPT_CITING_PREFIXES
        ):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeError):
            continue
        for ref in extract_references(text, rel):
            target = _edge_target(root, ref, citing=rel)
            edges = index.setdefault(target, [])
            if not any(e.doc == rel and e.kind == ref.kind for e in edges):
                edges.append(
                    DocEdge(doc=rel, target=target, kind=ref.kind, line=ref.line)
                )
    return index


def _normalize_query_path(root: Path, path: str) -> Optional[str]:
    """Normalize a query path to repo-root-relative form, or ``None``.

    Accepts absolute paths (hook payloads carry absolute ``file_path``) and
    repo-relative spellings; a path outside ``root`` yields ``None``.
    """
    norm = str(path).replace("\\", "/")
    if os.path.isabs(norm):
        try:
            norm = str(Path(norm).resolve().relative_to(Path(root).resolve()))
        except (ValueError, OSError):
            return None
    norm = os.path.normpath(norm).replace(os.sep, "/")
    if norm in (".", "") or norm.startswith(".."):
        return None
    return norm


def docs_for_path(
    repo_root: Path,
    path: str,
    index: Optional[dict] = None,
    doc_files: Optional[Sequence[str]] = None,
) -> List[str]:
    """Sorted docs that cite ``path`` — exactly, or via an enclosing dir.

    Self-citations are excluded (a doc citing itself creates no obligation).
    Raises nothing extra beyond :func:`build_reverse_index`'s git requirement
    when ``index``/``doc_files`` are not supplied.
    """
    root = Path(repo_root)
    if index is None:
        index = build_reverse_index(root, doc_files=doc_files)
    norm = _normalize_query_path(root, path)
    if norm is None:
        return []
    hits = {e.doc for e in index.get(norm, ()) if e.doc != norm}
    for edges in index.values():
        for e in edges:
            if (
                e.kind == "dir"
                and e.doc != norm
                and (norm == e.target or norm.startswith(e.target + "/"))
            ):
                hits.add(e.doc)
    return sorted(hits)


def edges_for_path(
    repo_root: Path,
    path: str,
    index: Optional[dict] = None,
    doc_files: Optional[Sequence[str]] = None,
) -> List[DocEdge]:
    """The citing edges for ``path``, strongest claim first.

    Exact-file citations are strong claims ("this doc describes THIS file") and
    sort before directory citations (weak: the doc mentions an enclosing tree);
    within dir edges, the most specific (longest) target wins. One edge per
    citing doc — a doc citing both the file and its directory contributes only
    its file edge. Self-citations excluded.
    """
    root = Path(repo_root)
    if index is None:
        index = build_reverse_index(root, doc_files=doc_files)
    norm = _normalize_query_path(root, path)
    if norm is None:
        return []
    best: dict = {}
    for e in index.get(norm, ()):
        if e.doc != norm:
            best[e.doc] = e
    for edges in index.values():
        for e in edges:
            if (
                e.kind == "dir"
                and e.doc != norm
                and e.doc not in best
                and (norm == e.target or norm.startswith(e.target + "/"))
            ):
                held = best.get(e.doc)
                if held is None or (
                    held.kind == "dir" and len(e.target) > len(held.target)
                ):
                    best[e.doc] = e
    return sorted(
        best.values(),
        key=lambda e: (e.kind != "file", -len(e.target), e.doc),
    )


#: Reverse-index cache schema version; bump when DocEdge shape or extraction
#: semantics change so stale caches self-invalidate.
_CACHE_VERSION = 1


def _corpus_digest(root: Path, doc_files: Sequence[str]) -> Optional[str]:
    """sha256 over (path, mtime_ns, size) of the obligation-citing corpus."""
    import hashlib

    h = hashlib.sha256()
    h.update(f"v{_CACHE_VERSION}".encode())
    for rel in sorted(doc_files):
        if rel in EXEMPT_CITING_FILES or rel.startswith(
            OBLIGATION_EXEMPT_CITING_PREFIXES
        ):
            continue
        try:
            st = os.stat(root / rel)
        except OSError:
            return None
        h.update(f"{rel}\0{st.st_mtime_ns}\0{st.st_size}\n".encode())
    return h.hexdigest()


def cached_reverse_index(repo_root: Path) -> dict:
    """:func:`build_reverse_index` behind an mtime-digest cache.

    A cold build costs ~200ms on this repo's corpus — too heavy for a
    per-edit PreToolUse hook — while the digest check costs ~25ms. The cache
    lives at ``.episteme/cache/doc_map.json`` and is written ONLY when
    ``.episteme/`` already exists (positive system: episteme caches where it
    already has a footprint, never scattering dotdirs into foreign projects).
    Every cache failure — unreadable, stale, malformed — degrades to a fresh
    build; a wrong answer is never served to avoid a rebuild.
    """
    import json as _json

    root = Path(repo_root)
    doc_files = tracked_markdown(root)  # raises RuntimeError without git — caller's contract
    digest = _corpus_digest(root, doc_files)
    cache_path = root / ".episteme" / "cache" / "doc_map.json"

    if digest is not None:
        try:
            payload = _json.loads(cache_path.read_text(encoding="utf-8"))
            if (
                payload.get("version") == _CACHE_VERSION
                and payload.get("digest") == digest
            ):
                return {
                    target: [
                        DocEdge(doc=d, target=target, kind=k, line=ln)
                        for d, k, ln in rows
                    ]
                    for target, rows in payload.get("targets", {}).items()
                }
        except (OSError, ValueError, TypeError):
            pass

    index = build_reverse_index(root, doc_files=doc_files)

    if digest is not None and (root / ".episteme").is_dir():
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            # pid-suffixed: two concurrent hook processes must not interleave
            # writes into one tmp file (review nit; replace() stays atomic).
            tmp = cache_path.with_suffix(f".json.tmp.{os.getpid()}")
            tmp.write_text(
                _json.dumps(
                    {
                        "version": _CACHE_VERSION,
                        "digest": digest,
                        "targets": {
                            target: [[e.doc, e.kind, e.line] for e in edges]
                            for target, edges in index.items()
                        },
                    }
                ),
                encoding="utf-8",
            )
            tmp.replace(cache_path)
        except OSError:
            pass
    return index


def annotate_docs(repo_root: Path, docs: Sequence[str]) -> List[tuple]:
    """``(doc, label)`` pairs for display: lifecycle state, or manifest tier.

    Labels, in precedence order: a parsed lifecycle marker renders as
    ``status · reviewed_as_of`` plus ``· N events behind`` when the marker is
    event-tagged and ``docs/EVENTS.md`` yields a later corpus event (same
    ``E<n>`` scan as session_context's staleness banner — conscious sibling);
    a manifest-managed kernel file renders as ``manifest-managed``; anything
    else gets an empty label. Every lookup degrades to a weaker label rather
    than raising — annotation must never break a caller's advisory.
    """
    root = Path(repo_root)
    latest_event: Optional[int] = None
    try:
        events_text = (root / "docs" / "EVENTS.md").read_text(
            encoding="utf-8", errors="replace"
        )
        nums = [int(m) for m in re.findall(r"\bE(\d+)\b", events_text)]
        if nums:
            latest_event = max(nums)
    except OSError:
        latest_event = None

    managed: frozenset = frozenset()
    try:
        from episteme.kernel_integrity import MANAGED_KERNEL_FILES

        managed = frozenset(MANAGED_KERNEL_FILES)
    except Exception:
        managed = frozenset()

    out: List[tuple] = []
    for rel in docs:
        label = ""
        marker = None
        try:
            from episteme import doc_lifecycle

            marker = doc_lifecycle.parse_marker(root / rel)
        except Exception:
            marker = None
        if marker is not None and marker.status:
            label = marker.status
            if marker.reviewed_as_of:
                label += f" · {marker.reviewed_as_of}"
                ev = re.match(r"^E(\d+)$", marker.reviewed_as_of)
                if ev is not None and latest_event is not None:
                    lag = latest_event - int(ev.group(1))
                    if lag > 0:
                        label += f" · {lag} events behind"
        elif rel in managed:
            label = "manifest-managed"
        out.append((rel, label))
    return out


def run_map_cli(root: Optional[Path] = None, paths: Sequence[str] = ()) -> int:
    """``episteme docs map [path ...]`` — query or dump the reverse index.

    With paths: the citing docs (annotated) per path. Without: the full
    ``target ← docs`` map. Informational — always exits 0; an empty answer is
    an answer (positive system: no citation, no obligation).
    """
    from episteme.doc_lifecycle import _repo_root  # one notion of root resolution

    root = Path(root) if root is not None else _repo_root()
    try:
        index = cached_reverse_index(root)  # warms the same cache the hook reads
    except RuntimeError as exc:
        print(f"docs map: {exc}")
        return 1
    if not paths:
        if not index:
            print("docs map: no citation edges in tracked markdown")
            return 0
        for target in sorted(index):
            cited_by = sorted({e.doc for e in index[target]})
            print(f"{target}  ←  {', '.join(cited_by)}")
        return 0
    for query in paths:
        edges = edges_for_path(root, query, index=index)
        if not edges:
            print(f"{query}: no citing docs — no doc claims to describe this path")
            continue
        print(f"{query}:")
        labels = dict(annotate_docs(root, [e.doc for e in edges]))
        for e in edges:
            label = labels.get(e.doc, "")
            via = f"  [via {e.target}/]" if e.kind == "dir" else ""
            print(f"  {e.doc}" + (f"  ({label})" if label else "") + via)
    return 0


if __name__ == "__main__":  # pragma: no cover
    import sys

    root = Path(__file__).resolve().parents[2]
    exit_code = 0
    result = find_drift(root)
    if result:
        print(f"{len(result)} dangling doc->code reference(s):")
        print(_format_findings(result))
        exit_code = 1
    stale = find_stale_citations(root)
    if stale:
        print(f"{len(stale)} stale citation(s) of historical docs by living docs:")
        print(_format_stale_citations(stale))
        exit_code = 1
    if exit_code == 0:
        print("doc references: clean")
    sys.exit(exit_code)
