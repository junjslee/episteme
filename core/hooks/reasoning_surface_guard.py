#!/usr/bin/env python3
"""PreToolUse guard: high-impact ops require a valid Reasoning Surface.

Enforces the kernel rule `irreversible or high-blast-radius -> declare a
Reasoning Surface first` (kernel/CONSTITUTION.md, kernel/REASONING_SURFACE.md).

Behavior:
- Matches a high-impact pattern in Bash commands (git push, publish,
  migrations, cloud deletes, DB destructive SQL) or Write|Edit to irreversible
  files (lock files, secrets). Command text is normalized (quotes, commas,
  brackets, parens, backticks mapped to whitespace) before matching so bypass
  shapes like `python -c "subprocess.run(['git','push'])"`,
  `os.system('git push')`, or `` `git push` `` trip the same patterns as bare
  shell.
- **Indirection heuristics** (best-effort, avoid FPs):
    * `eval $VAR` / `eval "$VAR"` — blocked as variable-indirection.
    * Direct shell-script execution (`./x.sh`, `bash x.sh`, `sh x.sh`,
      `source x.sh`, `. x.sh`) is opened and scanned for high-impact patterns
      (capped at 64 KB; silently passed through if unreadable).
- Reads `.episteme/reasoning-surface.json` in the project cwd.
- A Surface is valid when: timestamp within SURFACE_TTL_SECONDS, non-empty
  core_question, at least one substantive unknown, and a disconfirmation
  field that meets minimum length and is not a lazy placeholder
  (none, n/a, tbd, 해당 없음, 없음, ...).
- **Default mode: STRICT (blocking).** Missing, stale, incomplete, or lazy
  surfaces exit 2 and block the op. Opt out per-project by creating
  `.episteme/advisory-surface`; the hook then emits advisory context only.
- Legacy marker `.episteme/strict-surface` is now a no-op (strict is default).
- **Calibration telemetry (Gap A):** on allowed Bash executions, writes a
  prediction record to `~/.episteme/telemetry/YYYY-MM-DD-audit.jsonl` with
  correlation_id, timestamp, command_executed, epistemic_prediction. A
  companion PostToolUse hook (`calibration_telemetry.py`) writes the matching
  outcome record carrying exit_code. Records are local-only, never committed.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# v1.0 RC CP3 — Layer 2 in the hot path, blueprint-aware.
# Import sibling hook modules (_specificity, _blueprint_registry,
# _scenario_detector) via sys.path injection so the guard works
# identically whether invoked as a standalone script by the host runtime
# (its own dir is on sys.path by default) or imported under pytest
# (which sets sys.path from pyproject's pythonpath = ["src", "."]
# extension at commit 2a2ed68). Same pattern CP1 used for
# _profile_audit.py's _specificity import.
_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

# Event 135 — Stage 2 Tier-1 dispatch path needs to import from
# core.hooks._irreversible_tier (moved there in Event 136 Stage 4b). The
# hook runs as a standalone script in production; add the repo root to
# sys.path so the package import resolves the same under runtime and pytest.
_REPO_ROOT = _HOOKS_DIR.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from _blueprint_registry import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    BlueprintParseError as _BlueprintParseError,
    BlueprintValidationError as _BlueprintValidationError,
    load_registry as _load_registry,
)
from _scenario_detector import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    detect_scenario as _detect_scenario,
)
from _specificity import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    _classify_origin_evidence as _classify_origin,
    classify_disconfirmation_parts as _classify_parts_for_layer2,
)
from _grounding import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    ground_blueprint_fields as _layer3_ground_blueprint_fields,
)
from _verification_trace import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    VerificationTrace as _VerificationTrace,
    validate_trace as _validate_trace,
    smoke_test_rollback_path as _smoke_test_rollback,
)
from _context_signature import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    build as _build_context_signature,
)
from _pending_contracts import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    write_contract as _write_pending_contract,
)
from _guidance import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    query as _guidance_query,
    format_advisory as _guidance_format_advisory,
)
from _blueprint_d import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    FLAW_CLASSES as _TEMPLATE_FLAW_CLASSES,
    POSTURE_VALUES as _TEMPLATE_POSTURE_VALUES,
    validate_blueprint_d as _validate_blueprint_d,
    write_cascade_deferred_discoveries as _write_cascade_deferred_discoveries,
)
import _fence_synthesis  # noqa: E402  # pyright: ignore[reportMissingImports]


SURFACE_TTL_SECONDS = 30 * 60  # 30 minutes


# Per-blueprint declaration of which required_fields the Layer-2
# specificity classifier actually runs against. Some fields are
# statements-of-fact (Knowns) or provisional-beliefs (Assumptions) —
# classifying them as "trigger+observable" would be a category error.
# CP3 seeds the generic fallback (classifier runs on `disconfirmation`
# and per-entry on `unknowns`). CP5 / CP10 add named-blueprint entries
# as Fence Reconstruction / Architectural Cascade land.
_CLASSIFIED_FIELDS_BY_BLUEPRINT: dict[str, tuple[str, ...]] = {
    "generic": ("disconfirmation", "unknowns"),
    # CP5: Fence adds `removal_consequence_prediction` — a fire-shape
    # field (trigger + observable) describing what breaks if the
    # constraint is removed. `origin_evidence` has a different
    # specificity rule (evidence markers, not trigger+observable) and
    # is validated separately by `_layer_fence_validate` below.
    "fence_reconstruction": (
        "disconfirmation",
        "unknowns",
        "removal_consequence_prediction",
    ),
}

# Minimum character thresholds — lazy one-word answers are rejected.
# These are now derived from the operator profile's uncertainty_tolerance +
# testing_rigor via ~/.episteme/derived_knobs.json (written by the adapter
# at `episteme sync` time; see `core/hooks/_derived_knobs.py` and
# `kernel/OPERATOR_PROFILE_SCHEMA.md` section 5). Fallback is the historic
# default (15) when no profile-derived knobs have been computed yet.
# Inlined rather than imported so this hook stays self-contained — the hook
# is invoked as a standalone script by the host runtime with no guaranteed
# sys.path setup.
_MIN_LEN_DEFAULT = 15
def _derived_knobs_path() -> Path:
    """Resolved per call, honoring EPISTEME_HOME (Event 171 — the
    module-load constant ignored the sandbox env var; same bug class
    as _derived_knobs._KNOBS_PATH, fixed in the same event)."""
    return Path(
        os.environ.get("EPISTEME_HOME") or (Path.home() / ".episteme")
    ) / "derived_knobs.json"


def _load_derived_knob(name: str, default):
    try:
        if not _derived_knobs_path().is_file():
            return default
        with open(_derived_knobs_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or name not in data:
            return default
        value = data[name]
        if default is not None and not isinstance(value, type(default)):
            return default
        return value
    except (OSError, json.JSONDecodeError):
        return default


def _min_disconfirmation_len() -> int:
    return int(_load_derived_knob("disconfirmation_specificity_min", _MIN_LEN_DEFAULT))


def _min_unknown_len() -> int:
    return int(_load_derived_knob("unknown_specificity_min", _MIN_LEN_DEFAULT))

# Lazy-token blocklist: strings that defeat the Reasoning Surface contract
# by providing fluent-looking placeholders instead of measurable conditions.
# Matched case-insensitively against whitespace-collapsed content.
LAZY_TOKENS = frozenset({
    "none", "null", "nil", "nothing", "undefined",
    "n/a", "na", "n.a.", "n.a", "not applicable",
    "tbd", "todo", "to be determined", "to be decided",
    "unknown", "idk", "i don't know", "no idea",
    "해당 없음", "해당없음", "없음", "모름", "모르겠음",
    "해당 사항 없음", "해당사항없음",
    "-", "--", "---", "—", "...", "...",
    "pending", "later", "maybe", "?",
})

HIGH_IMPACT_BASH = [
    (re.compile(r"\bgit\s+push\b"), "git push"),
    (re.compile(r"\bgit\s+merge\b(?!\s+--abort)"), "git merge"),
    # Event 146 — `git reset --hard` discards the working tree + index
    # irreversibly. block_dangerous.py already halts it as a raw string;
    # add it to the positive enumeration so the surface gate also demands
    # a Reasoning Surface for it (conscious positive-system addition, not
    # a match-surface broadening).
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "git reset --hard"),
    (re.compile(r"\bnpm\s+publish\b"), "npm publish"),
    (re.compile(r"\byarn\s+publish\b"), "yarn publish"),
    (re.compile(r"\bpnpm\s+publish\b"), "pnpm publish"),
    (re.compile(r"\bpoetry\s+publish\b"), "poetry publish"),
    (re.compile(r"\bcargo\s+publish\b"), "cargo publish"),
    (re.compile(r"\btwine\s+upload\b"), "twine upload"),
    (re.compile(r"\bpip\s+install\b(?!.*--dry-run)"), "pip install"),
    (re.compile(r"\bpip\s+uninstall\b"), "pip uninstall"),
    (re.compile(r"\balembic\s+upgrade\b"), "alembic upgrade"),
    (re.compile(r"\bprisma\s+migrate\s+deploy\b"), "prisma migrate deploy"),
    (re.compile(r"\bterraform\s+apply\b"), "terraform apply"),
    (re.compile(r"\bterraform\s+destroy\b"), "terraform destroy"),
    (re.compile(r"\bkubectl\s+(?:delete|apply)\b"), "kubectl delete/apply"),
    (re.compile(r"\baws\s+s3\s+rm\b"), "aws s3 rm"),
    (re.compile(r"\bgcloud\b.*\bdelete\b"), "gcloud delete"),
    (re.compile(r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b", re.I), "SQL DROP"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.I), "SQL TRUNCATE"),
    (re.compile(r"\bgh\s+pr\s+merge\b"), "gh pr merge"),
    (re.compile(r"\bgh\s+release\s+create\b"), "gh release create"),
]

IRREVERSIBLE_WRITE_PATHS = (
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
)

# Characters that separate tokens in quoted / bracketed / parenthesized /
# backtick invocations. Normalize these to a space so regex-word-boundary
# patterns catch `subprocess.run(['git','push'])`, `os.system("git push")`,
# and `` `git push` `` the same way they catch bare `git push`.
_NORMALIZE_SEPARATORS = re.compile(r"[,'\"\[\]\(\)\{\}`]")

# Indirection patterns — blocked even when the direct op name isn't literally
# present. These intentionally target constructs whose legitimate uses are
# rare enough that per-project advisory opt-out is an acceptable escape.
INDIRECTION_BASH = [
    (re.compile(r"\beval\s+[\"']?\$"), "eval with variable indirection"),
]

# Shell-script execution interceptors. Matched AFTER direct/indirection
# patterns miss; if any matches, the referenced script is opened and scanned
# for high-impact patterns. Only `.sh` files are considered (avoids scanning
# binaries / arbitrary executables).
_SCRIPT_EXEC_PATTERNS = [
    # `bash X.sh`, `sh X.sh`, `zsh X.sh`, `ksh X.sh`
    re.compile(r"\b(?:bash|sh|zsh|ksh)\s+([^\s;&|]+\.sh)\b"),
    # `source X.sh`, `. X.sh`
    re.compile(r"(?:\bsource\s+|(?:^|[;&|]\s*)\.\s+)([^\s;&|]+\.sh)\b"),
    # `./X.sh`, `/abs/path/X.sh`
    re.compile(r"(?:^|\s)((?:\.\/|\/)[^\s;&|]+\.sh)\b"),
]

# Cap script reads to keep the hook fast and bounded.
MAX_SCRIPT_SCAN_BYTES = 64 * 1024

# Variable-indirection execution shapes used with agent-written files. When
# these appear alongside a recent agent-write in the state store, we block
# even without a literal file reference — the agent has taken the file-name
# out of the command text to defeat pattern matching.
_INDIRECT_EXEC_PATTERNS = [
    re.compile(r"\b(?:bash|sh|zsh|ksh)\s+\$"),
    re.compile(r"\bpython\d?\s+\$"),
    re.compile(r"\bnode\s+\$"),
    re.compile(r"(?:^|\s)(?:\./|source\s+|\.\s+)\$"),
]


def _normalize_command(cmd: str) -> str:
    """Map shell / language token separators to spaces for robust matching."""
    return _NORMALIZE_SEPARATORS.sub(" ", cmd)


def _tool_name(payload: dict) -> str:
    return str(payload.get("tool_name") or payload.get("toolName") or "").strip()


def _tool_input(payload: dict) -> dict:
    raw = payload.get("tool_input") or payload.get("toolInput") or {}
    return raw if isinstance(raw, dict) else {}


def _bash_command(payload: dict) -> str:
    ti = _tool_input(payload)
    return str(ti.get("command") or ti.get("cmd") or ti.get("bash_command") or "")


def _write_target(payload: dict) -> str:
    ti = _tool_input(payload)
    return str(ti.get("file_path") or ti.get("path") or ti.get("target_file") or "")


def _match_against_patterns(text: str) -> str | None:
    """Return the first high-impact / indirection label that matches `text`."""
    for pattern, label in HIGH_IMPACT_BASH:
        if pattern.search(text):
            return label
    for pattern, label in INDIRECTION_BASH:
        if pattern.search(text):
            return label
    return None


# ---------------------------------------------------------------------------
# Event 146 — argv-position classification.
#
# Failure mode countered: the pre-146 path ran the high-impact patterns over
# the WHOLE command text (`_match_against_patterns(_normalize_command(cmd))`),
# so a heredoc BODY, a quoted string literal argument (`echo "git push ..."`),
# a grep pattern (`grep "git push" ...`), or a commit-message body all
# classified as high-impact and each firing injected the full ~2.3 KB surface
# template. This narrows the MATCH SURFACE from all-text to what the shell
# would actually EXECUTE — argv command-position tokens per segment, plus the
# command-string ARGUMENT of wrapper/indirect executors, plus command-
# substitution bodies — while leaving data-position text inert.
#
# Fail-closed direction (ratified repo lesson, Events 142-143): the failure
# direction is TOWARD classifying. A shlex parse failure or any unhandled
# shape falls back to the pre-146 whole-text scan, and wrappers retain the
# old whole-argument sensitivity. Only data-position text stops triggering.
# Tokenization uses shlex (stdlib); no hand-rolled character-level quoting
# logic beyond shlex + operator splitting + heredoc/substitution extraction.
# ---------------------------------------------------------------------------

# Heredoc terminator word shape — used by `_heredoc_terminator` to validate
# the token following a genuine `<<` / `<<-` operator. A regex over the raw
# line is NOT used to DETECT the intro (FINDING 2): `<<`-lookalikes inside a
# quoted string literal (`git commit -m "add a<<b shift"`) must not register
# as a heredoc. Detection goes through shlex so a `<<` embedded in a quoted
# token stays inside that token and is never mistaken for an operator.
_HEREDOC_TERMINATOR_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Command-substitution spans — their contents ARE executed, so they are
# extracted and scanned recursively rather than treated as data.
_BACKTICK_SUBST = re.compile(r"`([^`]*)`")
_DOLLAR_PAREN_SUBST = re.compile(r"\$\(([^()]*)\)")

# Wrapper executors that run their command-string argument: `bash -c STR`,
# `sh -c STR`, `python -c STR`, etc. The `-c` argument is scanned with the
# retained pre-146 whole-text sensitivity (`_match_against_patterns` over a
# normalized string) so a real high-impact op inside it never goes invisible.
_WRAPPER_DASH_C = frozenset({
    "bash", "sh", "zsh", "ksh", "dash",
    "python", "python2", "python3",
})

# Redirect tokens are dropped before command-position reconstruction.
_REDIRECT_TOKENS = frozenset({"<", ">", ">>", "<<", "<<<", "&>", ">&", "2>", "2>>"})

# Bound recursion into command substitutions.
_MAX_SUBST_DEPTH = 3


def _strip_quotes(tok: str) -> str:
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in ("'", '"'):
        return tok[1:-1]
    return tok


def _is_quoted(tok: str) -> bool:
    return len(tok) >= 2 and tok[0] in ("'", '"') and tok[-1] == tok[0]


# FINDING 1 backstop — bare (unquoted) executor tokens that run a
# command-STRING argument somewhere in the segment: `bash -c ...`,
# `python -c ...`, `eval ...`, or a trailing-command builder (`xargs`).
# The set of *prefix* wrappers that can precede one of these
# (timeout / env / nohup / nice / stdbuf / command / ionice / xvfb-run / ...)
# is OPEN-ENDED, so we do NOT enumerate prefixes. Instead we detect the
# executor token wherever it lands and fall the whole segment back to the
# pre-146 whole-text sensitivity (see `_scan_segment`). `python*` (python2 /
# python3 / python3.11) is matched by prefix, not enumerated here.
_EXECUTOR_BASES = frozenset({
    "bash", "sh", "zsh", "ksh", "dash", "eval", "xargs",
})


def _is_executor_token(tok: str) -> bool:
    """True when `tok` is a BARE (unquoted) command-string executor.

    A quoted token is data, never an executor — `echo "bash -c git push"`
    must stay inert. A path-qualified executor (`/usr/bin/bash`) matches on
    its basename.
    """
    if _is_quoted(tok):
        return False
    base = tok.rsplit("/", 1)[-1]
    if base in _EXECUTOR_BASES:
        return True
    if base.startswith("python"):
        rest = base[len("python"):]
        return rest == "" or rest.replace(".", "").isdigit()
    return False


def _neutralize_token(tok: str) -> str:
    """Command-position reconstruction rule for one non-posix shlex token.

    A quoted token whose content carries internal whitespace is a multi-word
    string literal in data position (the shape of every Event-146 false
    positive: `"git push origin master"`, a grep pattern, a commit body) —
    neutralize it so its internal words cannot form a high-impact adjacency.
    A single-word quoted token (e.g. a quoted subcommand `git 'push'`) keeps
    its value, biasing toward classifying (fail-closed). Unquoted tokens pass
    through unchanged.
    """
    if _is_quoted(tok):
        content = _strip_quotes(tok)
        if not content or any(ch.isspace() for ch in content):
            return " "
        return content
    return tok


def _heredoc_terminator(line: str) -> str | None:
    """Return the terminator WORD if `line` opens a GENUINE heredoc, else None.

    FINDING 2b — detection goes through shlex, not a raw-line regex. A genuine
    `<<` / `<<-` operator tokenizes as its own operator token under non-posix
    shlex; a `<<` that lives inside a quoted string literal
    (`git commit -m "add a<<b shift"`, `echo "compare x << y"`) stays embedded
    in its quoted token and never surfaces as an operator — so it is not
    mistaken for an intro. A here-string (`<<<`) tokenizes as a distinct `<<<`
    token and is likewise ignored. Any tokenization failure (unbalanced quote)
    returns None: the fail-closed direction here is NOT to strip.
    """
    if "<<" not in line:
        return None
    try:
        tokens = _tokenize_nonposix(line)
    except ValueError:
        return None
    for idx, tok in enumerate(tokens):
        if tok in ("<<", "<<-"):
            if idx + 1 >= len(tokens):
                return None
            word = tokens[idx + 1]
            # `<<-EOF` tokenizes as `<<` + `-EOF`; drop the strip-tabs dash.
            if word.startswith("-"):
                word = word[1:]
            word = _strip_quotes(word)
            if _HEREDOC_TERMINATOR_WORD.fullmatch(word):
                return word
            return None
    return None


def _strip_heredoc_bodies(cmd: str) -> str:
    """Drop heredoc BODY lines (data), keeping the intro and terminator lines.

    Without this, the body's bare words tokenize as ordinary command-position
    tokens and a body line like `git push origin main` classifies as an op.

    FINDING 2a — when the terminator line is never found, NOTHING is stripped:
    an unterminated heredoc is either malformed input or a false intro match,
    and dropping every remaining line hid trailing REAL commands
    (`git commit -m "a<<b"` + newline + `git push origin main`). Not-stripping
    is the fail-closed direction — the raw text then reaches the tokenizer,
    whose quoted-token handling neutralizes data while keeping later commands
    visible.
    """
    if "<<" not in cmd:
        return cmd
    lines = cmd.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        terminator = _heredoc_terminator(line)
        if terminator is None:
            out.append(line)
            i += 1
            continue
        j = i + 1
        while j < len(lines) and lines[j].strip() != terminator:
            j += 1
        if j < len(lines):
            # Terminator found — strip the body [i+1, j); keep intro + term.
            out.append(line)
            out.append(lines[j])
            i = j + 1
        else:
            # Terminator absent — keep ALL remaining lines untouched.
            out.extend(lines[i:])
            break
    return "\n".join(out)


def _extract_substitutions(cmd: str) -> tuple[str, list[str]]:
    """Replace `` `...` `` / `$(...)` spans with a space and return their bodies.

    Command-substitution bodies execute, so they are scanned recursively.
    Extraction is quote-agnostic (a substitution inside single quotes does not
    execute in a real shell) — extracting it anyway over-classifies, which is
    the fail-closed direction.
    """
    subs: list[str] = []

    def _grab(m: "re.Match[str]") -> str:
        subs.append(m.group(1))
        return " "

    cmd = _BACKTICK_SUBST.sub(_grab, cmd)
    for _ in range(_MAX_SUBST_DEPTH):
        new = _DOLLAR_PAREN_SUBST.sub(_grab, cmd)
        if new == cmd:
            break
        cmd = new
    return cmd, subs


def _tokenize_nonposix(text: str) -> list[str]:
    """Tokenize with quotes RETAINED so data tokens stay distinguishable.

    Non-posix shlex returns `"git push"` as a single quoted token while a bare
    `git push` returns two tokens — this is exactly the data-vs-command signal
    `_neutralize_token` consumes. `punctuation_chars` groups shell operators
    (`&&`, `||`, `|`, `;`) into their own tokens for segment splitting.
    Raises ValueError on unbalanced quotes (caller falls back, fail-closed).
    """
    lex = shlex.shlex(text, posix=False, punctuation_chars=";&|()<>")
    lex.whitespace_split = True
    return list(lex)


def _is_operator_token(tok: str) -> bool:
    return bool(tok) and all(ch in ";&|" for ch in tok)


def _split_segments(tokens: list[str]) -> list[list[str]]:
    """Partition a token stream at shell command separators (&&, ||, |, ;, &)."""
    segments: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if _is_operator_token(tok):
            if current:
                segments.append(current)
                current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    return segments


def _wrapper_command_string(base: str, tokens: list[str]) -> str | None:
    """Return the command-string argument a wrapper executor will run, or None.

    `bash -c STR` / `python -c STR` → STR; `xargs CMD ...` → the trailing
    command line. `source` / `.` run a FILE, handled by
    `_match_script_execution`, so they return None here.
    """
    if base in _WRAPPER_DASH_C:
        for i in range(1, len(tokens)):
            if _strip_quotes(tokens[i]) == "-c" and i + 1 < len(tokens):
                return _strip_quotes(tokens[i + 1])
        return None
    if base == "xargs":
        rest = [_strip_quotes(t) for t in tokens[1:]]
        return " ".join(rest) if rest else None
    return None


def _scan_eval_segment(tokens: list[str]) -> str | None:
    """Handle `eval` specially — it executes its argument.

    `eval $X` / `eval "$X"` is variable indirection (blocked, matching the
    pre-146 INDIRECTION_BASH heuristic whether or not the `$` is quoted).
    A literal `eval "git push"` is scanned with the retained old sensitivity;
    `eval "echo hi"` stays inert.
    """
    if len(tokens) < 2:
        return None
    inner = _strip_quotes(tokens[1])
    if inner.startswith("$"):
        return "eval with variable indirection"
    joined = " ".join(_strip_quotes(t) for t in tokens[1:])
    return _match_against_patterns(_normalize_command(joined))


def _scan_segment(tokens: list[str]) -> str | None:
    tokens = [t for t in tokens if t not in _REDIRECT_TOKENS]
    if not tokens:
        return None
    base = _strip_quotes(tokens[0]).rsplit("/", 1)[-1]
    if base == "eval":
        return _scan_eval_segment(tokens)
    inner = _wrapper_command_string(base, tokens)
    if inner is not None:
        label = _match_against_patterns(_normalize_command(inner))
        if label:
            return label
    # FINDING 1 backstop — an open-ended set of exec prefixes
    # (timeout / env / nohup / nice / stdbuf / command / ionice / xvfb-run / ...)
    # can carry a `bash -c "<op>"` deeper in the segment than the base-token
    # wrapper fast path above ever inspects, and the neutralizing
    # reconstruction below would erase the quoted payload as data. If ANY bare
    # token is a command-string executor, scan the WHOLE segment (quoted
    # contents included) with the pre-146 whole-text sensitivity so a real op
    # cannot go invisible. A bare `bash` in data position
    # (`echo bash -c "git push"`) over-classifies here — the accepted,
    # fail-closed direction.
    if any(_is_executor_token(t) for t in tokens):
        seg_text = " ".join(_strip_quotes(t) for t in tokens)
        label = _match_against_patterns(_normalize_command(seg_text))
        if label:
            return label
    reconstructed = " ".join(_neutralize_token(t) for t in tokens)
    return _match_against_patterns(reconstructed)


def _match_executed_command(cmd: str, _depth: int = 0) -> str | None:
    """Classify against what the shell would EXECUTE, not the raw command text.

    Returns a high-impact / indirection label or None. On any shlex parse
    failure, falls back to the pre-146 whole-text scan (fail closed).
    """
    if not cmd or not cmd.strip():
        return None
    body, subs = _extract_substitutions(_strip_heredoc_bodies(cmd))
    try:
        tokens = _tokenize_nonposix(body)
    except ValueError:
        # Malformed command (e.g. unbalanced quote): fail closed to the
        # pre-146 whole-text scan so a real op is never lost to a parse error.
        return _match_against_patterns(_normalize_command(cmd))
    for segment in _split_segments(tokens):
        label = _scan_segment(segment)
        if label:
            return label
    if _depth < _MAX_SUBST_DEPTH:
        for sub in subs:
            label = _match_executed_command(sub, _depth + 1)
            if label:
                return label
    return None


def _resolve_script_path(cwd: Path, raw: str) -> Path | None:
    """Best-effort resolution of a script reference against `cwd`.

    Returns None if the path escapes bounds, doesn't exist, or is not a file.
    """
    raw = raw.strip()
    if not raw:
        return None
    try:
        candidate = Path(raw) if Path(raw).is_absolute() else (cwd / raw)
        candidate = candidate.resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    if not candidate.exists() or not candidate.is_file():
        return None
    return candidate


def _match_script_execution(cwd: Path, cmd: str) -> str | None:
    """If `cmd` runs a .sh script, scan that script's content for high-impact ops.

    Best-effort: missing / unreadable / oversized scripts pass through without
    blocking. This keeps legitimate automation unaffected when script content
    is absent or produced on-the-fly.
    """
    for pattern in _SCRIPT_EXEC_PATTERNS:
        for match in pattern.finditer(cmd):
            script_ref = match.group(1)
            resolved = _resolve_script_path(cwd, script_ref)
            if resolved is None:
                continue
            try:
                with open(resolved, "rb") as f:
                    raw_bytes = f.read(MAX_SCRIPT_SCAN_BYTES + 1)
            except OSError:
                continue
            if len(raw_bytes) > MAX_SCRIPT_SCAN_BYTES:
                # Truncate at cap; still scan what we have.
                raw_bytes = raw_bytes[:MAX_SCRIPT_SCAN_BYTES]
            try:
                content = raw_bytes.decode("utf-8", errors="replace")
            except Exception:
                continue
            inner_label = _match_against_patterns(_normalize_command(content))
            if inner_label:
                return f"{inner_label} via {script_ref}"
    return None


def _episteme_home() -> Path:
    """Resolve the episteme state root, honoring ``EPISTEME_HOME``.

    FINDING 4 — mirrors the resolver the fence / cascade / pending-contract
    modules use for their pending dirs so a relocated ``EPISTEME_HOME`` keeps
    ALL guard state under one root. Falls back to ``~/.episteme`` when unset —
    which is why tests that patch ``Path.home`` still isolate state.
    """
    return Path(os.environ.get("EPISTEME_HOME") or (Path.home() / ".episteme"))


def _state_store_path() -> Path:
    return Path.home() / ".episteme" / "state" / "session_context.json"


def _safe_session_id(raw: str) -> str:
    """Sanitize a session id for use as a filename component (cf. context_guard)."""
    cleaned = "".join(
        ch for ch in (raw or "") if ch.isalnum() or ch in {"-", "_", "."}
    )
    return cleaned[:128]


def _advisory_shown_marker(session_id: str) -> Path:
    """Per-session marker recording that the full surface schema was shown.

    Follows the `~/.episteme/state/<kind>/<id>` convention used by the
    fence / cascade pending markers; isolated in tests via `Path.home`.
    """
    return (
        _episteme_home() / "state" / "advisory_shown"
        / f"{_safe_session_id(session_id)}.marker"
    )


def _should_show_full_surface(payload: dict) -> bool:
    """Event 146 — session-scoped dedup of the ~2.3 KB remediation schema.

    The first firing in a session shows the full two-artifact schema and
    records a marker; subsequent firings in the same session collapse to a
    1-2 line pointer. When the runtime supplies no ``session_id`` — or the
    marker cannot be persisted — the full schema is shown (fail toward
    informing). Session id is present on both PreToolUse and PostToolUse
    payloads (Event 145 B1).
    """
    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        return True
    marker = _advisory_shown_marker(session_id)
    try:
        if marker.exists():
            return False
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(
            datetime.now(timezone.utc).isoformat(), encoding="utf-8"
        )
    except OSError:
        return True
    return True


def _surface_pointer(label: str, status: str) -> str:
    """Compact (<200 byte) pointer emitted on repeat firings within a session."""
    return (
        f"`{label}` needs a valid Reasoning Surface ({status}); full schema "
        f"shown earlier this session — re-author .episteme/reasoning-surface.json."
    )


def _load_session_state() -> dict:
    """Load the session state store. Returns empty entries on any error."""
    try:
        with open(_state_store_path(), "r", encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict) and isinstance(obj.get("entries"), dict):
            return obj
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": 1, "entries": {}}


def _scan_agent_written_file(path: Path) -> str | None:
    """Open an agent-written file and scan its content for high-impact patterns."""
    try:
        with open(path, "rb") as f:
            raw = f.read(MAX_SCRIPT_SCAN_BYTES + 1)
    except OSError:
        return None
    if len(raw) > MAX_SCRIPT_SCAN_BYTES:
        raw = raw[:MAX_SCRIPT_SCAN_BYTES]
    try:
        content = raw.decode("utf-8", errors="replace")
    except Exception:
        return None
    return _match_against_patterns(_normalize_command(content))


def _match_agent_written_files(cmd: str) -> str | None:
    """Deep-scan recently agent-written files the command references.

    Consults the session state store (populated by `state_tracker.py` on
    PostToolUse Write/Edit/MultiEdit/Bash). Two match modes:

      1. The command text literally mentions the stored absolute path or
         the file's basename — scan that file's current content.
      2. The command uses a variable-indirection execution shape
         (`bash $X`, `python $X`, etc.) and the state store has ANY
         recently-written tracked file — scan each one. This closes
         `F=run.sh; bash $F` bypass style.
    """
    state = _load_session_state()
    entries = state.get("entries", {})
    if not entries:
        return None

    uses_indirection = any(p.search(cmd) for p in _INDIRECT_EXEC_PATTERNS)

    for abs_path in entries.keys():
        try:
            p = Path(abs_path)
        except (TypeError, ValueError):
            continue
        if not p.exists() or not p.is_file():
            continue

        basename = p.name
        mentioned = (abs_path in cmd) or (
            basename and re.search(rf"(?<![A-Za-z0-9_./-]){re.escape(basename)}\b", cmd)
        )
        if not (mentioned or uses_indirection):
            continue

        inner = _scan_agent_written_file(p)
        if inner:
            return f"{inner} via agent-written {basename}"
    return None


def _match_high_impact(tool_name: str, payload: dict) -> str | None:
    if tool_name == "Bash":
        cmd = _bash_command(payload)
        # Event 146 — classify against executed command positions, not raw
        # text. Data-position text (heredoc bodies, quoted string literals,
        # grep patterns, commit-message bodies) no longer triggers; wrapper
        # arguments and command substitutions retain the old sensitivity, and
        # any parse failure falls back to the whole-text scan (fail closed).
        label = _match_executed_command(cmd)
        if label:
            return label
        cwd = Path(payload.get("cwd") or os.getcwd())
        label = _match_script_execution(cwd, cmd)
        if label:
            return label
        return _match_agent_written_files(cmd)
    if tool_name in {"Write", "Edit", "MultiEdit"}:
        target = _write_target(payload).replace("\\", "/")
        name = Path(target).name if target else ""
        for lock in IRREVERSIBLE_WRITE_PATHS:
            if name == lock:
                return f"edit {lock}"
        return None
    return None


# Belt-and-suspenders traversal cap for the root walk. The `.git` repo
# boundary and the filesystem root both terminate the walk in governed and
# ungoverned trees respectively; this cap only bites on a pathological
# symlink cycle or an absurdly deep ungoverned path. Generous enough that a
# real subdirectory cwd (e.g. `pkg/a/b/c/d/e/…`) still reaches its root.
_ROOT_WALK_MAX_DEPTH = 64


def _resolve_episteme_root(cwd: Path) -> Path | None:
    """Nearest ancestor holding `.episteme/`, bounded by the repo boundary.

    Walk UP from ``cwd`` until a directory containing `.episteme/` is found,
    STOPPING at the first directory that carries a `.git` entry (a directory
    in a normal checkout, a FILE in a linked worktree) and at the filesystem
    root. The `.git`-boundary directory itself IS inspected for `.episteme/`
    BEFORE the walk stops — a repo root carries both. The walk NEVER crosses
    a `.git` boundary into a parent repo:

      Event 148 fail-open closer — a nested child repo WITHOUT its own
      `.episteme` must not inherit the parent's surface / advisory marker /
      interrogation verdict. Crossing the boundary would silently disarm the
      guard for an ungoverned repo (a governed op admitted, or blocked-op
      downgraded to advisory, on artifacts the child never authored). That is
      the fail-open shape this resolver exists to prevent.

    Returns ``None`` when no `.episteme/` is found up to (and including) the
    boundary, the filesystem root, or the depth cap — the caller then falls
    back to today's missing-artifact (fail-closed) behavior.

    Pure path checks only — NO `git rev-parse` subprocess on this hot path
    (Event 148 deliverable 5; the subprocess it replaces both crossed the
    nested-repo boundary via its walk fallback and coupled the gate to the
    `git` binary's presence and cwd-discovery quirks). ``cwd`` is resolved to
    its real path first so a symlinked cwd is checked against the real tree.
    """
    probe = cwd.resolve() if cwd.exists() else cwd
    for _ in range(_ROOT_WALK_MAX_DEPTH):
        if (probe / ".episteme").is_dir():
            return probe
        # Repo boundary — checked AFTER `.episteme` so a repo root (which
        # carries both) resolves to itself. `.exists()` matches the `.git`
        # dir of a normal checkout AND the `.git` FILE of a linked worktree.
        if (probe / ".git").exists():
            return None
        if probe.parent == probe:
            break
        probe = probe.parent
    return None


def _canonical_project_root(cwd: Path) -> Path:
    """Governed root for `.episteme` artifact discovery, or ``cwd`` fallback.

    Back-compat wrapper over :func:`_resolve_episteme_root`: returns the
    governed root when one is found before the repo boundary, else ``cwd`` —
    so ``cwd / ".episteme" / …`` names a non-existent artifact and the caller
    gets today's missing-artifact (fail-closed) behavior. The fallback can
    never accidentally satisfy discovery: if ``cwd/.episteme`` existed the
    resolver would have returned ``cwd`` at depth 0.

    Path-A Event 42 (subdirectory cwd survives) is preserved by the walk;
    Event 148 removes the `git rev-parse` subprocess and adds the `.git`
    boundary so a nested child repo cannot inherit a parent's artifacts.
    """
    return _resolve_episteme_root(cwd) or cwd


def _surface_path(cwd: Path) -> Path:
    """Canonical path to the reasoning surface — honors canonical root."""
    return _canonical_project_root(cwd) / ".episteme" / "reasoning-surface.json"


def _advisory_marker_path(cwd: Path) -> Path:
    """Canonical path to the advisory opt-out marker — honors canonical root.

    Routed through the same boundary-aware resolver as the surface so the
    advisory opt-out is seen from a subdirectory cwd (was read from the raw
    cwd and missed — a false strict block) AND is NOT inherited across a
    nested `.git` boundary (a child repo must not be downgraded to advisory
    by a parent's marker — Event 148 fail-open closer).
    """
    return _canonical_project_root(cwd) / ".episteme" / "advisory-surface"


def _read_surface(cwd: Path) -> dict | None:
    p = _surface_path(cwd)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _surface_age_seconds(surface: dict) -> int | None:
    ts = surface.get("timestamp")
    if not ts:
        return None
    try:
        if isinstance(ts, (int, float)):
            return int(time.time() - float(ts))
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(time.time() - dt.timestamp())
    except (ValueError, TypeError):
        return None


def _is_lazy(text: str) -> bool:
    """Return True when `text` is a placeholder rather than a real commitment."""
    collapsed = re.sub(r"\s+", " ", text.strip().lower())
    if not collapsed:
        return True
    if collapsed in LAZY_TOKENS:
        return True
    # Also catch "none." / "n/a!" etc. — trim trailing punctuation and retry.
    stripped = collapsed.rstrip(".!?,;:")
    return stripped in LAZY_TOKENS


# THE_WAY_TO_THINK gate labels (Event 161). The block message names the
# skipped COGNITIVE MOVE, not just the schema field — the gate is where
# the practice reaches the agent, so the message teaches the move at the
# moment of failure. Literal duplicates of
# core/practice/cognitive_moves.gate_move_labels() per the hooks-stay-
# self-contained convention; parity is CI-enforced by
# tests/test_practice_cognitive_moves.py::test_gate_labels_match_guard_duplicates.
_MOVE_BY_FIELD = {
    "core_question": "Frame · Core Question discipline — counters question substitution (Kahneman)",
    "unknowns": "Frame · Unknowns ledger with cost_of_ignorance — counters WYSIATI (Kahneman)",
    "disconfirmation": "Verify · Disconfirmation conditions (pre-committed) — counters motivated reasoning + post-hoc rationalization (cognitive_profile.md § Decision Engine)",
}


def _surface_missing_fields(surface: dict) -> list[str]:
    """Return the list of fields that fail the kernel's validation contract.

    A field is considered missing if it is absent, empty, lazy-placeholder,
    or (for disconfirmation/unknowns) below the minimum-length threshold.
    """
    missing: list[str] = []

    core_q = str(surface.get("core_question") or "").strip()
    if not core_q or _is_lazy(core_q):
        missing.append("core_question")

    unknown_min = _min_unknown_len()
    disc_min = _min_disconfirmation_len()

    unknowns = surface.get("unknowns")
    if not isinstance(unknowns, list):
        missing.append("unknowns")
    else:
        substantive = [
            str(u).strip()
            for u in unknowns
            if str(u).strip()
            and not _is_lazy(str(u))
            and len(str(u).strip()) >= unknown_min
        ]
        if not substantive:
            missing.append("unknowns")

    disc = str(surface.get("disconfirmation") or "").strip()
    if not disc or _is_lazy(disc) or len(disc) < disc_min:
        missing.append("disconfirmation")

    return missing


def _layer2_rejection_label(
    name: str, verdict: str, has_trigger: bool, has_observable: bool,
) -> str:
    """Render one Layer 2 rejection naming the missing contract half.

    ``tautological`` covers three distinct author states (trigger-only,
    observable-only, neither); a remediation message that names the
    wrong half sends the author to fix the part they already have.
    """
    if verdict != "tautological":
        return f"{name} ({verdict})"
    if has_trigger and not has_observable:
        missing = "missing specific observable"
    elif has_observable and not has_trigger:
        missing = "missing conditional trigger"
    else:
        missing = "missing conditional trigger and specific observable"
    return f"{name} (tautological — {missing})"


def _layer2_classify_blueprint_fields(
    surface: dict,
    pending_op: dict,
) -> tuple[str, str]:
    """Layer 2 · v1.0 RC CP3: blueprint-aware specificity classifier.

    Runs AFTER Layer 1 (`_surface_missing_fields`) has already passed.
    Consults the scenario detector for the selected blueprint name,
    loads that blueprint from the registry, and classifies each of the
    blueprint's classifier-eligible fields via `_classify_disconfirmation`.

    Returns ``(verdict, detail)`` where ``verdict`` is one of:

    - ``"pass"``     — every classifier-eligible field classifies as ``fire``
                       (conditional trigger + specific observable). Surface
                       proceeds to the existing ok path.
    NOTE: rejection labels are built by ``_layer2_rejection_label`` so
    the author is told which half of the fire-shape contract is missing
    — the pre-2026-07-03 message described only the trigger-without-
    observable shape and sent observable-without-trigger authors in
    circles (fresh-user recon: 3 of 5 failed attempts).
    - ``"advisory"`` — at least one field classifies as ``absence``
                       (`if no issues arise`-shape). Surface still passes;
                       caller emits a one-line stderr advisory.
    - ``"reject"``   — at least one field classifies as ``tautological``
                       or ``unknown``. Surface is rejected with detail
                       naming the failing fields; caller treats this
                       identically to a Layer-1 ``incomplete`` result.

    Graceful degrade: any error in the scenario detector, registry
    load, or classifier yields ``("pass", "")`` plus a one-line stderr
    note. Layer 1 already passed; we do not synthesize a block from
    our own infrastructure failing.
    """
    try:
        blueprint_name = _detect_scenario(
            pending_op, surface_text=None, project_context={},
            surface=surface,
        )
        blueprint = _load_registry().get(blueprint_name)
    except (_BlueprintParseError, _BlueprintValidationError, KeyError, OSError) as exc:
        sys.stderr.write(
            f"[episteme] Layer 2 fallback: blueprint registry error "
            f"({exc.__class__.__name__}); Layer-1 validation still enforced.\n"
        )
        return ("pass", "")

    classified_fields = _CLASSIFIED_FIELDS_BY_BLUEPRINT.get(blueprint.name, ())
    if not classified_fields:
        return ("pass", "")

    rejections: list[str] = []
    advisories: list[str] = []
    required = set(blueprint.required_fields)

    for field_name in classified_fields:
        if field_name not in required:
            continue  # classifier map lists a field the blueprint doesn't require
        value = surface.get(field_name)
        if field_name == "unknowns" and isinstance(value, list):
            # Per-entry classification. Each unknown carries its own
            # trigger+observable contract under the v1.0 RC blueprint
            # rules (spec § Layer 2 — "the generic surface's
            # `disconfirmation` and `unknowns` entries are classified
            # against the same contract").
            for i, entry in enumerate(value):
                verdict, has_trig, has_obs = _classify_parts_for_layer2(entry)
                if verdict in ("tautological", "unknown"):
                    rejections.append(_layer2_rejection_label(
                        f"unknowns[{i}]", verdict, has_trig, has_obs))
                elif verdict == "absence":
                    advisories.append(f"unknowns[{i}] (absence)")
        else:
            verdict, has_trig, has_obs = _classify_parts_for_layer2(value)
            if verdict in ("tautological", "unknown"):
                rejections.append(_layer2_rejection_label(
                    field_name, verdict, has_trig, has_obs))
            elif verdict == "absence":
                advisories.append(f"{field_name} (absence)")

    if rejections:
        detail = (
            f"Layer 2 classifier (blueprint `{blueprint.name}`) rejected: "
            + "; ".join(rejections)
            + ". The contract requires BOTH a conditional trigger word "
              "(`if`/`when`/`should`/`once`/`after`/`unless`) AND a "
              "specific observable (numeric threshold, metric name, "
              "failure verb, or log/dashboard reference) in the same "
              "field — e.g. \"if the deploy regresses, CI turns red "
              "with a non-zero exit code within 10 minutes\"."
        )
        return ("reject", detail)

    if advisories:
        detail = (
            f"Layer 2 advisory (blueprint `{blueprint.name}`): "
            + "; ".join(advisories)
            + ". Absence-conditions (`if no issues arise`) are less useful "
              "than fire-conditions (`if p95 > 400ms`); consider sharpening."
        )
        return ("advisory", detail)

    return ("pass", "")


_FENCE_REQUIRED_FIELDS: tuple[str, ...] = (
    "constraint_identified",
    "origin_evidence",
    "removal_consequence_prediction",
    "reversibility_classification",
    "rollback_path",
)

_FENCE_REVERSIBILITY_VALUES: frozenset[str] = frozenset({
    "reversible", "irreversible"
})


def _layer_fence_validate(surface: dict) -> tuple[str, str]:
    """Fence Reconstruction-specific validation — v1.0 RC CP5.

    Runs AFTER Layer 1 / 2 / 3 pass on a surface whose blueprint was
    selected as `fence_reconstruction`. Checks:

    1. All 5 Fence-required fields are present, non-empty, non-lazy,
       and ≥ 15 chars. Absence of any field → reject.
    2. `origin_evidence` classifies as `"evidence"` via
       `_classify_origin_evidence`. `"legacy"` / `"unknown"` → reject
       with message pointing at the evidence-marker set.
    3. `reversibility_classification` is exactly `"reversible"` or
       `"irreversible"` (case-insensitive). Anything else → reject.
    4. When `reversibility == "irreversible"` → verdict
       ``"advisory-irreversible"`` so the caller emits a stderr
       escalation to Axiomatic Judgment and does NOT write a synthesis
       marker. The op is not blocked by Fence on this axis (Axiomatic
       Judgment blueprint lands at CP6 as structure-only).
    5. When all checks pass and reversibility is `"reversible"` →
       verdict ``"pass"``; caller proceeds to synthesis marker write.

    Returns ``(verdict, detail)`` where verdict ∈ {``"pass"``,
    ``"advisory-irreversible"``, ``"reject"``}.
    """
    missing: list[str] = []
    min_len = _min_disconfirmation_len()
    for field in _FENCE_REQUIRED_FIELDS:
        value = surface.get(field)
        if not isinstance(value, str):
            missing.append(field)
            continue
        stripped = value.strip()
        if not stripped or _is_lazy(stripped):
            missing.append(field)
            continue
        # reversibility is a short enum — don't apply min-length to it.
        if field == "reversibility_classification":
            continue
        if len(stripped) < min_len:
            missing.append(f"{field} (< {min_len} chars)")

    if missing:
        detail = (
            f"Fence Reconstruction blueprint selected but required fields are "
            f"missing, lazy, or too short: {', '.join(missing)}. Add "
            f"`constraint_identified` (file:line), `origin_evidence` "
            f"(git blame / commit SHA / issue ID / dated reference), "
            f"`removal_consequence_prediction` (observable), "
            f"`reversibility_classification` (`reversible` or `irreversible`), "
            f"and `rollback_path` (concrete revert procedure) to the "
            f".episteme/reasoning-surface.json."
        )
        return ("reject", detail)

    # Reversibility enum check.
    reversibility = str(
        surface.get("reversibility_classification") or ""
    ).strip().lower()
    if reversibility not in _FENCE_REVERSIBILITY_VALUES:
        detail = (
            f"Fence Reconstruction: `reversibility_classification` must be "
            f"`reversible` or `irreversible` (got {reversibility!r}). See "
            f"spec § Blueprint B."
        )
        return ("reject", detail)

    # origin_evidence — evidence markers vs legacy hedge.
    origin = surface.get("origin_evidence", "")
    evidence_verdict = _classify_origin(origin)
    if evidence_verdict != "evidence":
        detail = (
            f"Fence Reconstruction: `origin_evidence` classified as "
            f"`{evidence_verdict}` — the constraint's origin must cite a "
            f"concrete evidence marker (commit SHA, @file:line reference, "
            f"issue/incident ID, URL, dated event, or explicit "
            f"`git blame` / `post-mortem` citation). Soft hedges like "
            f"'unclear — probably legacy' do not reconstruct the fence; "
            f"they restate its absence."
        )
        return ("reject", detail)

    if reversibility == "irreversible":
        detail = (
            "Fence Reconstruction: `reversibility_classification = "
            "irreversible` — this op exceeds Blueprint B's scope. "
            "Escalate to Blueprint A (Axiomatic Judgment) which decomposes "
            "per-source conflicts on irreversible decisions. "
            "Axiomatic Judgment structural validation lands at CP6 as "
            "structure-only; full enforcement lands v1.0.1. Until then "
            "this is an advisory-only escalation (not a block). "
            "No constraint-safety protocol will be synthesized for an "
            "irreversible op."
        )
        return ("advisory-irreversible", detail)

    return ("pass", "")


def _layer4_fence_smoke_test(
    surface: dict,
    cwd: Path,
) -> tuple[str, str]:
    """Layer 4 · CP6 — Fence rollback_path smoke test.

    Runs AFTER `_layer_fence_validate` returns ``"pass"`` on a
    reversible Fence firing. The Fence blueprint declares
    ``verification_trace_maps_to: rollback_path`` — so the existing
    ``rollback_path`` field IS the Layer 4 verification trace. This
    function runs the reversible-context smoke test
    (``shlex.split`` + prod-marker absence + path-existence) against
    it. NOT actual rollback execution — running the rollback at
    PreToolUse would undo the constraint removal before it happens.

    Returns ``(verdict, detail)`` where verdict ∈ {``"pass"``,
    ``"reject"``}. Graceful degrade: any unexpected exception inside
    the smoke test yields ``("pass", "")`` with a stderr fallback in
    the caller — Layers 1-3 + Fence structural checks stay enforced.
    """
    rollback = str(surface.get("rollback_path") or "").strip()
    if not rollback:
        # Should have been caught by _layer_fence_validate's missing-
        # field check; defensive pass-through.
        return ("pass", "")
    verdict, detail = _smoke_test_rollback(rollback, cwd)
    if verdict == "valid":
        return ("pass", "")
    return (
        "reject",
        f"Layer 4 (Fence rollback smoke test): {detail}",
    )


def _maybe_write_pending_contract(
    surface: dict,
    payload: dict,
    cwd: Path,
    label: str,
    blueprint_name: str,
) -> None:
    """CP7: write a hash-chained pending_contract when the surface's
    ``verification_trace`` carries ``window_seconds``. No-op when
    absent. Exception-safe — the caller traps any failure so
    contract bookkeeping never blocks an admitted op."""
    trace_raw = surface.get("verification_trace")
    if not isinstance(trace_raw, dict):
        return
    window = trace_raw.get("window_seconds")
    if not isinstance(window, int) or isinstance(window, bool) or window <= 0:
        return

    cmd = _bash_command(payload) if _tool_name(payload) == "Bash" else ""
    ts = datetime.now(timezone.utc).isoformat()
    correlation = _correlation_id(payload, cmd, ts)
    signature = _build_context_signature(
        cwd, blueprint_name=blueprint_name, op_class=label,
    )
    surface_prov = {
        "core_question": str(surface.get("core_question") or "").strip(),
        "disconfirmation": str(surface.get("disconfirmation") or "").strip(),
    }
    _write_pending_contract(
        correlation_id=correlation,
        op_label=label,
        blueprint=blueprint_name,
        context_signature=signature.as_dict(),
        verification_trace=trace_raw,
        surface_provenance=surface_prov,
    )


def _layer4_generic_validate(
    surface: dict,
    blueprint_name: str,
) -> tuple[str, str]:
    """Layer 4 · CP6 — generic verification_trace validation.

    Called when the selected blueprint declares
    ``verification_trace_required: true`` AND does NOT map the trace
    to a blueprint-specific field (``verification_trace_maps_to`` is
    None — i.e. the generic blueprint at RC). Extracts the
    ``verification_trace`` object from the surface, validates against
    the RC field contract (``_verification_trace.validate_trace``),
    returns a reject when the trace is absent, shape-invalid, has no
    parseable slot, or carries a command without a strict
    threshold_observable.

    This is the closure path for the three spec fluent-vacuous examples
    that honestly passed Layers 2+3: they carry no verification_trace,
    so L4 rejects them with the "declare a commitment" message.
    """
    raw = surface.get("verification_trace")
    trace = _VerificationTrace.from_surface_field(raw)
    verdict, detail = _validate_trace(trace)
    if verdict == "valid":
        return ("pass", "")
    return (
        "reject",
        f"Layer 4 (blueprint `{blueprint_name}`): {detail}. High-impact "
        f"ops must declare a `verification_trace` object with a parseable "
        f"`command` (+ matching `threshold_observable`), `or_dashboard` "
        f"(http(s) URL), or `or_test` (pytest / unittest id) — the "
        f"kernel uses it at Layer 6 / CP7 to check whether the "
        f"disconfirmation actually fired.",
    )


def _surface_status(cwd: Path) -> tuple[str, str]:
    # Disambiguate "file absent" from "file present but malformed". The
    # two cases surface the same `_read_surface` return (None) but ask
    # the operator to take different actions — author vs. repair. Parse
    # inline here so the status detail can name the actual failure.
    p = _surface_path(cwd)
    if not p.exists():
        return "missing", "no .episteme/reasoning-surface.json found"
    try:
        surface = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return "invalid", (
            f"surface file exists but is not valid JSON "
            f"({exc.__class__.__name__} at line {exc.lineno}, col {exc.colno})"
        )
    except OSError as exc:
        return "invalid", f"surface file exists but could not be read ({exc.__class__.__name__})"
    if not isinstance(surface, dict):
        return "invalid", "surface file is valid JSON but not an object"
    age = _surface_age_seconds(surface)
    if age is None:
        return "invalid", "surface has no parseable timestamp"
    if age > SURFACE_TTL_SECONDS:
        mins = age // 60
        return "stale", f"surface is {mins} minute(s) old (TTL {SURFACE_TTL_SECONDS // 60} min)"
    missing = _surface_missing_fields(surface)
    if missing:
        moves = "; ".join(_MOVE_BY_FIELD.get(f, f) for f in missing)
        detail = (
            f"cognitive move(s) skipped — {moves}. "
            f"Surface fails validation on: {', '.join(missing)}. "
            f"Disconfirmation must be a concrete observable condition "
            f"(>= {_min_disconfirmation_len()} chars, not 'none'/'n/a'/'tbd'/'해당 없음'). "
            f"At least one unknown must be sharp and specific (>= {_min_unknown_len()} chars)."
        )
        return "incomplete", detail
    return "ok", ""


def _write_audit(
    tool: str, op: str, cwd: Path, status: str, action: str, mode: str,
    source: str = "surface",
) -> None:
    audit_path = Path.home() / ".episteme" / "audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    entry: dict[str, object] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool,
        "op": op,
        "cwd": str(cwd),
        "status": status,
        "action": action,
        "mode": mode,
        # Event 138 — which artifact satisfied (or failed) the gate:
        # "surface" (v1 Reasoning Surface) or "interrogation" (v2
        # verdict). E3 falsifiability measurement reads this field.
        "source": source,
    }
    # Honest environment tagging (E3 measurement integrity,
    # 2026-07-03): 38 of the first 50 interrogation-source audit
    # records were pytest fixtures, indistinguishable from lived use —
    # the E3 grep would have "passed" on test-suite noise alone. Tag
    # records written under a test runner so the measurement (kernel/
    # FALSIFIABILITY_CONDITIONS.md § E3) can exclude them. Tag, don't
    # drop: users may legitimately work under /tmp, and dropped
    # records would hide real gate activity.
    if os.environ.get("PYTEST_CURRENT_TEST"):
        entry["test_env"] = True
    try:
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Audit failure must never block operations


def _correlation_id(payload: dict, cmd: str, ts: str) -> str:
    """Derive a correlation id tying a PreToolUse prediction to its PostToolUse outcome.

    Prefers the runtime-provided `tool_use_id`. Falls back to a SHA-1 over
    (ts-second, cwd, cmd) which will match between the two hook invocations
    on any sane hook runner that fires them within the same second for the
    same call.
    """
    rid = payload.get("tool_use_id") or payload.get("toolUseId") or payload.get("request_id")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    cwd = str(payload.get("cwd") or os.getcwd())
    bucket = ts.split(".")[0]  # truncate to whole-second resolution
    seed = f"{bucket}|{cwd}|{cmd}".encode("utf-8", errors="replace")
    return "h_" + hashlib.sha1(seed).hexdigest()[:16]


def _extract_prediction(surface: dict | None) -> dict:
    """Extract the falsifiable claims of a Reasoning Surface for calibration.

    Records only the fields load-bearing for predicted-vs-observed audit:
    the core question, disconfirmation condition, unknowns, and hypothesis.
    """
    if not isinstance(surface, dict):
        return {}
    return {
        "core_question": str(surface.get("core_question") or "").strip(),
        "disconfirmation": str(surface.get("disconfirmation") or "").strip(),
        "unknowns": [str(u).strip() for u in (surface.get("unknowns") or []) if str(u).strip()],
        "hypothesis": str(surface.get("hypothesis") or "").strip(),
    }


def _redact(cmd: str) -> str:
    """Crude secret-redaction — command_executed must not carry tokens.

    Inlined (not imported from episodic_writer) because the hook is invoked
    as a standalone script with no guaranteed sys.path. If this pattern set
    diverges from episodic_writer._redact, unify by editing both.
    """
    if not cmd:
        return cmd
    patterns = [
        (re.compile(r"(?i)((?:password|passwd|token|secret|api[_-]?key|bearer))(\s*[=:]\s*)\S+"),
         r"\1\2<REDACTED>"),
        (re.compile(r"AKIA[0-9A-Z]{16}"), "<REDACTED-AWS-KEY>"),
        (re.compile(r"(?i)ghp_[a-z0-9]{30,}"), "<REDACTED-GH-TOKEN>"),
    ]
    redacted = cmd
    for pat, repl in patterns:
        redacted = pat.sub(repl, redacted)
    return redacted


def _telemetry_path(ts: str) -> Path:
    date = ts[:10]  # YYYY-MM-DD
    return Path.home() / ".episteme" / "telemetry" / f"{date}-audit.jsonl"


def _write_telemetry(record: dict) -> None:
    """Append a JSONL record to the day-scoped telemetry file. Never raises."""
    try:
        path = _telemetry_path(record["ts"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except (OSError, KeyError):
        pass  # Telemetry failure must never block operations


def _write_prediction(
    payload: dict,
    tool: str,
    op: str,
    cmd: str,
    cwd: Path,
    surface: dict | None,
    blueprint_name: str = "generic",
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    record = {
        "ts": ts,
        "event": "prediction",
        "correlation_id": _correlation_id(payload, cmd, ts),
        "tool": tool,
        "op": op,
        "cwd": str(cwd),
        "command_executed": _redact(cmd),
        "epistemic_prediction": _extract_prediction(surface),
        # CP8 — PostToolUse spot-check reads blueprint_name back from
        # here so it can compute the blueprint_fired multiplier without
        # re-running scenario detection.
        "blueprint_name": blueprint_name,
        "exit_code": None,
    }
    _write_telemetry(record)


def _advisory_footer() -> str:
    """Phase A · v1.0.1 — render an operator-posture advisory block from
    derived knobs. Silent when no knobs are set.

    Closes the Q1 "knobs computed but not consumed" gap for two axes:

    - ``preferred_lens_order`` (Munger latticework — cognitive.dominant_lens
      verbatim from the operator profile) becomes a Frame-stage hint the
      operator sees when they are about to author a surface, so the lens
      discipline is visible at the exact moment the Reasoning Surface is
      being composed.
    - ``explanation_form`` (cognitive.explanation_depth) becomes a framing
      hint about the kind of Knowns / Assumptions prose the operator
      prefers (e.g. causal-chain over pattern-analogy).

    Advisory-only — never changes the hook's exit code or the block/pass
    decision. The footer only appears inside the block/advisory message
    shown to the operator after Layer 1-4 has ALREADY determined the
    surface is incomplete or missing.

    Kernel anchor: `kernel/OPERATOR_PROFILE_SCHEMA.md` § 5 (derived knobs);
    `docs/PROGRESS.md` Event 25 (Phase A scope).
    """
    lines: list[str] = []

    lens_order = _load_derived_knob("preferred_lens_order", None)
    if isinstance(lens_order, list) and lens_order:
        cleaned = [str(x) for x in lens_order if isinstance(x, str) and x]
        if cleaned:
            lines.append(
                "Operator lens order (apply to Unknowns / Disconfirmation): "
                + " → ".join(cleaned[:5])
            )

    explanation = _load_derived_knob("explanation_form", None)
    if isinstance(explanation, str) and explanation:
        lines.append(
            f"Explanation depth: {explanation} — prefer mechanisms over "
            f"pattern analogies in Knowns / Assumptions."
        )

    if not lines:
        return ""
    return (
        "\n--- Operator posture (from derived knobs) ---\n"
        + "\n".join(lines) + "\n"
    )


# Shape hints for blueprint-specific required fields. Keyed by field
# name; rendered verbatim into the template skeleton (must stay valid
# JSON — a stranger copies the skeleton and replaces placeholder
# values). Enum vocabularies are sourced from the validating module so
# template/validator drift fails tests/test_surface_template_roundtrip.
_TEMPLATE_FIELD_SHAPES: dict[str, str] = {
    "flaw_classification":
        '"<one of: ' + " | ".join(sorted(_TEMPLATE_FLAW_CLASSES)) + '>"',
    "posture_selected":
        '"<one of: ' + " | ".join(sorted(_TEMPLATE_POSTURE_VALUES)) + '>"',
    "patch_vs_refactor_evaluation":
        '"<why this posture for THIS change — name the concrete '
        'modules/layers involved; generic phrasing is rejected>"',
    "blast_radius_map":
        '[{"surface": "<file or doc this op touches>", '
        '"status": "needs_update"}, '
        '{"surface": "<surface deliberately untouched>", '
        '"status": "not-applicable", '
        '"rationale": "<why it is untouched>"}]',
    "sync_plan":
        '[{"surface": "<each needs_update surface above>", '
        '"action": "<what will be done to it>"}]',
    "deferred_discoveries": "[]",
    "removal_consequence_prediction":
        '"<if/when the constraint is removed, <specific observable: '
        'number, metric, failure verb, or log/dashboard ref>>"',
    "origin_evidence":
        '"<concrete pointer: commit SHA, path:line, URL, issue ID, or '
        'dated event — hedges like \'probably legacy\' are rejected>"',
}

_TEMPLATE_BASE_FIELDS: tuple[str, ...] = (
    "timestamp", "core_question", "knowns", "unknowns", "assumptions",
    "disconfirmation",
)


def _surface_template(blueprint_name: str = "generic") -> str:
    """Render the remediation template for the ACTIVE blueprint.

    Contract (tests/test_surface_template_roundtrip.py): a surface
    built by filling exactly the fields this template names must pass
    the guard's own strict validation in one attempt. That means every
    conditionally-required field — `verification_trace` for CP6
    blueprints, the Blueprint D six for architectural_cascade, the
    Fence fields — must appear here with a shape a stranger can follow
    without reading core/hooks source. Registry failures degrade to the
    base six-field skeleton; the block message must never crash.
    """
    entries: list[str] = [
        '"timestamp": "<ISO-8601 UTC>"',
        '"core_question": "<one question this work answers>"',
        '"knowns": ["..."]',
        '"unknowns": ["<conditional trigger word (if/when/should/once/'
        'after/unless) + specific observable (number, metric name, '
        'failure verb, or log/dashboard ref), >= 15 chars>"]',
        '"assumptions": ["..."]',
        '"disconfirmation": "<same fire shape — conditional trigger + '
        'specific observable, >= 15 chars>"',
    ]
    guidance = ""

    blueprint = None
    try:
        blueprint = _load_registry().get(blueprint_name)
    except Exception:
        blueprint = None  # degrade to the base skeleton — never crash.

    if blueprint is not None:
        for field in blueprint.required_fields:
            if field in _TEMPLATE_BASE_FIELDS:
                continue
            shape = _TEMPLATE_FIELD_SHAPES.get(
                field, f'"<required by blueprint `{blueprint.name}`>"'
            )
            entries.append(f'"{field}": {shape}')
        needs_trace = (
            blueprint.verification_trace_required
            and blueprint.verification_trace_maps_to is None
        )
        if needs_trace:
            entries.append(
                '"verification_trace": {\n'
                '    "command": "<shell command, >= 2 tokens, that '
                'verifies this op>",\n'
                '    "threshold_observable": "<comparison with a number,'
                " e.g. 'exit code == 0'>\",\n"
                '    "window_seconds": 300\n'
                "  }"
            )
            guidance = (
                "\nThe verification_trace also accepts `or_test`: "
                '"<pytest node id>" or `or_dashboard`: "<https URL>" in '
                "place of command + threshold_observable."
            )

    base = (
        "Write .episteme/reasoning-surface.json with:\n"
        "{\n  "
        + ",\n  ".join(entries)
        + "\n}\n"
        "Lazy values (none, n/a, tbd, 해당 없음, 없음, ...) are rejected."
        + guidance
    )
    return base + _advisory_footer()


def _try_tier1_dispatch(payload: dict, tool_name: str, label: str) -> bool:
    """Event 135 — Stage 2 Tier-1 advisory dispatch path.

    Returns True iff the op qualifies for Tier 1 dispatch AND a valid
    micro-surface exists AND the soak gate is open. On True, an advisory
    has already been emitted to stderr and main() should return 0
    immediately. On False, main() continues to the existing strict-block
    validation (loss-averse default).

    Any exception in the dispatch path falls through to False — the
    existing gate remains the source of truth on errors.
    """
    try:
        from core.hooks._irreversible_tier import (  # noqa: E402
            Tier as _Tier,
            classify as _classify,
            load_git_context as _load_git_ctx,
            load_operator_profile as _load_profile,
            soak_gate_open as _soak_gate,
            validate_micro_surface as _validate_micro,
        )
    except Exception as exc:
        sys.stderr.write(
            f"[episteme tier1] import fallback: "
            f"{exc.__class__.__name__} — strict-block enforced\n"
        )
        return False

    try:
        cwd = Path(payload.get("cwd") or os.getcwd())
        git_ctx = _load_git_ctx(cwd)
        verdict = _classify(
            tool_name=tool_name,
            tool_args=_tool_input(payload),
            git_context=git_ctx,
            operator_profile=_load_profile(),
        )
    except Exception as exc:
        sys.stderr.write(
            f"[episteme tier1] classify fallback: "
            f"{exc.__class__.__name__} — strict-block enforced\n"
        )
        return False

    if verdict.tier != _Tier.ONE:
        return False  # Tier 2 or Tier 3 — existing path handles it

    # Read the on-disk surface ONCE and check it's shaped as a Tier 1
    # micro-surface (tier=1 field). Anything else falls through.
    surface_dict = _read_surface(cwd)
    if surface_dict is None or surface_dict.get("tier") != 1:
        sys.stderr.write(
            f"[episteme tier1] {verdict.reason} — no Tier 1 micro-surface "
            f"on disk; falling through to strict-block\n"
        )
        return False

    try:
        ok, reason = _validate_micro(surface_dict, git_ctx)
    except Exception as exc:
        sys.stderr.write(
            f"[episteme tier1] validator fallback: "
            f"{exc.__class__.__name__} — strict-block enforced\n"
        )
        return False
    if not ok:
        sys.stderr.write(
            f"[episteme tier1] micro-surface invalid: {reason} — "
            f"falling through to strict-block\n"
        )
        return False

    try:
        gate_open, gate_reason = _soak_gate()
    except Exception as exc:
        sys.stderr.write(
            f"[episteme tier1] soak-gate fallback: "
            f"{exc.__class__.__name__} — strict-block enforced\n"
        )
        return False
    if not gate_open:
        sys.stderr.write(
            f"[episteme tier1] {gate_reason} — falling through to "
            f"strict-block until soak clears\n"
        )
        return False

    # All three gates open — emit the advisory and let the op through.
    # Claude Code's permission popup is the next gate.
    sys.stderr.write(
        f"[episteme tier1 advisory] {verdict.reason} on `{label}`; "
        f"micro-surface valid; {gate_reason}. Operator confirmation "
        f"required at the permission popup.\n"
    )
    return True


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    tool_name = _tool_name(payload)
    label = _match_high_impact(tool_name, payload)
    # CP5: the Fence Reconstruction selector admits constraint-removal
    # ops as high-impact even when the command word itself (`rm`,
    # `disable`, `delete`) is not in the generic HIGH_IMPACT_BASH
    # pattern set. This is how `rm .episteme/advisory-surface` and
    # `git rm kernel/FAILURE_MODES.md` reach the surface-validation
    # gate — Fence's compound AND (removal-verb ∧ constraint-path) is
    # the specificity gate that makes admitting the op FP-averse.
    if not label:
        # Scenario-detector dispatch for BYOS ops that bypass
        # HIGH_IMPACT_BASH but should reach surface validation. Reads
        # the surface once so Blueprint D's self-escalation trigger
        # can inspect flaw_classification. Cascade > Fence > generic
        # priority per the scenario detector.
        _probe_cwd = Path(payload.get("cwd") or os.getcwd())
        _probe_surface = _read_surface(_probe_cwd)
        try:
            _probe_scenario = _detect_scenario(
                payload, surface_text=None, project_context={},
                surface=_probe_surface,
            )
        except Exception:
            _probe_scenario = None
        if _probe_scenario == "architectural_cascade":
            label = "cascade:architectural"
        elif _probe_scenario == "fence_reconstruction":
            label = "fence:constraint-removal"
    if not label:
        return 0

    # Event 135 — Stage 2 Tier-1 advisory dispatch.
    # Runs AFTER high-impact pattern match (label is non-None) but BEFORE
    # the strict-block surface validation. When ALL THREE conditions
    # hold — classifier returns Tier.ONE, the on-disk surface is a
    # valid micro-surface, AND the soak gate is open per Stage 3's
    # lived-behavior threshold — the hook emits a stderr advisory and
    # exits 0. Claude Code's permission popup remains the human-in-loop
    # gate. ANY of those gates failing falls through to the existing
    # strict-block path below (loss-averse precedence: an error or gap
    # in the new path never weakens the gate).
    _tier1_dispatched = _try_tier1_dispatch(payload, tool_name, label)
    if _tier1_dispatched:
        return 0

    cwd = Path(payload.get("cwd") or os.getcwd())
    status, detail = _surface_status(cwd)
    # Event 148 — resolve the advisory marker through the boundary-aware
    # root helper (same as the surface), NOT the raw cwd: a subdir cwd must
    # still see the root marker, and a nested child repo must NOT inherit
    # the parent's marker.
    advisory_only = _advisory_marker_path(cwd).exists()
    mode = "advisory" if advisory_only else "strict"
    # Default blueprint name — overridden by the layer-2/3 block when
    # the surface file exists and scenario detection runs. Declared
    # here so CP8's prediction-record extension can always read it.
    blueprint_name = "generic"

    # Event 138 · v2.0 Epistemic Engine — a fresh interrogation verdict
    # (.episteme/interrogation.json, produced by the epistemic-
    # interrogation skill) is an alternative satisfier to the Reasoning
    # Surface. The verdict artifact records decomposed claims with
    # factored external verification, an argued opposition, and a
    # pre-committed disconfirmation — substance the surface's form
    # contract cannot see. `stop` verdicts and structural-floor
    # failures fall through to the v1 path unchanged (fails closed).
    # Spec: docs/DESIGN_V2_0_EPISTEMIC_ENGINE.md § 7.
    interrogation_admitted = False
    interrogation_detail = ""
    if status != "ok":
        try:
            import _interrogation  # type: ignore  # pyright: ignore[reportMissingImports]
            i_status, i_detail = _interrogation.artifact_status(cwd)
        except Exception:
            i_status, i_detail = "missing", ""
        if i_status == "ok":
            status = "ok"
            interrogation_admitted = True
            sys.stderr.write(
                f"[episteme] high-impact op `{label}` admitted via "
                f"interrogation verdict — {i_detail}\n"
            )
            # Event 139 · E5 — every consumed verdict is spot-checkable.
            # Sample-all; idempotent per artifact; never blocks.
            try:
                import _interrogation as _i5  # type: ignore  # pyright: ignore[reportMissingImports]
                _i5.enqueue_verdict_spot_check(cwd, op_label=label)
            except Exception:
                pass
        elif i_status != "missing":
            interrogation_detail = i_detail

    # Layer 2 · v1.0 RC CP3 — runs only after Layer 1 passes. A Layer-2
    # rejection downgrades status from "ok" to "incomplete" so the
    # existing block path handles it; an absence-advisory emits a
    # stderr warning and leaves status at "ok".
    #
    # Layer 3 · v1.0 RC CP4 — runs only after Layer 2 leaves status at
    # "ok" (including the Layer-2-advisory case). Blueprint-aware entity
    # grounding: extracts snake_case / SCREAMING_CASE / path+ext / hex-SHA
    # tokens from the blueprint's declared grounded fields and verifies
    # they exist in the project working tree. FP-averse gate per spec
    # § Layer 3. Graceful degrade: any exception yields "pass" with a
    # one-line stderr fallback — Layers 1 & 2 stay enforced.
    if status == "ok" and not interrogation_admitted:
        layer2_surface = _read_surface(cwd)
        if layer2_surface is not None:
            l2_verdict, l2_detail = _layer2_classify_blueprint_fields(
                layer2_surface, payload
            )
            if l2_verdict == "reject":
                status = "incomplete"
                detail = l2_detail
            elif l2_verdict == "advisory":
                sys.stderr.write(f"[episteme advisory] {l2_detail}\n")

            if status == "ok":
                # §3.2 · Single per-op wall-clock sample. ONE
                # `datetime.now()` read for the whole admitted op, threaded
                # to every correlation-id computation below (fence marker,
                # cascade deferred-discovery cid, cascade marker). A per-op
                # timestamp — NOT session-level (which would collapse every
                # op in a session into one h_ bucket and structurally
                # cross-pair Post events). Sampling once makes intra-op h_
                # divergence impossible by construction.
                op_ts = datetime.now(timezone.utc).isoformat()
                try:
                    blueprint_name = _detect_scenario(
                        payload, surface_text=None, project_context={},
                        surface=layer2_surface,
                    ) or "generic"
                except Exception as exc:  # graceful degrade — keep default
                    sys.stderr.write(
                        f"[episteme] scenario detection fallback: "
                        f"{exc.__class__.__name__}\n"
                    )

                # CP9 · Pillar 3 active guidance — one stderr advisory
                # per op. Fires AFTER scenario detection and BEFORE
                # Layer 3's blueprint enforcement per spec. Advisory
                # only — never blocking. Silent on zero match.
                try:
                    _candidate_sig = _build_context_signature(
                        cwd, blueprint_name=blueprint_name, op_class=label,
                    )
                    _match = _guidance_query(_candidate_sig, cwd=cwd)
                    if _match is not None:
                        sys.stderr.write(
                            _guidance_format_advisory(_match) + "\n"
                        )
                except Exception as exc:  # graceful degrade
                    sys.stderr.write(
                        f"[episteme] Pillar 3 guidance fallback: "
                        f"{exc.__class__.__name__}; Layers 1-4 still enforced.\n"
                    )

                try:
                    l3_verdict, l3_detail = _layer3_ground_blueprint_fields(
                        layer2_surface, blueprint_name, cwd
                    )
                except Exception as exc:  # graceful degrade
                    sys.stderr.write(
                        f"[episteme] Layer 3 fallback: "
                        f"{exc.__class__.__name__}; Layers 1 & 2 still enforced.\n"
                    )
                    l3_verdict, l3_detail = ("pass", "")
                if l3_verdict == "reject":
                    status = "incomplete"
                    detail = l3_detail
                elif l3_verdict == "advisory":
                    sys.stderr.write(f"[episteme advisory] {l3_detail}\n")

                # Layer · Fence (CP5) — blueprint-specific validation
                # plus Pillar 3 pending-marker write on reversible
                # success. Runs only when the scenario detector chose
                # fence_reconstruction AND Layers 1-3 left status at
                # "ok". Graceful degrade: any unexpected exception in
                # fence machinery downgrades to a stderr fallback and
                # leaves Layers 1-3 as the ultimate enforcer.
                if status == "ok" and blueprint_name == "fence_reconstruction":
                    try:
                        fence_verdict, fence_detail = _layer_fence_validate(
                            layer2_surface
                        )
                    except Exception as exc:  # graceful degrade
                        sys.stderr.write(
                            f"[episteme] Fence fallback: "
                            f"{exc.__class__.__name__}; Layers 1-3 still "
                            f"enforced.\n"
                        )
                        fence_verdict, fence_detail = ("pass", "")
                    if fence_verdict == "reject":
                        status = "incomplete"
                        detail = fence_detail
                    elif fence_verdict == "advisory-irreversible":
                        sys.stderr.write(
                            f"[episteme advisory] {fence_detail}\n"
                        )
                        # Do NOT write synthesis marker on irreversible.
                    elif fence_verdict == "pass":
                        # Layer 4 · CP6 — Fence rollback_path smoke test.
                        # Spec § Blueprint B: verification is the
                        # rollback_path executed as a smoke test in a
                        # reversible context. At RC the smoke test is
                        # syntactic + path-existence + prod-marker
                        # absence; full sandboxed execution lands in
                        # v1.0.1.
                        try:
                            l4_verdict, l4_detail = _layer4_fence_smoke_test(
                                layer2_surface, cwd
                            )
                        except Exception as exc:  # graceful degrade
                            sys.stderr.write(
                                f"[episteme] Layer 4 (Fence smoke) "
                                f"fallback: {exc.__class__.__name__}; "
                                f"Layers 1-3 + Fence structural still "
                                f"enforced.\n"
                            )
                            l4_verdict, l4_detail = ("pass", "")
                        if l4_verdict == "reject":
                            status = "incomplete"
                            detail = l4_detail
                    if status == "ok" and fence_verdict == "pass":
                        # Reversible Fence admitted AND Layer 4 smoke
                        # test green — write Pillar 3 pending-synthesis
                        # marker for the PostToolUse finalizer to act on
                        # (exit_code == 0 → constraint-safety protocol
                        # written to ~/.episteme/framework/protocols.jsonl).
                        try:
                            cmd_for_marker = (
                                _bash_command(payload)
                                if tool_name == "Bash" else ""
                            )
                            # Event 50 · CP-FENCE-02 — write the marker
                            # under every candidate correlation id so
                            # PostToolUse pairs reliably even when
                            # PreToolUse and PostToolUse payloads
                            # disagree on which id is available
                            # (Claude Code's Pre payload typically
                            # lacks tool_use_id). §3.1: pass session_scope
                            # so the marker carries the pair signature for
                            # the tier-3 fallback.
                            _fence_scope = str(payload.get("session_id") or "")
                            for correlation in _fence_synthesis.candidate_correlation_ids(
                                payload,
                                cmd_for_marker,
                                op_ts,
                            ):
                                _fence_synthesis.write_pending_marker(
                                    layer2_surface,
                                    correlation,
                                    cwd,
                                    cmd_for_marker,
                                    session_scope=_fence_scope,
                                )
                        except Exception:
                            # Synthesis bookkeeping failure must never
                            # block the admitted op. Layers 1-3 +
                            # Fence + L4 have already validated;
                            # synthesis is advisory-in-aggregate.
                            pass

                # Blueprint D · CP10 — architectural cascade
                # structural validation. Runs when the scenario
                # detector picked architectural_cascade AND Layers
                # 1-3 left status at "ok". Graceful degrade: any
                # exception in Blueprint D machinery downgrades to
                # a stderr fallback and leaves Layers 1-3 as the
                # ultimate enforcer.
                if status == "ok" and blueprint_name == "architectural_cascade":
                    try:
                        bd_verdict, bd_detail = _validate_blueprint_d(
                            layer2_surface
                        )
                    except Exception as exc:  # graceful degrade
                        sys.stderr.write(
                            f"[episteme] Blueprint D fallback: "
                            f"{exc.__class__.__name__}; Layers 1-3 still "
                            f"enforced.\n"
                        )
                        bd_verdict, bd_detail = ("pass", "")
                    if bd_verdict == "reject":
                        status = "incomplete"
                        detail = bd_detail
                    elif bd_verdict in (
                        "advisory-theater", "advisory-other",
                        "advisory-theater-plus-other",
                    ):
                        sys.stderr.write(f"[episteme advisory] {bd_detail}\n")

                    # On admission, hash-chain every
                    # deferred_discoveries[] entry immediately.
                    # CP10 plan Q7 — writer failure never blocks
                    # admission.
                    if status == "ok":
                        try:
                            _cmd_for_cid = (
                                _bash_command(payload)
                                if tool_name == "Bash" else ""
                            )
                            _cid = _correlation_id(
                                payload, _cmd_for_cid, op_ts,
                            )
                            _write_cascade_deferred_discoveries(
                                layer2_surface,
                                correlation_id=_cid,
                                op_label=label,
                                cwd=cwd,
                            )
                        except Exception:
                            pass  # bookkeeping never blocks.

                        # T13 · Blueprint D synthesis arm (Event 143,
                        # spec DESIGN_V1_0_SEMANTIC_GOVERNANCE.md:204).
                        # Write the Pillar 3 pending marker under every
                        # candidate correlation id (Event 50 pairing);
                        # the PostToolUse finalizer emits the cascade
                        # protocol iff the op exits 0.
                        try:
                            import _cascade_synthesis  # type: ignore  # pyright: ignore[reportMissingImports]
                            _cmd_for_marker = (
                                _bash_command(payload)
                                if tool_name == "Bash" else ""
                            )
                            # §3.2: same per-op `op_ts` — NOT a second
                            # `_marker_ts` sample (which straddled a second
                            # boundary against the deferred-cid sample).
                            for _corr in _fence_synthesis.candidate_correlation_ids(
                                payload, _cmd_for_marker, op_ts,
                            ):
                                _cascade_synthesis.write_pending_marker(
                                    layer2_surface,
                                    _corr,
                                    cwd,
                                    _cmd_for_marker,
                                )
                        except Exception:
                            pass  # synthesis bookkeeping never blocks.

                # Layer 4 · CP6 — generic verification_trace. Runs when
                # the blueprint declares verification_trace_required:
                # true AND does NOT map the trace to a field (Fence is
                # already handled in-line above). At RC this applies to
                # the generic blueprint — closing the three fluent-
                # vacuous examples from spec § "Why this exists" that
                # honestly passed Layers 2+3.
                #
                # CP7 extension: when Layer 4 passes AND the trace
                # carries `window_seconds`, the guard also writes a
                # hash-chained pending_contract to
                # ~/.episteme/state/pending_contracts.jsonl so Phase 12
                # can correlate the trace against bash-history telemetry
                # at SessionStart. Fence has its own synchronous smoke
                # test and does NOT use the pending-contracts stream.
                if status == "ok" and blueprint_name != "fence_reconstruction":
                    try:
                        _bp = _load_registry().get(blueprint_name)
                        _needs_trace = (
                            _bp.verification_trace_required
                            and _bp.verification_trace_maps_to is None
                        )
                    except (_BlueprintParseError, _BlueprintValidationError,
                            KeyError, OSError):
                        _bp = None
                        _needs_trace = False
                    if _needs_trace:
                        try:
                            l4g_verdict, l4g_detail = _layer4_generic_validate(
                                layer2_surface, blueprint_name
                            )
                        except Exception as exc:  # graceful degrade
                            sys.stderr.write(
                                f"[episteme] Layer 4 generic fallback: "
                                f"{exc.__class__.__name__}; Layers 1-3 "
                                f"still enforced.\n"
                            )
                            l4g_verdict, l4g_detail = ("pass", "")
                        if l4g_verdict == "reject":
                            status = "incomplete"
                            detail = l4g_detail
                        elif l4g_verdict == "pass":
                            # CP7: hash-chained Layer 6 pending-contract
                            # write when window_seconds is declared.
                            try:
                                _maybe_write_pending_contract(
                                    layer2_surface, payload, cwd,
                                    label, blueprint_name,
                                )
                            except Exception:
                                # Contract bookkeeping failure must not
                                # block an admitted op. Layers 1-4 have
                                # already validated; the missing L6
                                # record just means Phase 12 can't
                                # correlate this op retroactively.
                                pass

    if status == "ok":
        _write_audit(
            tool_name, label, cwd, status, "passed", mode,
            source="interrogation" if interrogation_admitted else "surface",
        )
        # Calibration telemetry: record the prediction so a PostToolUse hook
        # can pair it with the observed exit_code. Only fires for Bash, since
        # only Bash calls have a meaningful "outcome" against a prediction.
        if tool_name == "Bash":
            cmd = _bash_command(payload)
            surface = _read_surface(cwd)
            _write_prediction(
                payload, tool_name, label, cmd, cwd, surface,
                blueprint_name=blueprint_name,
            )
        return 0

    # Template must match the blueprint that will validate the retry.
    # `blueprint_name` is only set by the Layer-2/3 flow, which never
    # runs when the surface is missing or Layer-1-incomplete — exactly
    # the moments the template is printed. Detect here (surface may be
    # None; the detector accepts that) so a cascade/fence op's block
    # message names the fields its OWN validator will demand, not the
    # generic six. Round-trip contract:
    # tests/test_surface_template_roundtrip.py.
    template_blueprint = blueprint_name
    try:
        template_blueprint = _detect_scenario(
            payload, surface_text=None, project_context={},
            surface=_read_surface(cwd),
        )
    except Exception:
        pass  # degrade to the generic template — never crash the block.

    header = f"REASONING SURFACE {status.upper()}: high-impact op `{label}` with {detail}."
    if interrogation_detail:
        header += f" Interrogation artifact: {interrogation_detail}."

    # Event 146 — per-session dedup. The full ~2.3 KB two-artifact schema
    # is shown on the FIRST firing in a session; later firings in the same
    # session collapse to a 1-2 line pointer so repeat blocks cost <10% of
    # the original bytes. Decided here (after the status=="ok" early return)
    # so an admitted op never consumes the session's first-firing slot.
    show_full = _should_show_full_surface(payload)

    if show_full:
        # Event 138 — factual statements, two satisfier paths. The hooks
        # doctrine reserves imperatives for the model's own instructions;
        # out-of-band context states what exists and what would satisfy.
        instruction = (
            "Two artifacts satisfy this gate: (1) a fresh interrogation "
            "verdict at .episteme/interrogation.json, produced by the "
            "epistemic-interrogation skill — the decision decomposed into "
            "tiered claims, load-bearing claims verified in a fresh context "
            "against external evidence, an argued opposition, a weakest "
            "link, and a pre-committed disconfirmation; or (2) a Reasoning "
            f"Surface at .episteme/reasoning-surface.json: "
            f"{_surface_template(template_blueprint)}"
        )
    else:
        instruction = _surface_pointer(label, status)

    if not advisory_only:
        _write_audit(tool_name, label, cwd, status, "blocked", mode)
        if show_full:
            sys.stderr.write(
                "Execution blocked by Episteme Strict Mode: no valid "
                "Reasoning Surface or interrogation verdict exists for this "
                "high-impact op.\n"
                f"{header}\n{instruction}\n"
                "Per-project advisory mode (not recommended) is enabled by "
                "`touch .episteme/advisory-surface`.\n"
            )
        else:
            sys.stderr.write(f"Episteme Strict Mode: {instruction}\n")
        return 2

    _write_audit(tool_name, label, cwd, status, "advisory", mode)
    if show_full:
        additional_context = (
            f"{header} Advisory mode is active (.episteme/advisory-surface "
            f"present); the op proceeds unblocked and this gap is "
            f"recorded in the audit trail. {instruction}"
        )
    else:
        additional_context = instruction
    advisory = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": additional_context,
        }
    }
    sys.stdout.write(json.dumps(advisory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
