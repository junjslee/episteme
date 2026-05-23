"""Tiered irreversible-op classifier — proposal artifact (NOT yet wired).

See `docs/PROPOSAL_TIERED_IRREVERSIBLE_GATE.md` for the full design
rationale. This module is a standalone, pure-function classifier that
takes a (tool, args, git_context) triple and returns one of three tiers:

- `Tier.ONE` — bounded irreversible op (e.g., `git push origin
  feature-branch`). Requires a 2-field micro-surface plus operator confirm.
- `Tier.TWO` — current strict-block behavior. Requires the full Reasoning
  Surface per `kernel/REASONING_SURFACE.md`.
- `Tier.THREE` — denylist hard reject. No surface will pass; operator
  must override out-of-loop or rewrite the op.

This module is **not** imported by `core/hooks/reasoning_surface_guard.py`
in this Event. Integration is staged per § 6 of the proposal — operator
must approve the Tier 1 allowlist before the hook gains a path that
relaxes the strict-block default.

The classifier is consistent with the existing hook's normalization
discipline (`_NORMALIZE_SEPARATORS` at `core/hooks/reasoning_surface_guard.py:208`)
so bypass shapes like `subprocess.run(['git','push'])` route through the
same classification as bare `git push`.
"""
from __future__ import annotations

import enum
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


__all__ = [
    "Tier",
    "GitContext",
    "TierConfig",
    "OperatorProfile",
    "ClassifierVerdict",
    "MicroSurface",
    "classify",
    "validate_micro_surface",
    "load_protected_branches",
    "load_git_context",
    "load_operator_profile",
    "soak_gate_open",
    "write_tier1_record",
    "normalize_command",
    "TIER1_TELEMETRY_PATH",
    "MICRO_SURFACE_TTL_SECONDS",
    "MICRO_SURFACE_RATIONALE_MIN_LEN",
    "MICRO_SURFACE_DISCONFIRMATION_MIN_LEN",
    "SOAK_GATE_MIN_OPS",
    "SOAK_GATE_MIN_DAYS",
    "SOAK_GATE_MIN_RATIONALE_ACCURACY",
]


# Event 135 — Stage 3 soak gate constants per proposal § 7.
# Calibration thresholds: N ≥ 20 Tier 1 ops across ≥ 7 calendar days,
# rationale-accuracy rate ≥ 90% (operator confirmed proceed AND no
# subsequent revert within 24h), zero retroactive Tier 1 → Tier 2
# escalations, zero Tier 3 denylist ops slipping through Tier 1.
SOAK_GATE_MIN_OPS = 20
SOAK_GATE_MIN_DAYS = 7
SOAK_GATE_MIN_RATIONALE_ACCURACY = 0.90


# Operator-resolved constants per Event 134.1 (Stage 1 approval).

# § 4 of the proposal — Tier 1 micro-surface schema constants. Updated to
# include the branch-binding field that prevents context-bleed within the
# 5-minute TTL window across different irreversible ops.
MICRO_SURFACE_TTL_SECONDS = 300  # 5 minutes
MICRO_SURFACE_RATIONALE_MIN_LEN = 40
MICRO_SURFACE_DISCONFIRMATION_MIN_LEN = 20

# § 7 of the proposal — Tier 1 telemetry isolation per operator decision
# (FM-B rationale-rot tracking + EU AI Act primary-audit-trail
# decontamination). Tier 1 outcomes write here; the existing
# ~/.episteme/telemetry/YYYY-MM-DD-audit.jsonl remains the primary audit
# trail for Tier 2/3 ops.
TIER1_TELEMETRY_PATH = Path.home() / ".episteme" / "telemetry" / "tier1.jsonl"


class Tier(enum.Enum):
    """The three-tier classification of irreversible Bash/Write ops."""

    ONE = "tier_1"
    TWO = "tier_2"
    THREE = "tier_3"


@dataclass(frozen=True)
class GitContext:
    """Snapshot of git state needed to classify an op.

    `current_branch` may be `None` if HEAD is detached or git is not
    available; the classifier defaults to Tier 2 in that case (loss-averse).
    """

    current_branch: str | None
    protected_branches: frozenset[str]
    # Reserved for future profile-aware classification (e.g., dirty-tree
    # may escalate Tier 1 -> Tier 2 for write-class ops). Not used yet.
    is_dirty: bool = False


