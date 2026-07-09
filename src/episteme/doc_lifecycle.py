"""Doc/artifact lifecycle engine — machine-readable status markers as code.

Event 147, Mechanism 1. Counters FAILURE_MODES: doc-staleness-invisibility —
a tracked ``docs/*.md`` had no machine-readable lifecycle state, so a stale or
superseded doc was indistinguishable from a live one to every automated signal
path. This module makes the classification explicit at line 1 of every doc and
turns it into a lint gate + a self-healing index.

BOUNDS (anti-accretion, PLAYBOOK:220), does NOT add a parallel path:
``tests/test_doc_budget.py`` is reseated onto ``lint()`` here (the marker
contract subsumes the ad-hoc ceiling test's corpus walk) and the doc index in
``docs/README.md`` is generated from these markers rather than hand-listed.

## Marker contract

Line 1 of every tracked ``docs/*.md`` (symlinks skipped) carries a render-
invisible HTML comment::

    <!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->
    <!-- episteme-lifecycle: status=design-history; reviewed_as_of=E147; superseded_by=docs/DESIGN_V2_0_EPISTEMIC_ENGINE.md -->

Keys:

* ``status`` (required) ∈ {living, spec-implemented, design-history, report,
  tombstone}. Positive system — only the five enumerated statuses validate; a
  tracked ``docs/*.md`` with no marker is a lint failure (classification forced
  at creation, not inferred later).
* ``reviewed_as_of`` (required) — ``E<n>`` event tag or ISO date.
* ``superseded_by`` (required iff status=design-history; optional scoped
  pointer on a living doc).
* ``scope`` (optional) — qualifies a scoped supersession on a living doc.

## Portability

Repo-specific values (docs dir, report grandfather list) come from config
discovery — ``[tool.episteme]`` in ``pyproject.toml`` or ``.episteme/config.json``
— never hardcoded here. Another repo adopts the mechanism via ``episteme sync``
plus config alone. Default docs dir is ``docs/``.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

try:  # Python 3.11+ stdlib; fall back to tomli if ever run under 3.10.
    import tomllib as _tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - defensive for <3.11
    try:
        import tomli as _tomllib  # type: ignore[import-not-found, no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        _tomllib = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- #
# Vocabulary                                                                   #
# --------------------------------------------------------------------------- #

#: The five enumerated lifecycle statuses. Positive system: only these validate.
VALID_STATUSES: frozenset[str] = frozenset(
    {"living", "spec-implemented", "design-history", "report", "tombstone"}
)

#: Statuses that mandate a ``superseded_by`` pointer.
_REQUIRES_SUPERSEDED_BY: frozenset[str] = frozenset({"design-history"})

#: Default report docs allowed to remain tracked under status=report (the
#: report-sink grandfather list). Overridable via config; new reports must land
#: in ``archive/reports/`` or attach to EVENTS entries rather than accrete here.
_DEFAULT_REPORT_GRANDFATHER: tuple[str, ...] = (
    "docs/EVALUATION_METHOD.md",
    "docs/OSF_PRE_REGISTRATION_DRAFT.md",
    "docs/ADAPTER_PORTABILITY.md",
)

#: Index splice markers in the docs README.
INDEX_START = "<!-- episteme-docs-index:start -->"
INDEX_END = "<!-- episteme-docs-index:end -->"

# ``<!-- episteme-lifecycle: <body> -->`` anywhere on the first line.
_MARKER_RE = re.compile(r"<!--\s*episteme-lifecycle:\s*(?P<body>.*?)\s*-->")
# Strip any HTML comment (incl. volatile-fact spans) when deriving a purpose.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->")


# --------------------------------------------------------------------------- #
# Config discovery                                                             #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Config:
    """Repo-specific lifecycle configuration (portable via discovery)."""

    docs_dir: str = "docs"
    report_grandfather: tuple[str, ...] = _DEFAULT_REPORT_GRANDFATHER


def discover_config(root: Path) -> Config:
    """Resolve lifecycle config for ``root``.

    Precedence: ``.episteme/config.json`` (local override) > ``pyproject.toml``
    ``[tool.episteme]`` (tracked, portable) > built-in defaults. Any malformed
    source degrades to the next source rather than raising — config discovery
    must never break the lint gate.
    """
    root = Path(root)
    data: Dict[str, object] = {}

    pyproject = root / "pyproject.toml"
    if _tomllib is not None and pyproject.is_file():
        try:
            with open(pyproject, "rb") as fh:
                parsed = _tomllib.load(fh)
            tool = parsed.get("tool")
            if isinstance(tool, dict):
                section = tool.get("episteme")
                if isinstance(section, dict):
                    data.update(section)
        except (OSError, ValueError):
            pass

    cfg_json = root / ".episteme" / "config.json"
    if cfg_json.is_file():
        try:
            parsed_json = json.loads(cfg_json.read_text(encoding="utf-8"))
            if isinstance(parsed_json, dict):
                data.update(parsed_json)
        except (OSError, ValueError):
            pass

    docs_dir = data.get("docs_dir", "docs")
    if not isinstance(docs_dir, str) or not docs_dir.strip():
        docs_dir = "docs"
    docs_dir = docs_dir.strip().rstrip("/")

    raw_grandfather = data.get("report_grandfather")
    if isinstance(raw_grandfather, (list, tuple)) and all(
        isinstance(x, str) for x in raw_grandfather
    ):
        report_grandfather: tuple[str, ...] = tuple(raw_grandfather)
    else:
        report_grandfather = _DEFAULT_REPORT_GRANDFATHER

    return Config(docs_dir=docs_dir, report_grandfather=report_grandfather)


# --------------------------------------------------------------------------- #
# Data model                                                                   #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Marker:
    """A parsed ``episteme-lifecycle`` marker (line 1 of a doc)."""

    status: str
    reviewed_as_of: str
    superseded_by: Optional[str] = None
    scope: Optional[str] = None
    extra: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Finding:
    """A lint violation against the marker contract."""

    file: str
    line: int
    kind: str
    message: str


# --------------------------------------------------------------------------- #
# Parsing                                                                      #
# --------------------------------------------------------------------------- #


def _parse_marker_body(body: str) -> Dict[str, str]:
    """Parse ``k=v; k=v`` pairs from a marker body into a dict."""
    out: Dict[str, str] = {}
    for chunk in body.split(";"):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        key, _, value = chunk.partition("=")
        key = key.strip()
        value = value.strip()
        if key:
            out[key] = value
    return out


def parse_marker_text(first_line: str) -> Optional[Marker]:
    """Parse a marker from a single line of text, or ``None`` if absent."""
    match = _MARKER_RE.search(first_line)
    if match is None:
        return None
    kv = _parse_marker_body(match.group("body"))
    known = {"status", "reviewed_as_of", "superseded_by", "scope"}
    extra = {k: v for k, v in kv.items() if k not in known}
    return Marker(
        status=kv.get("status", ""),
        reviewed_as_of=kv.get("reviewed_as_of", ""),
        superseded_by=kv.get("superseded_by") or None,
        scope=kv.get("scope") or None,
        extra=extra,
    )


def parse_marker(path: Path) -> Optional[Marker]:
    """Return the lifecycle marker on line 1 of ``path``, or ``None``.

    ``None`` means the first line carries no ``episteme-lifecycle`` comment —
    the caller (``lint``) treats that as a missing-marker finding. Read errors
    also yield ``None`` so a transient IO failure surfaces as a lint finding
    rather than a crash.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            first_line = fh.readline()
    except OSError:
        return None
    return parse_marker_text(first_line)


