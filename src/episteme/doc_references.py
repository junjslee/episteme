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
        _consider(m.group(1), citing, lineno, link=True, out=out)
    residual = _LINK_RE.sub(" ", residual)
    for m in _HTML_SRC_RE.finditer(residual):
        _consider(m.group(1), citing, lineno, link=True, out=out)
    residual = _HTML_ANY_ATTR_RE.sub(" ", residual)
    # Inline code spans: only a single whitespace-free token is a citation; a
    # span with spaces is an example command/expression, not a path.
    for m in _INLINE_CODE_RE.finditer(residual):
        content = m.group(1).strip()
        if content and not any(c.isspace() for c in content):
            _consider(content, citing, lineno, link=False, out=out)
    residual = _INLINE_CODE_RE.sub(" ", residual)
    # Bare prose paths in what remains.
    for m in _BARE_PATH_RE.finditer(residual):
        _consider(m.group(1), citing, lineno, link=False, out=out)


def _consider(
    raw: str, citing: str, lineno: int, link: bool, out: List[Reference]
) -> None:
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