@dataclass(frozen=True)
class TierConfig:
    """Static feature toggles on individual Tier 1 allowlist entries.

    The operator-profile-aware override path is `OperatorProfile`, passed
    separately to `classify()`. This struct stays static so unit tests
    can pin specific Tier 1 features on/off without simulating a profile.
    """

    allowlist_prerelease_creates: bool = True


@dataclass(frozen=True)
class OperatorProfile:
    """Subset of the operator profile axes the classifier consults.

    Stage 0 (this event) defines the API surface only. Stage 2 will wire
    a loader that reads `core/memory/global/operator_profile.md` (or the
    derived `~/.episteme/derived_knobs.json`) and passes the resulting
    `OperatorProfile` to `classify()`. Until then, callers pass `None`
    and the classifier uses static loss-averse defaults.

    Per operator's Event 134.1 resolution: `risk_tolerance == 0` is the
    incident-response override that force-escalates every Tier 1
    classification to Tier 2 (Tier 3 denylist still applies — unchanged).
    Other axes are reserved for future stages.
    """

    risk_tolerance: int = 2  # matches the operator's current elicited value
    asymmetry_posture: str = "loss-averse"  # reserved — not consulted yet


@dataclass(frozen=True)
class ClassifierVerdict:
    """Output of `classify`. `tier` is the decision; `reason` is a short
    human-readable string the hook can include in stderr / telemetry."""

    tier: Tier
    reason: str
    # The pattern label that triggered the verdict — e.g., "git push" or
    # "git push --force to protected branch". Stable across versions for
    # telemetry aggregation.
    pattern: str = ""


@dataclass(frozen=True)
class MicroSurface:
    """The 2-field Tier 1 micro-surface schema, per proposal § 4 (revised
    Event 134.1 to bind the TTL to the target Git branch).

    Operator's branch-binding rationale: "a pure 5-minute temporal window
    introduces a context-bleeding vulnerability: if the operator writes a
    micro-surface for feature branch fix-coherence, an agent could
    theoretically execute a different irreversible operation within that
    5-minute window under the same token. The validator must assert that
    the current Git branch explicitly matches the branch target declared
    inside the micro-surface JSON."

    The `branch` field is the operator-stated binding. Any micro-surface
    whose `branch` does not equal `GitContext.current_branch` at op-execute
    time is rejected (validation returns False with a context-bleed
    reason), even if every other field passes — including the case where
    the surface is fresh and well-formed but the operator switched
    branches between authoring and execution.
    """

    tier: int
    branch: str
    rationale_one_line: str
    disconfirmation_one_line: str
    timestamp: str  # ISO-8601 UTC


