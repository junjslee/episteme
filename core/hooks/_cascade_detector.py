"""Blueprint D · Architectural Cascade detector — v1.0 RC CP10.

Unified four-trigger selector: returns ``"architectural_cascade"``
when a proposed op matches ANY of the four trigger classes. Otherwise
returns ``None`` and `_scenario_detector` falls through to Fence /
generic.

## The four triggers (order = cheapest-first short-circuit)

1. **Self-escalation** — the surface itself declares a
   ``flaw_classification`` field. Always decisive, zero cost. The
   operator / agent is explicitly asking for Blueprint D's
   discipline.

2. **Sensitive-path target** — the op touches a file path in the
   kernel-critical deny-list:

   - ``core/schemas/``
   - ``core/hooks/`` (kernel-adjacent, per CP10 plan Q2)
   - ``kernel/[A-Z_]+\\.md`` (uppercase kernel docs)
   - ``.episteme/``
   - ``pyproject.toml``
   - ``^policy[/_-]``
   - ``^security[/_-]``

   Extracted from Bash command tokens or Edit/Write ``file_path``.

3. **Refactor lexicon + cross-ref threshold** — command-head
   anchored lexicon hit (`git mv`, `git rename`, `rename`,
   `deprecate`, `migrate`, `sed -i`, `cleanup`) PLUS at least one
   path-shaped token whose basename appears ≥ 2 times in the
   project's content blob. The threshold filters out bespoke
   throwaway renames; sustained cross-references are the signal
   spec cares about. Per CP10 plan Q1, threshold = 2 exactly.

4. **Generated-artifact symbol reference** — rename/delete of a
   source file whose basename appears in the strict
   generated-artifact set (``kernel/MANIFEST.sha256``,
   ``kernel/CHANGELOG.md``, ``CHANGELOG.md``). Per CP10 plan Q3,
   scope is strict — expand post-soak only on demand.

## FP discipline

Command-head anchoring on the refactor lexicon (lesson from CP5
dogfood — a loose lexicon FP'd on its own shipping commit message).
Sensitive-path trigger requires the path to actually appear in the
command / target; naming a sensitive path in a commit message does
not trip it. Generated-artifact check requires a source-file basename
hit; random mentions don't fire.

## Graceful degrade

Any exception inside the detector (project fingerprint IO, regex
match failure) logs to stderr and returns None. Fence / generic
scenarios stay reachable. Blueprint D's "admission enforcement" runs
only after the selector fires AND the scenario is Blueprint D.

Spec: ``docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md`` § Blueprint D ·
Architectural Cascade & Escalation.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any


_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


ARCHITECTURAL_CASCADE = "architectural_cascade"


# ---------------------------------------------------------------------------
# Kernel-state-file exemptions (v1.0 RC live-dogfood learning)
# ---------------------------------------------------------------------------
#
# Blueprint D's four triggers fire on kernel / hook / schema edits.
# The kernel's OWN state files (``.episteme/reasoning-surface.json``
# and ``.episteme/advisory-surface``) live under ``.episteme/``, which
# Trigger 2 flags as sensitive. AND the surface itself self-escalates
# via Trigger 1 once it declares ``flaw_classification``. Together
# these created a live circular dependency during CP10's own dogfood
# commit: writing a Blueprint D surface fired cascade on the surface
# write itself, blocking refresh forever.
#
# Fix: when the proposed op TARGETS a kernel state file, the detector
# returns None regardless of other triggers. Operator metadata edits
# are not architectural cascades; they are the kernel's own
# dogfood-gate maintenance path.


_KERNEL_STATE_EXEMPT_SUFFIXES: tuple[str, ...] = (
    ".episteme/reasoning-surface.json",
    ".episteme/advisory-surface",
    ".episteme/strict-surface",  # legacy marker, pre-v0.8.1
)


# ---------------------------------------------------------------------------
# Trigger 1 · sensitive-path target
# ---------------------------------------------------------------------------


_SENSITIVE_PATH_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bcore/schemas/"),
    re.compile(r"\bcore/hooks/"),
    re.compile(r"\bkernel/[A-Z][A-Z_0-9]*\.md\b"),
    re.compile(r"\.episteme/"),
    re.compile(r"\bpyproject\.toml\b"),
    re.compile(r"(?:^|[\s/])policy[/_-]"),
    re.compile(r"(?:^|[\s/])security[/_-]"),
)


def _sensitive_path_hit(text: str) -> bool:
    """True iff the command text / file path matches any sensitive
    deny-list pattern."""
    if not text:
        return False
    return any(p.search(text) for p in _SENSITIVE_PATH_PATTERNS)


# ---------------------------------------------------------------------------
# Trigger 3 · refactor lexicon + cross-ref threshold
# ---------------------------------------------------------------------------


_REFACTOR_LEXICON_RE = re.compile(
    r"^\s*(?:"
    r"git\s+mv|git\s+rename|"
    r"(?:sudo\s+)?rename|"
    r"deprecate|"
    r"(?:alembic\s+)?migrate|"
    r"sed\s+-i|"
    r"cleanup"
    r")\b",
    re.IGNORECASE,
)

_PATH_SHAPED_TOKEN_RE = re.compile(
    r"[\w./\-]+\.(?:py|md|yaml|yml|json|toml|sh|js|ts|jsx|tsx|"
    r"go|rs|java|cpp|hpp|c|h|sql|css|html|ini|cfg|conf|"
    r"lock|txt|rst|xml|proto)",
    re.IGNORECASE,
)

_CROSS_REF_THRESHOLD = 2  # CP10 plan Q1 — exact value, not ">="


def _cross_ref_count(basename: str, cwd: Path) -> int:
    """Count how many times ``basename`` appears in the project's
    bounded content blob. Uses Layer 3's cached fingerprint so
    repeat calls don't re-walk the tree.

    Conservative proxy: byte-occurrence count in the blob. Over-counts
    when a single file mentions the basename multiple times; under-
    counts nothing. Good enough for RC threshold logic; tighten
    post-soak if FPs accumulate."""
    if not basename or "." not in basename:
        return 0
    try:
        from _grounding import (  # type: ignore  # pyright: ignore[reportMissingImports]
            _load_project_fingerprint as _fingerprint,
        )
        _filenames, content = _fingerprint(cwd)
    except Exception:
        return 0
    try:
        needle = basename.encode("utf-8")
    except UnicodeEncodeError:
        return 0
    return content.count(needle)


def _refactor_lexicon_hit(cmd: str, cwd: Path) -> bool:
    """True iff the command matches the refactor lexicon AND at least
    one path-shaped token's basename has cross-ref count ≥ threshold."""
    if not cmd or not _REFACTOR_LEXICON_RE.search(cmd):
        return False
    for match in _PATH_SHAPED_TOKEN_RE.finditer(cmd):
        token = match.group(0)
        basename = Path(token).name
        if _cross_ref_count(basename, cwd) >= _CROSS_REF_THRESHOLD:
            return True
    return False