# --------------------------------------------------------------------------- #
# Corpus enumeration                                                           #
# --------------------------------------------------------------------------- #


def tracked_docs(root: Path, config: Optional[Config] = None) -> List[str]:
    """Repo-root-relative paths of tracked top-level ``<docs_dir>/*.md`` files.

    Excludes symlinks (private planning docs are symlinked and lifecycle-exempt)
    and any nested path (assets/subdirs are out of scope). Tracked-only keeps
    the corpus environment-stable between a maintainer checkout and a clean CI
    clone.
    """
    root = Path(root)
    cfg = config or discover_config(root)
    docs_dir = cfg.docs_dir
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", f"{docs_dir}/*.md"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            "doc_lifecycle requires git to enumerate tracked docs; run inside "
            "a git working tree"
        ) from exc
    out: List[str] = []
    for rel in proc.stdout.split("\0"):
        if not rel:
            continue
        # Top-level only: exactly ``<docs_dir>/<name>.md`` (one slash).
        if rel.count("/") != 1:
            continue
        if (root / rel).is_symlink():
            continue
        out.append(rel)
    return sorted(out)


# --------------------------------------------------------------------------- #
# Lint                                                                         #
# --------------------------------------------------------------------------- #


def lint(root: Path, config: Optional[Config] = None) -> List[Finding]:
    """Validate every tracked top-level doc against the marker contract.

    Failing findings (positive system): a doc with no marker, an unrecognised
    status, a missing ``reviewed_as_of``, or a ``design-history`` doc without a
    ``superseded_by`` pointer. Deterministic order (by file, then line).
    """
    root = Path(root)
    cfg = config or discover_config(root)
    findings: List[Finding] = []
    for rel in tracked_docs(root, cfg):
        marker = parse_marker(root / rel)
        if marker is None:
            findings.append(
                Finding(
                    file=rel,
                    line=1,
                    kind="missing-marker",
                    message=(
                        "no episteme-lifecycle marker on line 1 — every tracked "
                        f"{cfg.docs_dir}/*.md must declare status + reviewed_as_of "
                        "at creation (positive system)"
                    ),
                )
            )
            continue
        if marker.status not in VALID_STATUSES:
            findings.append(
                Finding(
                    file=rel,
                    line=1,
                    kind="invalid-status",
                    message=(
                        f"status={marker.status!r} is not one of "
                        f"{sorted(VALID_STATUSES)}"
                    ),
                )
            )
        if not marker.reviewed_as_of:
            findings.append(
                Finding(
                    file=rel,
                    line=1,
                    kind="missing-reviewed-as-of",
                    message="marker is missing the required reviewed_as_of key",
                )
            )
        if marker.status in _REQUIRES_SUPERSEDED_BY and not marker.superseded_by:
            findings.append(
                Finding(
                    file=rel,
                    line=1,
                    kind="missing-superseded-by",
                    message=(
                        f"status={marker.status} requires a superseded_by pointer"
                    ),
                )
            )
    return findings


def format_findings(findings: Sequence[Finding]) -> str:
    """Render findings as one human-readable line each."""
    return "\n".join(
        f"  {f.file}:{f.line}  [{f.kind}]  {f.message}" for f in findings
    )


# --------------------------------------------------------------------------- #
# Index generation                                                             #
# --------------------------------------------------------------------------- #


def _doc_purpose(path: Path) -> str:
    """Derive a one-line purpose from a doc's first H1 heading.

    Strips HTML comments (marker + volatile-fact spans keep their inner value)
    and collapses whitespace. Falls back to an empty string when no H1 exists.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("# "):
            title = _HTML_COMMENT_RE.sub("", stripped[2:])
            return re.sub(r"\s+", " ", title).strip()
    return ""


def generate_index(root: Path, config: Optional[Config] = None) -> str:
    """Return the generated docs-index body (markdown list) from markers.

    One line per tracked top-level doc: linked filename, lifecycle status, and a
    one-line purpose derived from the doc's H1. Sorted by filename so the output
    is deterministic and diff-stable. Docs without a valid marker are listed with
    ``status=?`` so the index still surfaces them (lint is the gate that forces
    the marker; the index does not hide the gap).
    """
    root = Path(root)
    cfg = config or discover_config(root)
    lines: List[str] = []
    for rel in tracked_docs(root, cfg):
        name = rel.split("/", 1)[1]
        marker = parse_marker(root / rel)
        status = marker.status if (marker and marker.status) else "?"
        purpose = _doc_purpose(root / rel)
        entry = f"- [`{name}`](./{name}) · {status}"
        if purpose:
            entry += f" · {purpose}"
        lines.append(entry)
    return "\n".join(lines)


def render_index_section(root: Path, config: Optional[Config] = None) -> str:
    """Return the full splice block (markers + generated body)."""
    body = generate_index(root, config)
    return f"{INDEX_START}\n{body}\n{INDEX_END}"


def update_readme_index(
    root: Path, config: Optional[Config] = None
) -> tuple[bool, str]:
    """Splice the generated index into ``<docs_dir>/README.md`` in place.

    Replaces the content between :data:`INDEX_START` and :data:`INDEX_END`. When
    the markers are absent, appends a fresh index section under a heading. Returns
    ``(changed, message)``. Idempotent — running twice with no doc changes is a
    no-op.
    """
    root = Path(root)
    cfg = config or discover_config(root)
    readme = root / cfg.docs_dir / "README.md"
    try:
        original = readme.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"could not read {readme}: {exc}"

    section = render_index_section(root, cfg)
    if INDEX_START in original and INDEX_END in original:
        pattern = re.compile(
            re.escape(INDEX_START) + r".*?" + re.escape(INDEX_END),
            re.DOTALL,
        )
        updated = pattern.sub(lambda _m: section, original, count=1)
    else:
        suffix = "" if original.endswith("\n") else "\n"
        updated = (
            f"{original}{suffix}\n## Full index (generated)\n\n"
            f"Regenerate with `episteme docs index`.\n\n{section}\n"
        )

    if updated == original:
        return False, "docs index already up to date"
    readme.write_text(updated, encoding="utf-8")
    return True, f"updated docs index in {cfg.docs_dir}/README.md"


# --------------------------------------------------------------------------- #
# CLI entry points                                                             #
# --------------------------------------------------------------------------- #


def run_lint_cli(root: Optional[Path] = None) -> int:
    """`episteme docs lint` — exit 1 when the corpus has marker violations."""
    root = Path(root) if root is not None else _repo_root()
    findings = lint(root)
    if not findings:
        print("docs lifecycle: clean")
        return 0
    print(f"{len(findings)} doc lifecycle violation(s):")
    print(format_findings(findings))
    return 1


def run_index_cli(root: Optional[Path] = None, check: bool = False) -> int:
    """`episteme docs index` — regenerate (or, with ``check``, verify) the index."""
    root = Path(root) if root is not None else _repo_root()
    cfg = discover_config(root)
    if check:
        readme = root / cfg.docs_dir / "README.md"
        try:
            original = readme.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"docs index: could not read {readme}: {exc}")
            return 1
        section = render_index_section(root, cfg)
        if INDEX_START in original and INDEX_END in original:
            pattern = re.compile(
                re.escape(INDEX_START) + r".*?" + re.escape(INDEX_END),
                re.DOTALL,
            )
            match = pattern.search(original)
            if match is not None and match.group(0) == section:
                print("docs index: up to date")
                return 0
        print("docs index: STALE — run `episteme docs index` and commit")
        return 1
    changed, message = update_readme_index(root, cfg)
    print(f"docs index: {message}")
    return 0


def _repo_root() -> Path:
    """Resolve the repo root (git top-level, else the package's parents[2])."""
    here = Path(__file__).resolve()
    try:
        proc = subprocess.run(
            ["git", "-C", str(here.parent), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        top = proc.stdout.strip()
        if top:
            return Path(top)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return here.parents[2]