def validate_micro_surface(
    surface: dict,
    git_context: GitContext,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """Validate a Tier 1 micro-surface dict against the operator-resolved
    schema. Returns (is_valid, reason).

    A False return means the surface does NOT qualify for the Tier 1
    dispatch path — the caller (Stage 2 hook wire-up) must fall through
    to the Tier 2 strict-block path. There is no advisory in-between;
    "almost-Tier-1" is treated as Tier 2 by design (loss-averse on
    micro-surface mis-fills).

    Checks (in evaluation order — each gate runs only if the prior passed):
    1. `tier` field equals 1 (rejects misuse against Tier 2/3 ops).
    2. `branch` field present and non-empty.
    3. `rationale_one_line` length >= MICRO_SURFACE_RATIONALE_MIN_LEN.
    4. `disconfirmation_one_line` length >=
       MICRO_SURFACE_DISCONFIRMATION_MIN_LEN.
    5. `timestamp` parses as ISO-8601 and is within
       MICRO_SURFACE_TTL_SECONDS of `now`.
    6. `branch` equals `git_context.current_branch` exactly. This is the
       Event 134.1 context-bleed counter — if the operator switched
       branches between authoring and execution, the surface is invalid
       on this op regardless of TTL freshness.
    """
    if not isinstance(surface, dict):
        return False, "micro-surface is not a dict"

    tier_field = surface.get("tier")
    if tier_field != 1:
        return False, (
            f"micro-surface tier field must equal 1 (got {tier_field!r}); "
            "Tier 2/3 ops must use the full Reasoning Surface"
        )

    branch = surface.get("branch")
    if not isinstance(branch, str) or not branch.strip():
        return False, "micro-surface branch field is missing or empty"
    branch = branch.strip()

    rationale = surface.get("rationale_one_line", "")
    if not isinstance(rationale, str):
        return False, "rationale_one_line must be a string"
    if len(rationale.strip()) < MICRO_SURFACE_RATIONALE_MIN_LEN:
        return False, (
            f"rationale_one_line below minimum length "
            f"({len(rationale.strip())} < "
            f"{MICRO_SURFACE_RATIONALE_MIN_LEN}); must name both bounded "
            f"blast radius AND concrete rollback path"
        )

    disconfirm = surface.get("disconfirmation_one_line", "")
    if not isinstance(disconfirm, str):
        return False, "disconfirmation_one_line must be a string"
    if len(disconfirm.strip()) < MICRO_SURFACE_DISCONFIRMATION_MIN_LEN:
        return False, (
            f"disconfirmation_one_line below minimum length "
            f"({len(disconfirm.strip())} < "
            f"{MICRO_SURFACE_DISCONFIRMATION_MIN_LEN}); must name a "
            f"specific observable outcome"
        )

    ts_field = surface.get("timestamp", "")
    if not isinstance(ts_field, str) or not ts_field.strip():
        return False, "timestamp field is missing or empty"
    try:
        # `fromisoformat` in Python 3.11+ handles the trailing-Z form; we
        # accept both `...Z` and explicit `+00:00` offsets.
        ts = datetime.fromisoformat(ts_field.replace("Z", "+00:00"))
    except ValueError:
        return False, f"timestamp does not parse as ISO-8601: {ts_field!r}"
    if ts.tzinfo is None:
        # No timezone info — interpret as UTC per the schema. Stage 2
        # hook callers should always emit `Z` or explicit offset; this
        # branch is a robustness fallback.
        ts = ts.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    age_seconds = (now - ts).total_seconds()
    if age_seconds < 0:
        return False, (
            f"timestamp is in the future ({-age_seconds:.0f}s ahead); "
            f"clock skew or fabricated surface"
        )
    if age_seconds > MICRO_SURFACE_TTL_SECONDS:
        return False, (
            f"micro-surface is stale ({age_seconds:.0f}s > "
            f"{MICRO_SURFACE_TTL_SECONDS}s TTL); rewrite a fresh surface"
        )

    if branch != git_context.current_branch:
        return False, (
            f"branch-binding mismatch: surface declared branch "
            f"{branch!r} but current branch is "
            f"{git_context.current_branch!r}; context-bleed prevention "
            f"per Event 134.1"
        )

    return True, "ok"


# ---------------------------------------------------------------------------
# Normalization — mirrors `core/hooks/reasoning_surface_guard.py:208` so
# bypass shapes route through the same classification.
# ---------------------------------------------------------------------------

_NORMALIZE_SEPARATORS = re.compile(r"[,'\"\[\]\(\)\{\}`]")


def normalize_command(text: str) -> str:
    """Apply the same separator-normalization the live hook uses.

    Bypass shapes like ``subprocess.run(['git','push'])``,
    ``os.system("git push")``, and ``` `git push` ``` all collapse to a
    shape where the embedded command tokens are separated by whitespace.
    """
    return _NORMALIZE_SEPARATORS.sub(" ", text)


# ---------------------------------------------------------------------------
# Tier 3 — denylist (negative system, hard reject).
# ---------------------------------------------------------------------------

# Each entry: (compiled_pattern, label, requires_protected_target).
# `requires_protected_target=True` means the pattern is Tier 3 only when
# the target argument is a protected branch. `False` means always Tier 3.
_TIER_3_PATTERNS: tuple[tuple[re.Pattern[str], str, bool], ...] = (
    # History rewrite on shared branches.
    (re.compile(r"\bgit\s+push\s+(?:.*\s)?(?:--force|--force-with-lease|-f)\b"),
     "git push --force",
     True),
    (re.compile(r"\bgit\s+reset\s+--hard\b"),
     "git reset --hard",
     True),
    (re.compile(r"\bgit\s+branch\s+-D\b|\bgit\s+branch\s+-d\b"),
     "git branch -D",
     True),
    # History rewrite — no protected-branch qualifier; the intent is the
    # destruction.
    (re.compile(r"\bgit\s+filter-branch\b"), "git filter-branch", False),
    (re.compile(r"\bgit\s+filter-repo\b"), "git filter-repo", False),
    (re.compile(r"\bgit\s+rebase\s+--root\b"), "git rebase --root", False),
    # Destructive data ops.
    (re.compile(r"\bDROP\s+DATABASE\b", re.I), "SQL DROP DATABASE", False),
    (re.compile(r"\bDROP\s+SCHEMA\b", re.I), "SQL DROP SCHEMA", False),
    # Catastrophic shell.
    (re.compile(r"\brm\s+-rf\s+/(?:\s|$)"), "rm -rf /", False),
    (re.compile(r"\brm\s+-rf\s+~(?:\s|$)"), "rm -rf ~", False),
    (re.compile(r"\brm\s+-rf\s+\$HOME(?:\s|$)"), "rm -rf $HOME", False),
)


# ---------------------------------------------------------------------------
# Tier 1 — allowlist (positive system, bounded irreversible).
# ---------------------------------------------------------------------------

# Each entry: (compiled_pattern, label, predicate). `predicate` takes
# `(normalized_command, git_context, config)` and returns True if the
# op qualifies for Tier 1.

_GIT_PUSH = re.compile(
    r"\bgit\s+push\s+(?:-\S+\s+)*(?P<remote>[^\s-]\S*)"
    r"\s+(?:-\S+\s+)*(?P<branch>[^\s-]\S*)"
)
_GIT_PUSH_BARE = re.compile(r"\bgit\s+push\b")
_GH_RELEASE_CREATE = re.compile(r"\bgh\s+release\s+create\b")
_GH_RELEASE_PRERELEASE_FLAG = re.compile(r"\s--prerelease\b|\s-p\b")
_GH_ISSUE_PR_COMMENT = re.compile(
    r"\bgh\s+(?:issue\s+(?:create|comment|edit)|pr\s+(?:create|comment|edit))\b"
)
_DANGEROUS_FLAG = re.compile(r"\s(?:--force|--force-with-lease|-f|--no-verify)\b")


def _resolve_push_target(cmd: str, ctx: GitContext) -> str | None:
    """Return the effective target branch of a `git push` command, or None
    if it can't be resolved (detached HEAD, git unavailable, or the
    command doesn't actually contain `git push`).

    Handles: explicit `git push <remote> <branch>` (with intervening
    flags), `git push <remote> HEAD` (resolves to current_branch), and
    bare `git push` (resolves to current_branch). Strips `refs/heads/`
    prefix and `HEAD:` refspec form.
    """
    m = _GIT_PUSH.search(cmd)
    if m:
        target = m.group("branch").split(":")[-1]
        if target.startswith("refs/heads/"):
            target = target[len("refs/heads/"):]
        if target == "HEAD":
            return ctx.current_branch
        return target
    # Bare `git push` or `git push <remote>` — implicit current branch.
    if _GIT_PUSH_BARE.search(cmd):
        return ctx.current_branch
    return None


def _tier1_git_push(cmd: str, ctx: GitContext, cfg: TierConfig) -> bool:
    """`git push` qualifies for Tier 1 iff: target branch is not in the
    protected list AND no dangerous flags are present."""
    if _DANGEROUS_FLAG.search(cmd):
        return False
    target = _resolve_push_target(cmd, ctx)
    if target is None:
        # Detached HEAD or unresolvable — loss-averse: not Tier 1.
        return False
    return target not in ctx.protected_branches


def _tier1_gh_release(cmd: str, ctx: GitContext, cfg: TierConfig) -> bool:
    """`gh release create` is Tier 1 iff `--prerelease` is present and the
    operator config allows prerelease-as-Tier-1."""
    if not cfg.allowlist_prerelease_creates:
        return False
    return bool(_GH_RELEASE_PRERELEASE_FLAG.search(cmd))


def _tier1_gh_issue_pr_comment(cmd: str, ctx: GitContext, cfg: TierConfig) -> bool:
    """`gh issue/pr create/comment/edit` is Tier 1 — reversible by edit/delete,
    no destructive effect on shared state."""
    return True


_Tier1Predicate = Callable[[str, GitContext, TierConfig], bool]

# Operator Event 134.1 resolution: pip install was REMOVED from the Tier 1
# allowlist. Rationale (operator quote): "supply-chain attacks
# (typosquatting, malicious setup.py/macro execution during the
# installation phase) are highly sophisticated. Running a raw pip install
# allows arbitrary code execution on the local host before any code is
# run. While it is technically revertible via pip uninstall, its
# immediate execution blast radius is not strictly bounded if the
# malicious package attempts to exfiltrate environment variables or keys
# from disk." pip install matches Tier 2 fallback below.
_TIER_1_PATTERNS: tuple[tuple[re.Pattern[str], str, _Tier1Predicate], ...] = (
    (_GIT_PUSH_BARE, "git push (non-protected branch)", _tier1_git_push),
    (_GH_RELEASE_CREATE, "gh release create --prerelease", _tier1_gh_release),
    (_GH_ISSUE_PR_COMMENT, "gh issue/pr create/comment", _tier1_gh_issue_pr_comment),
)


# ---------------------------------------------------------------------------
# Tier 2 — the existing HIGH_IMPACT_BASH set minus anything Tier 1
# qualifies. We don't enumerate it here; classify() returns Tier 2 by
# default for anything matching the live hook's HIGH_IMPACT_BASH set that
# Tier 1 / Tier 3 didn't claim.
# ---------------------------------------------------------------------------

# The live hook's high-impact patterns — duplicated here so the classifier
# works as a standalone. Kept in sync manually until Stage 4 merges this
# into the hook.
_TIER_2_FALLBACK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bgit\s+push\b"), "git push"),
    (re.compile(r"\bgit\s+merge\b(?!\s+--abort)"), "git merge"),
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
    (re.compile(r"\bDROP\s+TABLE\b", re.I), "SQL DROP TABLE"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.I), "SQL TRUNCATE TABLE"),
    (re.compile(r"\bgh\s+pr\s+merge\b"), "gh pr merge"),
    (re.compile(r"\bgh\s+release\s+create\b"), "gh release create"),
)