# ---------------------------------------------------------------------------
# Trigger 4 · generated-artifact symbol reference
# ---------------------------------------------------------------------------


_GENERATED_ARTIFACTS: tuple[str, ...] = (
    "kernel/MANIFEST.sha256",
    "kernel/CHANGELOG.md",
    "CHANGELOG.md",
)

_RENAME_OR_DELETE_HEAD_RE = re.compile(
    r"^\s*(?:git\s+mv|git\s+rm|rm\s+-rf?|unlink|rename)\b",
    re.IGNORECASE,
)


_GENERATED_ARTIFACT_MIN_STEM = 5


def _generated_artifact_reference_hit(cmd: str, cwd: Path) -> bool:
    """True iff the command is a rename/delete targeting a Python
    source file whose basename stem appears in any generated-artifact
    file.

    PreToolUse proxy. Tightened post-CP10-dogfood:
    - Only Python source files (``.py``) are checked. Spec intent is
      "exported symbol name appears in MANIFEST"; non-Python files
      don't export symbols in the kernel sense.
    - Stem must be ≥ 5 chars to avoid short substrings
      (``ci`` / ``cp`` / ``md``) false-matching against generated
      artifact prose that happens to contain those letters.
    - Needle wraps with word-boundary checks: the stem must appear
      as a whole word, not as part of a longer identifier.
    """
    if not cmd or not _RENAME_OR_DELETE_HEAD_RE.search(cmd):
        return False
    tokens = [
        m.group(0) for m in _PATH_SHAPED_TOKEN_RE.finditer(cmd)
        if m.group(0).endswith(".py")
    ]
    if not tokens:
        return False
    for artifact_rel in _GENERATED_ARTIFACTS:
        artifact_path = cwd / artifact_rel
        if not artifact_path.is_file():
            continue
        try:
            artifact_text = artifact_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for token in tokens:
            basename = Path(token).name
            stem = basename.rsplit(".", 1)[0]
            if len(stem) < _GENERATED_ARTIFACT_MIN_STEM:
                continue
            # Word-boundary search — `_grounding` matches in prose
            # like "core/hooks/_grounding.py" or "_grounding module"
            # but not inside a longer identifier.
            pattern = re.compile(
                r"\b" + re.escape(stem) + r"\b"
            )
            if pattern.search(artifact_text):
                return True
    return False


