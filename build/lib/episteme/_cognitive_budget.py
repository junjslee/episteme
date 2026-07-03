"""Operator cognitive-budget approval-time history — Cognitive Arm A
companion stream (CP-OPERATOR-COGNITIVE-BUDGET-01 first slice; Event 88).

Append-only hash-chained record of operator approval-time observations.
Lives at ``~/.episteme/memory/reflective/approval_times.jsonl`` and uses
the existing CP7 ``cp7-chained-v1`` envelope schema (see
``core/hooks/_chain.py``).

## Why this exists

The kernel imposes cognitive load on its operator: every Reasoning
Surface declaration takes time, every cascade-class op requires
attention, every audit alert requires a decision. D11 (Operator Fatigue
Guardrails) was named in the v1.1 spec but had no executable carrier
until this Event. CP-OPERATOR-COGNITIVE-BUDGET-01 §4 calls out
distinguishing **cost-exceeded-benefit** from **discipline-failure**;
they look identical to the audit today (both register as drift). This
module ships the substrate that lets a future audit tell them apart.

The mechanism: every recorded approval entry pairs a
``correlation_id`` with the ``elapsed_seconds`` between blueprint
advisory and op completion plus a ``blueprint`` tag and a ``reason``
note. ``detect_fatigue`` walks the rolling window and flags
``attention_bottleneck`` when sub-second-approval rate exceeds the
configured threshold — the structured signal that means *operator
fatigue suspected, this isn't necessarily discipline-failure*.

## Schema

Single payload type:

```
{"type": "approval_record",
 "correlation_id": "<hook-correlation-id or operator-supplied tag>",
 "blueprint": "<one of A/B/C/D/fallback or 'unknown'>",
 "op_class": "<bash|edit|cascade|other>",
 "elapsed_seconds": <float ≥ 0>,
 "reason": "<≥15 chars, no lazy tokens>",
 "recorded_at": "<ISO-8601 UTC>",
 "recorder": "<operator-id>"}
```

## Validation discipline

- ``blueprint`` must be one of the declared blueprint slugs (or
  ``unknown`` / ``fallback``).
- ``op_class`` must be one of {bash, edit, cascade, other}.
- ``elapsed_seconds`` must be a non-negative number.
- ``reason`` must be ≥ 15 chars + must NOT match the lazy-token list
  (mirrors Reasoning Surface validator + ``_profile_history`` discipline).

## Auto-instrumentation status

This module ships the API + CLI for **manual** approval-time recording.
**Auto-instrumentation** of approval-time capture (PreToolUse marker +
PostToolUse computation + register-with-Claude-Code per Event 38) is
deferred to a follow-up Event. Operators use the
``episteme cognitive-budget --record`` CLI to log observations until then.

Spec: ``~/episteme-private/docs/cp-v1.1-architectural.md``
§ CP-OPERATOR-COGNITIVE-BUDGET-01.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Locate core/hooks/_chain.py — same lazy-import pattern other src/episteme/
# library modules use for hook-tier modules.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CORE_HOOKS_DIR = _REPO_ROOT / "core" / "hooks"
if str(_CORE_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_CORE_HOOKS_DIR))

import _chain  # type: ignore  # pyright: ignore[reportMissingImports]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


DEFAULT_REFLECTIVE_DIR = Path.home() / ".episteme" / "memory" / "reflective"
HISTORY_FILENAME = "approval_times.jsonl"


# Fixed enum for the blueprint slug carried in each record. Mirrors the
# Pillar 1 named-blueprints set with `unknown` (no blueprint matched) and
# `fallback` (Goodhart-closer max-rigor fallback fired). Strings, not
# objects — operator may record manually without importing anything.
VALID_BLUEPRINTS: frozenset[str] = frozenset({
    "axiomatic_judgment",      # Blueprint A
    "fence_reconstruction",    # Blueprint B
    "consequence_chain",       # Blueprint C
    "cascade_escalation",      # Blueprint D
    "fallback",                # Goodhart-closer max-rigor fallback
    "unknown",
})


VALID_OP_CLASSES: frozenset[str] = frozenset({
    "bash",
    "edit",
    "cascade",
    "other",
})


# Mirrors `_profile_history.py:LAZY_REASON_TOKENS`. Reasoning Surface
# validator's lazy-token discipline applied to the reason field.
LAZY_REASON_TOKENS: frozenset[str] = frozenset({
    # English shortforms
    "n/a", "na", "tbd", "todo",
    "none", "nothing", "nil", "null",
    "ack", "acked", "acknowledged",
    "ok", "okay", "fine",
    "later", "fix later", "do later", "address later",
    "wip", "in progress",
    # Korean equivalents
    "해당 없음", "없음", "없다", "추후", "나중에",
})

MIN_REASON_CHARS = 15


# Defaults for fatigue detection. The threshold values are conservative
# and tunable per-project via `<cwd>/.episteme/cognitive_budget_thresholds`
# (single line `p50=<float>,sub_second_rate=<float>,window=<int>`).
# Going with p50 < 1.5s and sub-second-rate > 0.5 across last 20 records
# as the qualitative anchor from v1.1 Event 56 ("sub-second approval
# times flag as attention_bottleneck drift signal").
DEFAULT_WINDOW = 20
DEFAULT_P50_THRESHOLD_SECONDS = 1.5
DEFAULT_SUB_SECOND_RATE_THRESHOLD = 0.5


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_blueprint(blueprint) -> None:
    if not isinstance(blueprint, str):
        raise ValueError("blueprint must be a string")
    stripped = blueprint.strip()
    if not stripped:
        raise ValueError("blueprint must be a non-empty string")
    if stripped not in VALID_BLUEPRINTS:
        raise ValueError(
            f"unknown blueprint {blueprint!r}. Must be one of "
            f"{sorted(VALID_BLUEPRINTS)}."
        )


def validate_op_class(op_class) -> None:
    if not isinstance(op_class, str):
        raise ValueError("op_class must be a string")
    stripped = op_class.strip()
    if not stripped:
        raise ValueError("op_class must be a non-empty string")
    if stripped not in VALID_OP_CLASSES:
        raise ValueError(
            f"unknown op_class {op_class!r}. Must be one of "
            f"{sorted(VALID_OP_CLASSES)}."
        )


def validate_elapsed_seconds(value) -> None:
    if isinstance(value, bool):
        raise ValueError("elapsed_seconds must be a number, not bool")
    if not isinstance(value, (int, float)):
        raise ValueError("elapsed_seconds must be a number")
    if value < 0:
        raise ValueError("elapsed_seconds must be non-negative")


def validate_correlation_id(value) -> None:
    if not isinstance(value, str):
        raise ValueError("correlation_id must be a string")
    if not value.strip():
        raise ValueError("correlation_id must be a non-empty string")


def validate_reason(text) -> None:
    """Lazy-token + min-char rejection. Mirrors `_profile_history.py:
    validate_reason` — a reason without substance defeats the
    purpose of the trajectory record."""
    if not isinstance(text, str):
        raise ValueError("reason must be a string")
    stripped = text.strip()
    lowered = stripped.lower()
    for token in LAZY_REASON_TOKENS:
        if lowered == token.lower():
            raise ValueError(
                f"reason matches lazy-token {token!r}. "
                f"Provide a substantive reason — what made this approval "
                f"observation worth recording?"
            )
    if len(stripped) < MIN_REASON_CHARS:
        raise ValueError(
            f"reason must be at least {MIN_REASON_CHARS} characters; "
            f"got {len(stripped)}. Empty / placeholder reasons rejected."
        )


# ---------------------------------------------------------------------------
# Recorder identity resolution (same pattern as _profile_history.py)
# ---------------------------------------------------------------------------


def _resolve_recorder() -> str:
    explicit = os.environ.get("EPISTEME_RECORDER", "").strip()
    if explicit:
        return explicit
    user = os.environ.get("USER", "").strip()
    if user:
        return user
    try:
        result = subprocess.run(
            ["git", "config", "--get", "user.name"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _resolve_path(reflective_dir: Path | None = None) -> Path:
    base = reflective_dir or DEFAULT_REFLECTIVE_DIR
    return base / HISTORY_FILENAME


# ---------------------------------------------------------------------------
# Threshold override (per-project)
# ---------------------------------------------------------------------------


def load_thresholds(cwd: Path) -> tuple[int, float, float]:
    """Read ``<cwd>/.episteme/cognitive_budget_thresholds`` for per-project
    overrides. Format: ``key=value`` lines, keys
    ``window`` / ``p50`` / ``sub_second_rate``. Falls back silently to
    defaults on missing / malformed file. Mirrors the override pattern
    used by ``_guidance.py:load_min_overlap``.
    """
    window = DEFAULT_WINDOW
    p50 = DEFAULT_P50_THRESHOLD_SECONDS
    rate = DEFAULT_SUB_SECOND_RATE_THRESHOLD
    path = cwd / ".episteme" / "cognitive_budget_thresholds"
    if not path.is_file():
        return (window, p50, rate)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return (window, p50, rate)
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip().lower()
        v = v.strip()
        try:
            if k == "window":
                window = max(1, int(v))
            elif k == "p50":
                p50 = max(0.0, float(v))
            elif k in ("sub_second_rate", "rate"):
                rate = max(0.0, min(1.0, float(v)))
        except (ValueError, TypeError):
            continue
    return (window, p50, rate)


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


def record_approval(
    correlation_id: str,
    blueprint: str,
    op_class: str,
    elapsed_seconds: float,
    reason: str,
    *,
    recorder: str | None = None,
    reflective_dir: Path | None = None,
    _now: datetime | None = None,  # test seam
) -> dict:
    """Append an ``approval_record`` envelope to the history stream
    and return the full chain envelope.

    Raises ValueError on invalid blueprint (must be in VALID_BLUEPRINTS),
    invalid op_class (must be in VALID_OP_CLASSES), invalid
    elapsed_seconds (must be ≥ 0), or invalid reason (lazy-token /
    too-short).
    """
    validate_correlation_id(correlation_id)
    validate_blueprint(blueprint)
    validate_op_class(op_class)
    validate_elapsed_seconds(elapsed_seconds)
    validate_reason(reason)
    now = _now or datetime.now(timezone.utc)

    payload = {
        "type": "approval_record",
        "correlation_id": correlation_id.strip(),
        "blueprint": blueprint.strip(),
        "op_class": op_class.strip(),
        "elapsed_seconds": float(elapsed_seconds),
        "reason": reason.strip(),
        "recorded_at": now.isoformat(),
        "recorder": recorder or _resolve_recorder(),
    }
    return _chain.append(_resolve_path(reflective_dir), payload)


# ---------------------------------------------------------------------------
# Read paths
# ---------------------------------------------------------------------------


def walk_approvals(
    *,
    blueprint: str | None = None,
    op_class: str | None = None,
    limit: int | None = None,
    reflective_dir: Path | None = None,
) -> list[dict]:
    """Return approval envelopes in chronological (chain) order. Filters
    by ``blueprint`` / ``op_class`` if supplied. ``limit`` returns the
    last N (most recent) entries after filtering; pass None for all.

    Filters out non-`approval_record` payloads (defensive — the stream
    is single-payload-type by design, but the filter ensures forward-
    compat with future payload types).
    """
    if blueprint is not None:
        validate_blueprint(blueprint)
    if op_class is not None:
        validate_op_class(op_class)
    path = _resolve_path(reflective_dir)
    if not path.exists():
        return []

    entries: list[dict] = []
    for envelope in _chain.iter_records(path, verify=True):
        payload = envelope.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "approval_record":
            continue
        if blueprint is not None and payload.get("blueprint") != blueprint:
            continue
        if op_class is not None and payload.get("op_class") != op_class:
            continue
        entries.append(envelope)
    if limit is not None and limit > 0:
        return entries[-limit:]
    return entries


def list_blueprints_with_history(*, reflective_dir: Path | None = None) -> set[str]:
    """Return set of blueprint slugs that have at least one recorded
    approval observation."""
    path = _resolve_path(reflective_dir)
    if not path.exists():
        return set()
    blueprints: set[str] = set()
    for envelope in _chain.iter_records(path, verify=True):
        payload = envelope.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "approval_record":
            continue
        bp = payload.get("blueprint")
        if isinstance(bp, str):
            blueprints.add(bp)
    return blueprints


# ---------------------------------------------------------------------------
# Fatigue detection (D11 attention_bottleneck signal)
# ---------------------------------------------------------------------------


def detect_fatigue(
    *,
    window: int = DEFAULT_WINDOW,
    p50_threshold_seconds: float = DEFAULT_P50_THRESHOLD_SECONDS,
    sub_second_rate_threshold: float = DEFAULT_SUB_SECOND_RATE_THRESHOLD,
    reflective_dir: Path | None = None,
) -> dict | None:
    """Inspect the most recent ``window`` approval observations and
    return a fatigue signal if either:

    - rolling p50 elapsed_seconds is BELOW ``p50_threshold_seconds``, OR
    - rate of sub-second-elapsed approvals exceeds
      ``sub_second_rate_threshold``.

    Returns None when not enough observations OR neither threshold is
    crossed. Returns a dict ``{signal: "attention_bottleneck", window,
    p50, sub_second_rate, observed_at, sample_size}`` when fired.

    Both thresholds are evaluated independently — either alone fires
    the signal. p50 measures central tendency; sub-second-rate measures
    auto-approval shape. Together they cover both 'consistently fast'
    and 'occasional bursts of fast approvals'.

    The function is purely observational. Operator action on the signal
    (slow down, take a break, raise discipline ceiling, etc.) lives in
    the audit / advisory layer — explicitly NOT here. Per the v1.1
    bounded-autonomy posture: budget detection should never block.
    """
    if window < 1:
        raise ValueError("window must be ≥ 1")
    if p50_threshold_seconds < 0:
        raise ValueError("p50_threshold_seconds must be ≥ 0")
    if not 0.0 <= sub_second_rate_threshold <= 1.0:
        raise ValueError("sub_second_rate_threshold must be in [0, 1]")

    entries = walk_approvals(limit=window, reflective_dir=reflective_dir)
    if not entries:
        return None

    elapsed = [
        float(env["payload"]["elapsed_seconds"])
        for env in entries
        if isinstance(env.get("payload"), dict)
        and isinstance(env["payload"].get("elapsed_seconds"), (int, float))
    ]
    if not elapsed:
        return None

    sample_size = len(elapsed)
    sorted_e = sorted(elapsed)
    # Median (p50) — for even sample sizes, average the two middle values.
    mid = sample_size // 2
    if sample_size % 2 == 1:
        p50 = sorted_e[mid]
    else:
        p50 = (sorted_e[mid - 1] + sorted_e[mid]) / 2.0
    sub_second_count = sum(1 for v in elapsed if v < 1.0)
    sub_second_rate = sub_second_count / sample_size

    p50_fires = p50 < p50_threshold_seconds
    rate_fires = sub_second_rate > sub_second_rate_threshold
    if not (p50_fires or rate_fires):
        return None

    triggers = []
    if p50_fires:
        triggers.append("p50_below_threshold")
    if rate_fires:
        triggers.append("sub_second_rate_above_threshold")

    return {
        "signal": "attention_bottleneck",
        "window": window,
        "sample_size": sample_size,
        "p50": p50,
        "sub_second_rate": sub_second_rate,
        "p50_threshold_seconds": p50_threshold_seconds,
        "sub_second_rate_threshold": sub_second_rate_threshold,
        "triggers": triggers,
        "observed_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Summary stats (CLI helper)
# ---------------------------------------------------------------------------


def summarize(
    *,
    window: int | None = None,
    blueprint: str | None = None,
    reflective_dir: Path | None = None,
) -> dict:
    """Return a summary dict over the most-recent ``window`` observations
    (or all if window=None). Useful as a CLI surface — operator runs
    `episteme cognitive-budget --summary` and gets a concise readout.

    Shape: ``{count, p50, p95, mean, sub_second_rate, by_blueprint:
    {<bp>: count}, fatigue: <detect_fatigue result or None>}``.
    """
    entries = walk_approvals(
        blueprint=blueprint,
        limit=window,
        reflective_dir=reflective_dir,
    )
    if not entries:
        return {
            "count": 0,
            "p50": None,
            "p95": None,
            "mean": None,
            "sub_second_rate": None,
            "by_blueprint": {},
            "fatigue": None,
        }
    elapsed: list[float] = []
    by_bp: dict[str, int] = {}
    for env in entries:
        payload = env.get("payload", {})
        if not isinstance(payload, dict):
            continue
        e = payload.get("elapsed_seconds")
        if isinstance(e, (int, float)):
            elapsed.append(float(e))
        bp = payload.get("blueprint")
        if isinstance(bp, str):
            by_bp[bp] = by_bp.get(bp, 0) + 1
    if not elapsed:
        return {
            "count": len(entries),
            "p50": None,
            "p95": None,
            "mean": None,
            "sub_second_rate": None,
            "by_blueprint": by_bp,
            "fatigue": None,
        }
    sorted_e = sorted(elapsed)
    n = len(sorted_e)
    mid = n // 2
    if n % 2 == 1:
        p50 = sorted_e[mid]
    else:
        p50 = (sorted_e[mid - 1] + sorted_e[mid]) / 2.0
    p95_idx = max(0, min(n - 1, int(round(0.95 * (n - 1)))))
    p95 = sorted_e[p95_idx]
    mean = sum(sorted_e) / n
    sub_second_rate = sum(1 for v in sorted_e if v < 1.0) / n

    fatigue = detect_fatigue(
        window=window or DEFAULT_WINDOW,
        reflective_dir=reflective_dir,
    )
    return {
        "count": n,
        "p50": p50,
        "p95": p95,
        "mean": mean,
        "sub_second_rate": sub_second_rate,
        "by_blueprint": by_bp,
        "fatigue": fatigue,
    }


# ---------------------------------------------------------------------------
# Chain verification (delegates to _chain)
# ---------------------------------------------------------------------------


def verify_chain(reflective_dir: Path | None = None):
    """Return ``_chain.ChainVerdict`` for the approval_times stream.
    Used by ``episteme chain verify`` to integrate the budget stream
    into the Pillar 2 verification surface."""
    return _chain.verify_chain(_resolve_path(reflective_dir))