# ---------------------------------------------------------------------------
# Config loaders.
# ---------------------------------------------------------------------------

_DEFAULT_PROTECTED_BRANCHES = frozenset({"main", "master"})


def load_protected_branches(
    project_root: Path | None = None,
) -> frozenset[str]:
    """Load `.episteme/protected_branches.json` from project_root. Returns
    the default {"main", "master"} if the file is missing or malformed."""
    if project_root is None:
        project_root = Path.cwd()
    config_path = project_root / ".episteme" / "protected_branches.json"
    if not config_path.is_file():
        return _DEFAULT_PROTECTED_BRANCHES
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return _DEFAULT_PROTECTED_BRANCHES
        branches = {str(b).strip() for b in data if str(b).strip()}
        if not branches:
            return _DEFAULT_PROTECTED_BRANCHES
        return frozenset(branches)
    except (OSError, json.JSONDecodeError):
        return _DEFAULT_PROTECTED_BRANCHES


def load_git_context(
    project_root: Path | None = None,
) -> GitContext:
    """Snapshot the current git branch + protected list. Returns a context
    with `current_branch=None` if git is unavailable or HEAD is detached —
    safe-fail to Tier 2 in the classifier."""
    if project_root is None:
        project_root = Path.cwd()
    current_branch: str | None = None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            # `HEAD` literal means detached state — treat as unknown.
            if branch and branch != "HEAD":
                current_branch = branch
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return GitContext(
        current_branch=current_branch,
        protected_branches=load_protected_branches(project_root),
    )