# ---------------------------------------------------------------------------
# Payload helpers (BYOS — same shape the guard produces)
# ---------------------------------------------------------------------------


def _tool_name(payload: dict) -> str:
    return str(
        payload.get("tool_name") or payload.get("toolName") or ""
    ).strip()


def _bash_command(payload: dict) -> str:
    ti = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(ti, dict):
        return ""
    return str(
        ti.get("command")
        or ti.get("cmd")
        or ti.get("bash_command")
        or ""
    )


def _edit_write_target(payload: dict) -> str:
    ti = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(ti, dict):
        return ""
    return str(
        ti.get("file_path")
        or ti.get("path")
        or ti.get("target_file")
        or ""
    )


def _op_cwd(payload: dict) -> Path:
    import os
    return Path(payload.get("cwd") or os.getcwd())


# ---------------------------------------------------------------------------
# Unified detector
# ---------------------------------------------------------------------------


def _op_targets_kernel_state(pending_op: dict[str, Any]) -> bool:
    """True iff the op's target is a kernel state file. Checked
    before any trigger fires — metadata edits to .episteme/ state
    are not architectural cascades."""
    tool = _tool_name(pending_op)
    if tool in {"Edit", "Write", "MultiEdit"}:
        target = _edit_write_target(pending_op)
        return any(
            target.endswith(suf) for suf in _KERNEL_STATE_EXEMPT_SUFFIXES
        )
    if tool == "Bash":
        cmd = _bash_command(pending_op)
        if not cmd:
            return False
        # Catch path-shaped tokens first.
        for match in _PATH_SHAPED_TOKEN_RE.finditer(cmd):
            tok = match.group(0)
            if any(
                tok.endswith(suf) for suf in _KERNEL_STATE_EXEMPT_SUFFIXES
            ):
                return True
        # Also catch extension-less .episteme/advisory-surface paths
        # that the path-shaped regex misses.
        for suf in _KERNEL_STATE_EXEMPT_SUFFIXES:
            if suf in cmd:
                return True
    return False


def detect_cascade(
    pending_op: dict[str, Any],
    surface: dict[str, Any] | None = None,
) -> str | None:
    """Return ``"architectural_cascade"`` when any trigger fires,
    else None. Short-circuits on first match. Graceful degrade —
    any exception returns None rather than masking Fence / generic.
    """
    try:
        # Kernel-state-file exemption — ALWAYS wins. Edits to the
        # kernel's own metadata files (reasoning-surface.json,
        # advisory-surface) bypass cascade detection. CP10 lesson:
        # self-escalation on `flaw_classification` would otherwise
        # block subsequent surface refreshes recursively.
        if _op_targets_kernel_state(pending_op):
            return None

        # Trigger 1 — self-escalation (cheapest). Fires regardless of
        # tool type when the surface declares flaw_classification.
        if isinstance(surface, dict):
            flaw = surface.get("flaw_classification")
            if isinstance(flaw, str) and flaw.strip():
                return ARCHITECTURAL_CASCADE

        tool = _tool_name(pending_op)

        if tool == "Bash":
            cmd = _bash_command(pending_op)
            if not cmd:
                return None
            # Trigger 2 — sensitive path in command.
            if _sensitive_path_hit(cmd):
                return ARCHITECTURAL_CASCADE
            cwd = _op_cwd(pending_op)
            # Trigger 3 — refactor lexicon + cross-ref threshold.
            if _refactor_lexicon_hit(cmd, cwd):
                return ARCHITECTURAL_CASCADE
            # Trigger 4 — generated-artifact symbol reference.
            if _generated_artifact_reference_hit(cmd, cwd):
                return ARCHITECTURAL_CASCADE
            return None

        if tool in {"Edit", "Write", "MultiEdit"}:
            target = _edit_write_target(pending_op)
            if not target:
                return None
            # Trigger 2 — sensitive path as target.
            if _sensitive_path_hit(target):
                return ARCHITECTURAL_CASCADE
            return None

        return None
    except Exception as exc:  # graceful degrade
        sys.stderr.write(
            f"[episteme] Blueprint D cascade detector fallback: "
            f"{exc.__class__.__name__}; Fence / generic scenarios "
            f"still reachable.\n"
        )
        return None
