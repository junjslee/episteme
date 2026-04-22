"""Blueprint D · Architectural Cascade & Escalation — v1.0 RC CP10.

Structural validation + hash-chained deferred-discovery writer. Runs
after the cascade detector fires and the guard determines
``blueprint_name == "architectural_cascade"``.

## Required surface fields (spec § Blueprint D)

- ``flaw_classification`` — one of the 7 named classes or ``other``.
- ``posture_selected`` — ``patch`` or ``refactor``.
- ``patch_vs_refactor_evaluation`` — non-generic rationale referencing
  concrete blast-radius surfaces. Must be ≥ 20 chars AND NOT
  consist solely of generic-evaluation tokens
  (``simpler`` / ``easier`` / ``local`` / etc).
- ``blast_radius_map`` — list of dicts. Each entry:
    ``surface`` (string, path or category name) + ``status`` (one of
    ``needs_update`` / ``not-applicable``). ``not-applicable`` entries
    require ``rationale``. Minimum 1 entry. All-``not-applicable``
    yields an advisory (spec's "cascade-theater" hint) — Layer 8's
    ``cascade_integrity`` verdict dimension closes the loop at
    verdict time.
- ``sync_plan`` — list of dicts. Every ``blast_radius_map`` entry with
  ``status: needs_update`` has a matching ``sync_plan`` entry (by
  ``surface``). Each plan entry carries either ``action`` (string)
  or ``no_change_reason`` (string).
- ``deferred_discoveries`` — optional empty list OR list of dicts.
  Each entry: ``description`` (≥ 15 chars), ``observable``,
  ``log_only_rationale``.

## Verdicts

- ``pass`` — all fields valid; op proceeds.
- ``reject`` — missing / invalid field; guard blocks.
- ``advisory-theater`` — ALL blast_radius_map entries marked
  ``not-applicable`` with rationales. Emits stderr advisory, admits
  op (per CP10 plan Q6).
- ``advisory-other`` — ``flaw_classification == "other"`` + valid
  free-text description. Admits op with stderr advisory ("vocab
  expansion candidate for Phase 12 audit") per CP10 plan Q5.
- ``advisory-theater-plus-other`` — both advisories apply; emits both.

## Deferred-discovery writes

Every entry in ``surface["deferred_discoveries"]`` is hash-chained
to ``~/.episteme/framework/deferred_discoveries.jsonl`` at PreToolUse
via ``_framework.write_deferred_discovery``. CP9's
``episteme guide --deferred`` surfaces the accumulating log. Writer
failure swallows silently — architectural-cascade admission must not
block on bookkeeping.

Spec: ``docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md`` § Blueprint D.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


# ---------------------------------------------------------------------------
# Vocabulary + limits
# ---------------------------------------------------------------------------


FLAW_CLASSES: frozenset[str] = frozenset({
    "vulnerability",
    "stale-artifact",
    "config-gap",
    "core-logic-misalignment",
    "deprecated-dependency",
    "doc-code-drift",
    "schema-implementation-drift",
    "other",
})

POSTURE_VALUES: frozenset[str] = frozenset({"patch", "refactor"})

BLAST_RADIUS_STATUS_VALUES: frozenset[str] = frozenset({
    "needs_update", "not-applicable",
})

# Evaluation tokens that by themselves do NOT constitute a
# concrete patch-vs-refactor rationale. If the evaluation text is
# composed entirely of these + filler, reject.
GENERIC_EVALUATION_TOKENS: frozenset[str] = frozenset({
    "simpler", "easier", "local", "smaller", "quicker",
    "cheaper", "faster", "better", "cleaner", "safer",
})

MIN_EVALUATION_LEN = 20
MIN_DESCRIPTION_LEN = 15
MIN_BLAST_RADIUS_ENTRIES = 1


_BLUEPRINT_D_REQUIRED_FIELDS: tuple[str, ...] = (
    "flaw_classification",
    "posture_selected",
    "patch_vs_refactor_evaluation",
    "blast_radius_map",
    "sync_plan",
    "deferred_discoveries",
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z_-]*")


_STOP_WORDS: frozenset[str] = frozenset({
    # Articles / pronouns / auxiliaries
    "it", "is", "are", "was", "were", "will", "be", "been", "being",
    "more", "less", "and", "or", "but", "nor", "yet", "so",
    "the", "a", "an", "to", "of", "this", "that", "its", "as",
    "than", "for", "with", "in", "on", "by", "at", "from",
    "we", "should", "would", "could", "may", "might", "must",
    # Vacuous verbs without specific referent
    "do", "does", "done", "make", "made", "work", "fit", "apply",
    "handle", "manage", "deal", "get", "got", "seem", "seems",
    "look", "feel", "think", "want", "need", "keep",
})


def _is_generic_evaluation(text: str) -> bool:
    """True iff the evaluation consists only of generic tokens +
    stop-words. Captures phrases like ``"it's simpler and easier
    to do"`` that technically reach min length but commit to
    nothing concrete."""
    words = [w.lower() for w in _WORD_RE.findall(text)]
    if not words:
        return True
    non_generic = [
        w for w in words
        if w not in GENERIC_EVALUATION_TOKENS
        and w not in _STOP_WORDS
    ]
    return len(non_generic) == 0


def _validate_blast_radius_map(
    raw: Any,
) -> tuple[str | None, bool]:
    """Return ``(error_message_or_none, all_not_applicable)``.
    ``error_message_or_none`` is the first structural violation, or
    ``None`` when the map validates. ``all_not_applicable`` is
    ``True`` when every entry is ``not-applicable`` — caller decides
    advisory posture."""
    if not isinstance(raw, list):
        return (
            f"blast_radius_map must be a list (got {type(raw).__name__})",
            False,
        )
    if len(raw) < MIN_BLAST_RADIUS_ENTRIES:
        return (
            f"blast_radius_map must carry at least "
            f"{MIN_BLAST_RADIUS_ENTRIES} entry",
            False,
        )
    all_not_applicable = True
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            return (
                f"blast_radius_map[{i}] must be a dict "
                f"(got {type(entry).__name__})",
                False,
            )
        surface = entry.get("surface")
        status = entry.get("status")
        if not isinstance(surface, str) or not surface.strip():
            return (
                f"blast_radius_map[{i}].surface must be a non-empty string",
                False,
            )
        if status not in BLAST_RADIUS_STATUS_VALUES:
            return (
                f"blast_radius_map[{i}].status must be one of "
                f"{sorted(BLAST_RADIUS_STATUS_VALUES)} (got {status!r})",
                False,
            )
        if status == "not-applicable":
            rationale = entry.get("rationale")
            if not isinstance(rationale, str) or not rationale.strip():
                return (
                    f"blast_radius_map[{i}].rationale required when "
                    f"status is `not-applicable` (got {rationale!r})",
                    False,
                )
        else:
            all_not_applicable = False
    return (None, all_not_applicable)


def _validate_sync_plan(
    raw: Any, blast_radius_map: list,
) -> str | None:
    """Every ``needs_update`` surface in the map must have a matching
    plan entry. Each plan entry must carry ``action`` OR
    ``no_change_reason`` (non-empty string)."""
    if not isinstance(raw, list):
        return f"sync_plan must be a list (got {type(raw).__name__})"
    needs_update_surfaces = {
        entry["surface"]
        for entry in blast_radius_map
        if isinstance(entry, dict)
        and entry.get("status") == "needs_update"
        and isinstance(entry.get("surface"), str)
    }
    plan_surfaces: set[str] = set()
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            return (
                f"sync_plan[{i}] must be a dict (got {type(entry).__name__})"
            )
        surface = entry.get("surface")
        if not isinstance(surface, str) or not surface.strip():
            return f"sync_plan[{i}].surface must be a non-empty string"
        action = entry.get("action")
        no_change = entry.get("no_change_reason")
        if not (
            (isinstance(action, str) and action.strip())
            or (isinstance(no_change, str) and no_change.strip())
        ):
            return (
                f"sync_plan[{i}] must carry either `action` or "
                f"`no_change_reason` (non-empty string)"
            )
        plan_surfaces.add(surface)
    missing = needs_update_surfaces - plan_surfaces
    if missing:
        return (
            f"sync_plan missing entries for blast_radius_map surfaces "
            f"marked `needs_update`: {sorted(missing)}"
        )
    return None


def _validate_deferred_discoveries(raw: Any) -> str | None:
    """Optional empty list; when present, each entry requires
    description (≥ MIN_DESCRIPTION_LEN), observable (non-empty),
    log_only_rationale (non-empty)."""
    if not isinstance(raw, list):
        return (
            f"deferred_discoveries must be a list "
            f"(got {type(raw).__name__})"
        )
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            return (
                f"deferred_discoveries[{i}] must be a dict "
                f"(got {type(entry).__name__})"
            )
        desc = entry.get("description")
        obs = entry.get("observable")
        rat = entry.get("log_only_rationale")
        if not isinstance(desc, str) or len(desc.strip()) < MIN_DESCRIPTION_LEN:
            return (
                f"deferred_discoveries[{i}].description must be a "
                f"string of ≥ {MIN_DESCRIPTION_LEN} chars"
            )
        if not isinstance(obs, str) or not obs.strip():
            return (
                f"deferred_discoveries[{i}].observable must be a "
                f"non-empty string"
            )
        if not isinstance(rat, str) or not rat.strip():
            return (
                f"deferred_discoveries[{i}].log_only_rationale must "
                f"be a non-empty string"
            )
    return None


# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------


def validate_blueprint_d(surface: dict) -> tuple[str, str]:
    """Return ``(verdict, detail)``.

    verdict ∈ {``pass``, ``reject``, ``advisory-theater``,
    ``advisory-other``, ``advisory-theater-plus-other``}.
    """
    missing = [
        f for f in _BLUEPRINT_D_REQUIRED_FIELDS
        if f not in surface
    ]
    if missing:
        return (
            "reject",
            f"Blueprint D: required fields missing from surface: "
            f"{', '.join(missing)}. Spec § Blueprint D requires "
            f"all of flaw_classification, posture_selected, "
            f"patch_vs_refactor_evaluation, blast_radius_map, "
            f"sync_plan, deferred_discoveries.",
        )

    # flaw_classification vocabulary.
    flaw = surface.get("flaw_classification")
    is_other = False
    if not isinstance(flaw, str) or flaw.strip() not in FLAW_CLASSES:
        return (
            "reject",
            f"Blueprint D: flaw_classification must be one of "
            f"{sorted(FLAW_CLASSES)} (got {flaw!r}).",
        )
    if flaw.strip() == "other":
        # Require a descriptive free-text body somewhere — the
        # patch_vs_refactor_evaluation carries it in practice. We
        # validate evaluation below; here just mark the advisory.
        is_other = True

    # posture_selected.
    posture = surface.get("posture_selected")
    if not isinstance(posture, str) or posture.strip() not in POSTURE_VALUES:
        return (
            "reject",
            f"Blueprint D: posture_selected must be one of "
            f"{sorted(POSTURE_VALUES)} (got {posture!r}).",
        )

    # patch_vs_refactor_evaluation.
    evaluation = surface.get("patch_vs_refactor_evaluation")
    if not isinstance(evaluation, str) or len(evaluation.strip()) < MIN_EVALUATION_LEN:
        return (
            "reject",
            f"Blueprint D: patch_vs_refactor_evaluation must be ≥ "
            f"{MIN_EVALUATION_LEN} chars naming concrete blast-radius "
            f"surfaces (got {evaluation!r}).",
        )
    if _is_generic_evaluation(evaluation):
        return (
            "reject",
            f"Blueprint D: patch_vs_refactor_evaluation consists only "
            f"of generic tokens ({sorted(GENERIC_EVALUATION_TOKENS)}); "
            f"name at least one concrete blast-radius surface. "
            f"Generic phrasing like 'simpler' or 'easier' does not "
            f"discharge the cognitive check.",
        )

    # blast_radius_map.
    blast_map_err, all_na = _validate_blast_radius_map(
        surface.get("blast_radius_map")
    )
    if blast_map_err:
        return ("reject", f"Blueprint D: {blast_map_err}")

    # sync_plan (depends on validated blast_radius_map).
    plan_err = _validate_sync_plan(
        surface.get("sync_plan"),
        surface.get("blast_radius_map") or [],
    )
    if plan_err:
        return ("reject", f"Blueprint D: {plan_err}")

    # deferred_discoveries.
    dd_err = _validate_deferred_discoveries(
        surface.get("deferred_discoveries")
    )
    if dd_err:
        return ("reject", f"Blueprint D: {dd_err}")

    # Advisories.
    advisories: list[str] = []
    if all_na:
        advisories.append(
            "blast_radius_map has ALL entries marked `not-applicable` — "
            "cascade-theater risk. Layer 8 will sample this firing at 2× "
            "with a `cascade_integrity` verdict dimension. Reconsider "
            "whether a single `needs_update` surface belongs in the map."
        )
    if is_other:
        advisories.append(
            "flaw_classification = `other` — Phase 12 audit vocabulary "
            "expansion candidate. Keep the surface; the classification "
            "goes into deferred_discoveries triage."
        )

    if advisories:
        detail = " | ".join(f"Blueprint D: {a}" for a in advisories)
        if all_na and is_other:
            return ("advisory-theater-plus-other", detail)
        if all_na:
            return ("advisory-theater", detail)
        return ("advisory-other", detail)

    return ("pass", "")


# ---------------------------------------------------------------------------
# Deferred-discovery writer
# ---------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def write_cascade_deferred_discoveries(
    surface: dict,
    *,
    correlation_id: str,
    op_label: str,
    cwd: Path,
    now: datetime | None = None,
) -> int:
    """Hash-chain each ``deferred_discoveries[]`` entry via
    ``_framework.write_deferred_discovery``. Returns count written.

    Graceful degrade — writer failure logs a stderr fallback and
    returns the count up to the failure. Admission never blocks on
    bookkeeping.
    """
    entries = surface.get("deferred_discoveries")
    if not isinstance(entries, list) or not entries:
        return 0
    try:
        from _framework import (  # type: ignore  # pyright: ignore[reportMissingImports]
            write_deferred_discovery,
        )
    except ImportError:
        return 0
    flaw = str(surface.get("flaw_classification") or "other")
    now_dt = now or datetime.now(timezone.utc)
    logged_at = _iso(now_dt)
    count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            payload = {
                "type": "deferred_discovery",
                "logged_at": logged_at,
                "flaw_classification": flaw,
                "description": str(entry.get("description", "")).strip(),
                "observable": str(entry.get("observable", "")).strip(),
                "log_only_rationale": str(
                    entry.get("log_only_rationale", "")
                ).strip(),
                "source_op": {
                    "correlation_id": correlation_id,
                    "op_label": op_label,
                    "cwd": str(cwd),
                },
                "status": "pending",
            }
            write_deferred_discovery(payload)
            count += 1
        except Exception as exc:
            sys.stderr.write(
                f"[episteme] Blueprint D deferred-discovery write "
                f"fallback: {exc.__class__.__name__}; remaining entries "
                f"attempted.\n"
            )
    return count