# ---------------------------------------------------------------------------
# Event 135 — Stage 2 OperatorProfile disk-loader.
# ---------------------------------------------------------------------------


_DERIVED_KNOBS_PATH = Path.home() / ".episteme" / "derived_knobs.json"
_OPERATOR_PROFILE_MD = (
    Path.home() / "episteme" / "core" / "memory" / "global" / "operator_profile.md"
)


def load_operator_profile() -> OperatorProfile | None:
    """Read the operator's runtime profile from disk.

    Resolution order:
    1. `~/.episteme/derived_knobs.json` — preferred path; written by the
       `episteme sync` adapter from the source-of-truth markdown profile.
       Expected fields: `risk_tolerance` (int), `asymmetry_posture` (str).
    2. `~/episteme/core/memory/global/operator_profile.md` — parse-fallback
       extracting `risk_tolerance: <int>` and `asymmetry_posture: <str>`
       lines from the YAML-shaped axis blocks.

    Returns `None` when neither source is readable. The classifier treats
    a None profile as "use static loss-averse defaults" — no behavior
    change vs the Event 134.1 default. The hook's Stage 2 wire-up passes
    whatever this function returns directly to `classify()`.

    The fallback parser is intentionally minimal — it does not need to
    understand the full schema, only the two axes the classifier
    consults. Richer reads are deferred to Stage 4+.
    """
    profile = _load_operator_profile_from_derived_knobs()
    if profile is not None:
        return profile
    return _load_operator_profile_from_markdown()


