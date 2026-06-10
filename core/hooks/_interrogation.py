"""Interrogation verdict artifact — v2.0 Epistemic Engine (Event 138).

The artifact at ``.episteme/interrogation.json`` is the structured residue
of the ``epistemic-interrogation`` skill: a decision decomposed into tiered
claims, load-bearing claims verified in a fresh context against external
evidence, an argued opposition, a weakest link, a pre-committed
disconfirmation, and a verdict. The PreToolUse gate accepts a fresh
``proceed`` / ``proceed-with-revision`` verdict as an alternative satisfier
to the v1 Reasoning Surface for high-impact ops.

Division of labor (DESIGN_V2_0 § 4): this module checks ONLY what
determinism can check — freshness, structural floors, verdict consistency.
Substance is the model's job at interrogation time and the spot-check
loop's job after. The floors here are floors, not quality claims; they
exist to make the cheapest gaming shapes (empty fields, lazy tokens,
self-contradicting verdicts) fail closed.

Freshness uses ``max(content timestamp, file mtime)`` — the mtime rescues
stale-at-birth artifacts where an agent guessed wall-clock wrong, while a
genuinely old artifact (old ts AND old mtime) stays stale. Touching the
file to refresh it is equivalent in power to rewriting the ts, so mtime
admits no new gaming shape.

Lesson synthesis (``maybe_synthesize_lesson``, called from the PostToolUse
hook): a successful op whose fresh verdict carries a non-null ``lesson``
emits a hash-chained protocol via CP7's ``_framework.write_protocol``,
deduplicated by lesson content hash. Signature shape: ``blueprint`` is the
``"generic"`` plane and ``constraint_head`` stays None so the lesson
resurfaces for any high-impact op in the same project (overlap >= 4 of 6);
``op_class`` carries the synthesizing op's head for specificity ranking.

Spec: ``docs/DESIGN_V2_0_EPISTEMIC_ENGINE.md`` §§ 6-8.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


INTERROGATION_TTL_SECONDS = 30 * 60

VERDICT_VALUES = frozenset({"proceed", "proceed-with-revision", "stop"})
CLAIM_TIERS = frozenset({"measured", "cited", "inferred", "assumed"})
VERIFICATION_METHODS = frozenset({"file-read", "execution", "search", "none"})
EXTERNAL_METHODS = frozenset({"file-read", "execution", "search"})
VERIFICATION_RESULTS = frozenset({"supported", "refuted", "unverifiable"})

_MIN_DECISION_LEN = 10
_MIN_CLAIM_LEN = 15
_MIN_EVIDENCE_LEN = 20
_MIN_OPPOSITION_LEN = 60
_MIN_WEAKEST_LINK_LEN = 30
_MIN_DISCONFIRMATION_LEN = 20
_MIN_LESSON_FIELD_LEN = 10

# Same lazy-token family as the surface validator — duplicated per the
# hooks-stay-self-contained convention.
_LAZY_TOKENS = frozenset({
    "none", "null", "nil", "nothing", "undefined",
    "n/a", "na", "n.a.", "n.a", "not applicable",
    "tbd", "todo", "to be determined", "to be decided",
    "unknown", "idk", "i don't know", "no idea",
    "해당 없음", "해당없음", "없음", "모름", "모르겠음",
    "해당 사항 없음", "해당사항없음",
    "-", "--", "---", "—", "...", "pending", "later", "maybe", "?",
})

_WS_RE = re.compile(r"\s+")


def _is_lazy(text: str) -> bool:
    collapsed = _WS_RE.sub(" ", text.strip().lower())
    if not collapsed:
        return True
    if collapsed in _LAZY_TOKENS:
        return True
    return collapsed.rstrip(".!?,;:") in _LAZY_TOKENS


def _canonical_project_root(cwd: Path) -> Path:
    """Walk up to the nearest directory holding ``.episteme/``. Mirrors
    reasoning_surface_guard._canonical_project_root minus the git probe —
    the artifact lives beside the surface, so the walk target is the same."""
    probe = cwd.resolve() if cwd.exists() else cwd
    for _ in range(8):
        if (probe / ".episteme").is_dir():
            return probe
        if probe.parent == probe:
            break
        probe = probe.parent
    return cwd


def artifact_path(cwd: Path) -> Path:
    return _canonical_project_root(cwd) / ".episteme" / "interrogation.json"


def read_artifact(cwd: Path) -> dict | None:
    p = artifact_path(cwd)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _age_seconds(artifact: dict, path: Path) -> int | None:
    """Age from the FRESHER of content ts and file mtime (see module
    docstring for why mtime participates). None when neither parses."""
    ages: list[float] = []
    ts = artifact.get("timestamp")
    if isinstance(ts, (int, float)):
        ages.append(time.time() - float(ts))
    elif isinstance(ts, str) and ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            ages.append(time.time() - dt.timestamp())
        except ValueError:
            pass
    try:
        ages.append(time.time() - path.stat().st_mtime)
    except OSError:
        pass
    if not ages:
        return None
    return int(min(ages))


def _text_floor(value, min_len: int) -> bool:
    return (
        isinstance(value, str)
        and len(value.strip()) >= min_len
        and not _is_lazy(value)
    )


def artifact_status(cwd: Path) -> tuple[str, str]:
    """Return ``(status, detail)`` — status in
    {``ok``, ``missing``, ``invalid``, ``stale``, ``stop``}.

    Detail strings are factual statements suitable for hook output."""
    p = artifact_path(cwd)
    if not p.exists():
        return "missing", "no .episteme/interrogation.json found"
    artifact = read_artifact(cwd)
    if artifact is None:
        return "invalid", "interrogation artifact exists but is not a JSON object"

    age = _age_seconds(artifact, p)
    if age is None:
        return "invalid", "interrogation artifact has no usable timestamp"
    if age > INTERROGATION_TTL_SECONDS:
        return "stale", (
            f"interrogation verdict is {age // 60} minute(s) old "
            f"(TTL {INTERROGATION_TTL_SECONDS // 60} min)"
        )

    if not _text_floor(artifact.get("decision"), _MIN_DECISION_LEN):
        return "invalid", "interrogation artifact lacks a one-line decision"

    claims = artifact.get("claims")
    if not isinstance(claims, list) or not claims:
        return "invalid", "interrogation artifact carries no claims"
    load_bearing: list[dict] = []
    for i, c in enumerate(claims):
        if not isinstance(c, dict):
            return "invalid", f"claims[{i}] is not an object"
        if not _text_floor(c.get("claim"), _MIN_CLAIM_LEN):
            return "invalid", f"claims[{i}].claim is below the atomic-claim floor"
        tier = c.get("tier")
        if tier not in CLAIM_TIERS:
            return "invalid", (
                f"claims[{i}].tier must be one of {sorted(CLAIM_TIERS)}"
            )
        if c.get("load_bearing") is True:
            load_bearing.append(c)
    if not load_bearing:
        return "invalid", (
            "no claim is marked load_bearing — a decision with no "
            "load-bearing claim has not been decomposed"
        )

    refuted_load_bearing = False
    externally_verified = 0
    for c in load_bearing:
        v = c.get("verification")
        if not isinstance(v, dict):
            continue
        method = v.get("method")
        result = v.get("result")
        if method in EXTERNAL_METHODS and result in VERIFICATION_RESULTS:
            if _text_floor(v.get("evidence"), _MIN_EVIDENCE_LEN):
                externally_verified += 1
        if result == "refuted":
            refuted_load_bearing = True
    if externally_verified == 0:
        return "invalid", (
            "no load-bearing claim carries an external verification "
            "(file-read / execution / search) with concrete evidence — "
            "a verification step with no external signal is a null op"
        )

    if not _text_floor(artifact.get("opposition"), _MIN_OPPOSITION_LEN):
        return "invalid", (
            "opposition is below the argued-case floor "
            f"(≥ {_MIN_OPPOSITION_LEN} chars, not a placeholder)"
        )
    if not _text_floor(artifact.get("weakest_link"), _MIN_WEAKEST_LINK_LEN):
        return "invalid", "weakest_link is missing or below the floor"
    if not _text_floor(
        artifact.get("disconfirmation"), _MIN_DISCONFIRMATION_LEN
    ):
        return "invalid", "disconfirmation is missing or a placeholder"

    verdict = artifact.get("verdict")
    if verdict not in VERDICT_VALUES:
        return "invalid", (
            f"verdict must be one of {sorted(VERDICT_VALUES)} (got {verdict!r})"
        )
    if verdict == "stop":
        return "stop", (
            "the interrogation verdict is `stop` — a load-bearing claim "
            "failed or the opposition won; the artifact does not admit ops"
        )
    if refuted_load_bearing and verdict == "proceed":
        return "invalid", (
            "a load-bearing claim was refuted but the verdict is `proceed` "
            "— contradiction; revise (proceed-with-revision) or stop"
        )

    n_verified = externally_verified
    return "ok", (
        f"verdict `{verdict}`; {len(claims)} claim(s), "
        f"{len(load_bearing)} load-bearing, {n_verified} externally verified"
    )


# ---------------------------------------------------------------------------
# E5 · verdict spot-check enqueue (Layer 8 leg)
# ---------------------------------------------------------------------------


def enqueue_verdict_spot_check(cwd: Path, *, op_label: str) -> bool:
    """Enqueue the current verdict artifact into the Layer 8 spot-check
    queue, sample-all (E5: the operator judges substance vs theater).

    Sample-all is affordable by construction: verdicts attach to
    decision shapes, not per-command noise — the Event 137 exemption
    holds the base volume down, and Event 138 retired the per-Bash-call
    sampling that made the old queue unreviewable. Idempotent per
    artifact content (correlation id is the artifact hash), so one
    verdict consumed by several ops enqueues once. Never raises."""
    try:
        artifact = read_artifact(cwd)
        if artifact is None:
            return False
        import _spot_check  # type: ignore  # pyright: ignore[reportMissingImports]
        canon = json.dumps(
            artifact, sort_keys=True, ensure_ascii=False
        ).encode("utf-8", errors="replace")
        cid = "iv_" + hashlib.sha256(canon).hexdigest()[:16]
        if _spot_check._correlation_already_queued(cid):
            return False
        try:
            import _context_signature  # type: ignore  # pyright: ignore[reportMissingImports]
            sig = _context_signature.build(
                _canonical_project_root(cwd),
                blueprint_name="interrogation",
                op_class=op_label,
            ).as_dict()
        except Exception:
            sig = {}
        payload = {
            "type": _spot_check.ENTRY_TYPE,
            "correlation_id": cid,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "op_label": op_label,
            "blueprint": "interrogation",
            "context_signature": sig,
            "surface_snapshot": {"interrogation": artifact},
            "multipliers_applied": ["interrogation_verdict"],
            "effective_rate_at_sample": 1.0,
        }
        _spot_check._chain_append(_spot_check._queue_path(), payload)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Lesson synthesis (PostToolUse arm)
# ---------------------------------------------------------------------------


def lesson_hash(lesson: dict) -> str:
    seed = "|".join(
        str(lesson.get(k, "")).strip() for k in ("context", "rule", "because")
    ).encode("utf-8", errors="replace")
    return "lh_" + hashlib.sha256(seed).hexdigest()[:16]


def _valid_lesson(lesson) -> bool:
    if not isinstance(lesson, dict):
        return False
    return all(
        _text_floor(lesson.get(k), _MIN_LESSON_FIELD_LEN)
        for k in ("context", "rule", "because")
    )


def _op_class_from_payload(payload: dict) -> str:
    tool_input = payload.get("tool_input")
    cmd = ""
    if isinstance(tool_input, dict):
        cmd = str(tool_input.get("command") or "")
    tokens = cmd.split()
    if len(tokens) >= 2:
        return " ".join(tokens[:2])
    if tokens:
        return tokens[0]
    return "interrogation:lesson"


def maybe_synthesize_lesson(payload: dict, exit_code: int | None) -> dict | None:
    """On a successful op whose fresh interrogation verdict carries a valid
    lesson, emit a hash-chained protocol. Returns the protocol payload, or
    None when nothing synthesizes. Never raises past its own boundary —
    bookkeeping must not block PostToolUse."""
    try:
        if exit_code != 0:
            return None
        cwd = Path(payload.get("cwd") or os.getcwd())
        status, _ = artifact_status(cwd)
        if status != "ok":
            return None
        artifact = read_artifact(cwd) or {}
        lesson = artifact.get("lesson")
        if not isinstance(lesson, dict) or not _valid_lesson(lesson):
            return None

        import _framework  # type: ignore  # pyright: ignore[reportMissingImports]
        import _context_signature  # type: ignore  # pyright: ignore[reportMissingImports]

        h = lesson_hash(lesson)
        for env in _framework.list_protocols(include_superseded=True):
            p = env.get("payload") if isinstance(env, dict) else None
            if isinstance(p, dict) and p.get("lesson_hash") == h:
                return None

        sig = _context_signature.build(
            _canonical_project_root(cwd),
            blueprint_name="generic",
            op_class=_op_class_from_payload(payload),
            constraint_head=None,
        )
        protocol_payload = {
            "type": "protocol",
            "source": "interrogation",
            "protocol": (
                f"In context `{lesson['context'].strip()}`, "
                f"{lesson['rule'].strip()} — because "
                f"{lesson['because'].strip()}."
            ),
            "lesson_hash": h,
            "context_signature": sig.as_dict(),
            "decision": str(artifact.get("decision") or ""),
            "verdict": str(artifact.get("verdict") or ""),
        }
        _framework.write_protocol(protocol_payload)
        return protocol_payload
    except Exception:
        return None