def _load_operator_profile_from_derived_knobs() -> OperatorProfile | None:
    if not _DERIVED_KNOBS_PATH.is_file():
        return None
    try:
        with open(_DERIVED_KNOBS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    risk_tolerance = data.get("risk_tolerance")
    asymmetry_posture = data.get("asymmetry_posture")
    if not isinstance(risk_tolerance, int):
        return None
    if not isinstance(asymmetry_posture, str) or not asymmetry_posture.strip():
        asymmetry_posture = "loss-averse"
    return OperatorProfile(
        risk_tolerance=risk_tolerance,
        asymmetry_posture=asymmetry_posture.strip(),
    )


# Pattern matches `  value: 2` after a `risk_tolerance:` axis header.
# The operator profile schema (kernel/OPERATOR_PROFILE_SCHEMA.md) puts
# axes in YAML-shaped blocks where the first line is the axis name and
# subsequent indented lines carry `value:`, `confidence:`, etc.
_AXIS_VALUE_RE = re.compile(
    r"^\s*value:\s*(?P<value>[^\s#]+)", re.MULTILINE
)


def _load_operator_profile_from_markdown() -> OperatorProfile | None:
    if not _OPERATOR_PROFILE_MD.is_file():
        return None
    try:
        text = _OPERATOR_PROFILE_MD.read_text(encoding="utf-8")
    except OSError:
        return None

    risk_tolerance = _extract_axis_int(text, "risk_tolerance")
    asymmetry_posture = _extract_axis_str(text, "asymmetry_posture")
    if risk_tolerance is None:
        return None
    return OperatorProfile(
        risk_tolerance=risk_tolerance,
        asymmetry_posture=asymmetry_posture or "loss-averse",
    )


def _extract_axis_int(text: str, axis_name: str) -> int | None:
    """Extract `value: N` from the named axis block. Returns None if the
    axis isn't found or value isn't parseable as int."""
    block = _extract_axis_block(text, axis_name)
    if block is None:
        return None
    m = _AXIS_VALUE_RE.search(block)
    if m is None:
        return None
    try:
        return int(m.group("value"))
    except ValueError:
        return None


def _extract_axis_str(text: str, axis_name: str) -> str | None:
    block = _extract_axis_block(text, axis_name)
    if block is None:
        return None
    m = _AXIS_VALUE_RE.search(block)
    if m is None:
        return None
    return m.group("value").strip()


def _extract_axis_block(text: str, axis_name: str) -> str | None:
    """Find the axis header line `<axis_name>:` and return the indented
    block that follows (up to the next non-indented line or EOF)."""
    lines = text.splitlines()
    start: int | None = None
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{axis_name}:"):
            start = i
            break
    if start is None:
        return None
    end = start + 1
    while end < len(lines) and (
        lines[end].startswith((" ", "\t")) or lines[end].strip() == ""
    ):
        end += 1
    return "\n".join(lines[start:end])


# ---------------------------------------------------------------------------
# Event 135 — Stage 3 soak gate + telemetry writer.
# ---------------------------------------------------------------------------


def write_tier1_record(
    record: dict,
    path: Path | None = None,
) -> None:
    """Append a Tier 1 telemetry record to `TIER1_TELEMETRY_PATH` (or the
    explicit `path` for testing). Creates the parent directory if missing.

    The PostToolUse hook calls this with a record carrying at minimum:

        {
          "correlation_id": "<uuid>",
          "timestamp": "<ISO-8601 UTC>",
          "pattern": "<classifier pattern label>",
          "branch": "<git current branch>",
          "rationale_one_line": "<from the micro-surface>",
          "exit_code": <int from PostToolUse>,
          "operator_confirmed": <bool>,
          "subsequent_revert_within_24h": <bool — set by an async audit pass>
        }

    `subsequent_revert_within_24h` is left None at write-time and filled
    by the audit pass (`episteme tier1 audit`) that scans git history for
    a revert touching the same blast radius within 24h. The audit pass
    is the calibration loop's correction step.
    """
    target = path or TIER1_TELEMETRY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def soak_gate_open(
    now: datetime | None = None,
    path: Path | None = None,
) -> tuple[bool, str]:
    """Return `(is_open, reason)` for the Tier 1 advisory soak gate.

    The gate opens — i.e., the live hook may dispatch Tier 1 ops through
    the advisory path instead of strict-block — only when ALL three
    proposal § 7 conditions hold against the telemetry trail at
    `TIER1_TELEMETRY_PATH`:

    1. **Calendar span:** the earliest record is at least
       `SOAK_GATE_MIN_DAYS` calendar days before `now`.
    2. **Volume:** at least `SOAK_GATE_MIN_OPS` records exist.
    3. **Rationale-accuracy rate:** of records where both
       `operator_confirmed` is True AND
       `subsequent_revert_within_24h` is False, the fraction is
       ≥ `SOAK_GATE_MIN_RATIONALE_ACCURACY`.

    A FAIL on any condition returns `(False, "<specific reason>")` so the
    hook's stderr advisory can name what's missing. New installations
    (empty or absent telemetry file) start with the gate CLOSED — this
    is the loss-averse default the Event 135 split preserves: the code
    lands now, but runtime behavior change waits on lived evidence.

    Returns `(True, "soak passed: ...")` only when every condition holds.
    """
    target = path or TIER1_TELEMETRY_PATH
    now = now or datetime.now(timezone.utc)

    if not target.is_file():
        return False, (
            f"soak gate CLOSED: no telemetry at {target} — gate opens "
            f"after {SOAK_GATE_MIN_OPS} Tier 1 ops across "
            f"{SOAK_GATE_MIN_DAYS}+ days"
        )

    records: list[dict] = []
    try:
        with open(target, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    # Corrupt line — skip rather than fail the gate
                    # (loss-averse: the gate stays closed if the data is
                    # noisy; one bad line shouldn't crash the audit).
                    continue
    except OSError as exc:
        return False, f"soak gate CLOSED: telemetry read error: {exc}"

    if len(records) < SOAK_GATE_MIN_OPS:
        return False, (
            f"soak gate CLOSED: {len(records)} records "
            f"< {SOAK_GATE_MIN_OPS} required"
        )

    earliest_ts: datetime | None = None
    for r in records:
        ts_str = r.get("timestamp", "")
        if not isinstance(ts_str, str):
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if earliest_ts is None or ts < earliest_ts:
            earliest_ts = ts
    if earliest_ts is None:
        return False, "soak gate CLOSED: no parseable timestamps in telemetry"
    span_days = (now - earliest_ts).total_seconds() / 86400.0
    if span_days < SOAK_GATE_MIN_DAYS:
        return False, (
            f"soak gate CLOSED: span {span_days:.1f}d "
            f"< {SOAK_GATE_MIN_DAYS}d required"
        )

    confirmed = [r for r in records if r.get("operator_confirmed") is True]
    if not confirmed:
        return False, (
            "soak gate CLOSED: zero operator-confirmed records (rationale-"
            "accuracy rate undefined)"
        )
    clean = [
        r for r in confirmed
        if r.get("subsequent_revert_within_24h") is False
    ]
    accuracy = len(clean) / len(confirmed)
    if accuracy < SOAK_GATE_MIN_RATIONALE_ACCURACY:
        return False, (
            f"soak gate CLOSED: rationale-accuracy {accuracy:.2%} "
            f"< {SOAK_GATE_MIN_RATIONALE_ACCURACY:.0%} required "
            f"({len(clean)}/{len(confirmed)} confirmed ops survived 24h "
            f"without revert)"
        )

    return True, (
        f"soak gate OPEN: {len(records)} records, span {span_days:.1f}d, "
        f"rationale-accuracy {accuracy:.2%}"
    )


# ---------------------------------------------------------------------------
# The classifier.
# ---------------------------------------------------------------------------


def classify(
    tool_name: str,
    tool_args: dict,
    git_context: GitContext,
    config: TierConfig | None = None,
    operator_profile: OperatorProfile | None = None,
) -> ClassifierVerdict:
    """Classify a proposed tool call into Tier 1 / 2 / 3.

    Order of evaluation (intentional — loss-averse precedence):

    1. **Tier 3 (denylist).** Hard reject regardless of surface. Highest
       priority — if an op matches Tier 3 it cannot fall through to a
       lower-friction tier.
    2. **Tier 1 (allowlist).** Bounded irreversible — micro-surface +
       operator confirm. Each pattern's predicate is consulted; predicate
       returning True is required. **Operator-profile override** (Event
       134.1): when `operator_profile.risk_tolerance == 0` (incident-
       response posture), every Tier 1 hit is force-escalated to Tier 2.
       Tier 3 still applies — the override never relaxes safety, only
       tightens it.
    3. **Tier 2 (default).** Any op that matches the hook's existing
       HIGH_IMPACT_BASH set but didn't qualify for Tier 1 / 3. This
       preserves the current strict-block behavior for everything not
       explicitly relaxed.

    Returns ``ClassifierVerdict(Tier.TWO, ...)`` for ops that don't match
    any pattern in either direction — the safe default. Callers that want
    to know whether the op matched the high-impact set at all can inspect
    the verdict's `pattern` field (empty when no pattern matched).
    """
    cfg = config or TierConfig()
    force_tier_2_on_tier_1 = (
        operator_profile is not None and operator_profile.risk_tolerance == 0
    )
    cmd_text = _extract_command_text(tool_name, tool_args)
    if not cmd_text:
        # Non-Bash / non-Write tool or empty command — not classifiable
        # against this set. Treat as out-of-scope (Tier 2 default).
        return ClassifierVerdict(Tier.TWO, "no command text to classify", "")
    normalized = normalize_command(cmd_text)

    # Tier 3 — denylist takes precedence. Operator profile cannot relax
    # this; it can only further tighten the Tier 1 path (which is exactly
    # what `force_tier_2_on_tier_1` does below).
    for pattern, label, requires_protected in _TIER_3_PATTERNS:
        if not pattern.search(normalized):
            continue
        if requires_protected:
            if _targets_protected_branch(normalized, git_context):
                return ClassifierVerdict(
                    Tier.THREE,
                    f"Tier 3 — {label} against protected branch",
                    label,
                )
            # The op matched the dangerous pattern but didn't target a
            # protected branch. Still suspicious — Tier 2 (require full
            # Reasoning Surface) rather than Tier 1.
            return ClassifierVerdict(
                Tier.TWO,
                f"Tier 2 — {label} on non-protected branch (still requires full surface)",
                label,
            )
        return ClassifierVerdict(Tier.THREE, f"Tier 3 — {label}", label)

    # Tier 1 — allowlist (positive system).
    for pattern, label, predicate in _TIER_1_PATTERNS:
        if not pattern.search(normalized):
            continue
        if predicate(normalized, git_context, cfg):
            if force_tier_2_on_tier_1:
                # Operator profile incident-response override (Event
                # 134.1). Preserve the original Tier-1-pattern label for
                # telemetry so the operator can see what WOULD have been
                # Tier 1 absent the override.
                return ClassifierVerdict(
                    Tier.TWO,
                    f"Tier 2 — {label} force-escalated by operator "
                    f"profile risk_tolerance=0 (incident-response posture)",
                    label,
                )
            return ClassifierVerdict(Tier.ONE, f"Tier 1 — {label}", label)
        # Pattern matched but predicate rejected — fall through to Tier 2
        # (the predicate's job is to refine, not to authorize a free pass).

    # Tier 2 — default for anything matching the hook's high-impact set.
    for pattern, label in _TIER_2_FALLBACK_PATTERNS:
        if pattern.search(normalized):
            return ClassifierVerdict(
                Tier.TWO,
                f"Tier 2 — {label} requires full Reasoning Surface",
                label,
            )

    # Not in the high-impact set at all — out of scope for this gate.
    return ClassifierVerdict(Tier.TWO, "not in high-impact set", "")


# ---------------------------------------------------------------------------
# Internal helpers.
# ---------------------------------------------------------------------------


def _extract_command_text(tool_name: str, tool_args: dict) -> str:
    """Pull the text that should be matched against the patterns.

    - For `Bash` tool calls: the `command` field.
    - For `Write` / `Edit`: a synthesized "write <file_path>" line so
      lockfile mutations can be detected. (Reserved — current patterns
      don't match Write/Edit yet; Stage 2 will extend.)
    """
    if tool_name == "Bash":
        return str(tool_args.get("command", ""))
    if tool_name in ("Write", "Edit", "MultiEdit"):
        path = str(tool_args.get("file_path", ""))
        return f"write {path}" if path else ""
    return ""


def _targets_protected_branch(
    normalized_cmd: str, ctx: GitContext
) -> bool:
    """Heuristic: does the normalized command target a protected branch?

    For `git push`, defers to `_resolve_push_target`. For `git reset
    --hard` and `git branch -D/-d`, the op operates on the current branch
    unless a ref is named — we err loss-averse and treat ambiguous cases
    as protected to escalate.
    """
    target = _resolve_push_target(normalized_cmd, ctx)
    if target is not None:
        return target in ctx.protected_branches
    if (
        "reset" in normalized_cmd
        or "branch -D" in normalized_cmd
        or "branch -d" in normalized_cmd
    ):
        if ctx.current_branch is None:
            return True
        return ctx.current_branch in ctx.protected_branches
    return False
