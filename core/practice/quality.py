"""Practice-quality observations — gap-finding, not single-score grading.

This module observes a signed surface (or a stream of them) and emits
*gap observations* about practice quality. It deliberately does NOT
produce a single 0-10 score for the whole surface. Operator-noted
failure mode: surfacing a single score would create gaming pressure —
operators would optimize for the score rather than for the practice.

Instead, `observe_surface()` returns a list of `PracticeObservation`s
naming specific cognitive moves that were skipped, performed shallowly,
or substituted with lazy placeholders. The observations are qualitative
("Unknowns ledger empty" / "Disconfirmation cite is condition-vague")
and traceable back to the cognitive-move registry.

Used by `episteme practice retro` for retrospective summaries.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Literal, Optional

# cognitive_moves registry is the source-of-truth for move_id strings used
# in PracticeObservation; not imported here because we reference move_ids
# by string literal. Importing would create a cycle via core/practice/__init__.py.


Severity = Literal["info", "advisory", "warn", "critical"]


@dataclass(frozen=True, slots=True)
class PracticeObservation:
    """One observation about a single cognitive move on a single surface."""
    move_id: str
    severity: Severity
    summary: str  # short label, e.g., "Unknowns ledger empty"
    detail: str  # longer explanation
    surface_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "move_id": self.move_id,
            "severity": self.severity,
            "summary": self.summary,
            "detail": self.detail,
            "surface_id": self.surface_id,
        }


@dataclass
class PracticeRetrospective:
    """Aggregate practice observations over a window of surfaces."""
    period_from: Optional[str]
    period_to: Optional[str]
    surfaces_examined: int
    observations: List[PracticeObservation] = field(default_factory=list)
    move_gap_counts: Dict[str, int] = field(default_factory=dict)
    most_frequent_gaps: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_from": self.period_from,
            "period_to": self.period_to,
            "surfaces_examined": self.surfaces_examined,
            "observations": [o.to_dict() for o in self.observations],
            "move_gap_counts": dict(self.move_gap_counts),
            "most_frequent_gaps": list(self.most_frequent_gaps),
        }


# ─── Lazy-placeholder detection ──────────────────────────────────────────


_LAZY_PATTERNS = [
    re.compile(r"^\s*(tbd|n/?a|none|see above|various|tba|todo|fixme|\?+)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(해당\s*없음|없음)\s*$"),
]


def _is_lazy(text: Any) -> bool:
    if not isinstance(text, str) or not text.strip():
        return True
    for pat in _LAZY_PATTERNS:
        if pat.match(text):
            return True
    return False


# ─── Single-surface observation ──────────────────────────────────────────


def observe_surface(signed_surface: Dict[str, Any]) -> List[PracticeObservation]:
    """Run the practice-quality observation pass on one signed surface.

    Returns a list of `PracticeObservation`s. Empty list means the surface
    has no observable cognitive-move gaps. Non-empty list lists specific
    moves where the practice fell short.

    Severity levels:
      info       — minor; the field is structurally present
      advisory   — practice is shallow but defensible
      warn       — a cognitive move was skipped or substituted with a placeholder
      critical   — the field is required for safety-critical decisions and is missing
    """
    obs: List[PracticeObservation] = []
    surface = signed_surface.get("surface", {})
    envelope = signed_surface.get("envelope", {})
    sid = envelope.get("surface_id")

    risk = surface.get("risk_classification", {})
    is_irreversible = risk.get("reversibility") == "irreversible"
    is_high_tier = risk.get("ai_act_tier") in ("high", "unacceptable")

    # ── Frame stage ──
    cq = surface.get("core_question", "")
    if _is_lazy(cq):
        obs.append(PracticeObservation(
            move_id="frame.core_question",
            severity="critical" if is_irreversible else "warn",
            summary="Core Question is empty or lazy",
            detail=(
                "The Frame stage requires naming the single question this decision is actually trying "
                "to answer. Found: empty or lazy-placeholder value. Counters question-substitution "
                "(Kahneman System 1 fallback)."
            ),
            surface_id=sid,
        ))
    elif len(cq.strip()) < 40:
        obs.append(PracticeObservation(
            move_id="frame.core_question",
            severity="advisory",
            summary="Core Question is structurally present but shallow",
            detail=(
                f"Core Question is {len(cq.strip())} chars. The schema accepts ≥20, but Frame-stage "
                f"discipline typically produces a fully-specified question of 40+ chars. Likely a "
                f"placeholder pass; reauthor with a question that names the specific decision context."
            ),
            surface_id=sid,
        ))

    unknowns = surface.get("unknowns", []) or []
    if len(unknowns) == 0:
        obs.append(PracticeObservation(
            move_id="frame.unknowns",
            severity="warn" if is_irreversible or is_high_tier else "advisory",
            summary="Unknowns ledger empty",
            detail=(
                "The Frame stage requires naming what you don't know. An empty Unknowns ledger is "
                "structurally suspicious — it claims perfect information, which is almost never true. "
                "Counters WYSIATI (Kahneman) — reasoning from what's in context, blind to what's absent."
            ),
            surface_id=sid,
        ))
    else:
        # Examine each unknown for cost_of_ignorance depth
        for i, u in enumerate(unknowns):
            coi = u.get("cost_of_ignorance", "") if isinstance(u, dict) else ""
            if _is_lazy(coi) or len(coi.strip()) < 30:
                obs.append(PracticeObservation(
                    move_id="frame.unknowns",
                    severity="warn",
                    summary=f"unknowns[{i}].cost_of_ignorance is shallow",
                    detail=(
                        f"Unknown #{i} present but cost_of_ignorance is empty / lazy / under 30 chars. "
                        f"The cost field is what enforces the utility filter — 'so what is the cost of "
                        f"staying ignorant?' Without it the Unknown is decorative."
                    ),
                    surface_id=sid,
                ))

    assumptions = surface.get("assumptions", []) or []
    if len(assumptions) == 0 and is_irreversible:
        obs.append(PracticeObservation(
            move_id="frame.assumptions",
            severity="warn",
            summary="Assumptions ledger empty on irreversible decision",
            detail=(
                "Irreversible decisions almost always rest on load-bearing assumptions. An empty "
                "Assumptions ledger claims none — structurally suspicious. Counters overconfidence "
                "(Kahneman) and hidden-constraint failure (cognitive_profile.md § Governance Core)."
            ),
            surface_id=sid,
        ))
    else:
        for i, a in enumerate(assumptions):
            if not isinstance(a, dict):
                continue
            iw = a.get("if_wrong_then", "")
            if _is_lazy(iw):
                obs.append(PracticeObservation(
                    move_id="frame.assumptions",
                    severity="advisory",
                    summary=f"assumptions[{i}].if_wrong_then is lazy",
                    detail=(
                        f"Assumption #{i} present but if_wrong_then is empty / lazy. The if-wrong "
                        f"projection is what makes the assumption falsifiable in retrospect."
                    ),
                    surface_id=sid,
                ))

    # ── Verify stage ──
    discon = surface.get("disconfirmation_conditions", []) or []
    if len(discon) == 0:
        obs.append(PracticeObservation(
            move_id="verify.disconfirmation_conditions",
            severity="critical" if is_irreversible else "warn",
            summary="Disconfirmation conditions empty",
            detail=(
                "The Verify stage requires pre-committed conditions that would invalidate the plan. "
                "Without disconfirmation conditions, the decision is unfalsifiable — it is doxa, not "
                "epistēmē. Robust falsifiability is enforced at the file-system level by episteme; "
                "the practice requires it BEFORE the action, not after."
            ),
            surface_id=sid,
        ))
    else:
        for i, d in enumerate(discon):
            if not isinstance(d, dict):
                continue
            obs_field = d.get("observable", "")
            method = d.get("measurement_method", "")
            if _is_lazy(obs_field) or len(obs_field.strip()) < 20:
                obs.append(PracticeObservation(
                    move_id="verify.disconfirmation_conditions",
                    severity="warn",
                    summary=f"disconfirmation_conditions[{i}].observable is vague",
                    detail=(
                        f"Disconfirmation #{i} observable is empty / lazy / under 20 chars. Robust "
                        f"falsifiability requires a CONCRETE OBSERVABLE — 'if issues arise' fails; "
                        f"'p95 latency > 500ms for 5 min on Grafana dashboard api-latency' passes."
                    ),
                    surface_id=sid,
                ))
            if _is_lazy(method):
                obs.append(PracticeObservation(
                    move_id="verify.disconfirmation_conditions",
                    severity="advisory",
                    summary=f"disconfirmation_conditions[{i}].measurement_method missing",
                    detail=(
                        f"Disconfirmation #{i} lacks measurement_method. The observable is the WHAT; "
                        f"measurement_method is the HOW — how would you actually observe this in practice?"
                    ),
                    surface_id=sid,
                ))

    # ── Decompose stage (hypothesis-as-bet) ──
    decision = surface.get("decision", {})
    confidence = decision.get("confidence")
    if isinstance(confidence, (int, float)):
        if is_irreversible and decision.get("choice") == "proceed" and confidence < 0.5:
            obs.append(PracticeObservation(
                move_id="decompose.hypothesis_as_bet",
                severity="warn",
                summary="Low confidence on irreversible proceed",
                detail=(
                    f"Decision is 'proceed' on an irreversible action with confidence "
                    f"{confidence:.2f} < 0.50. The bet itself is honest — proceeding under low "
                    f"confidence is sometimes the right call — but it should be paired with a strong "
                    f"rollback path (handoff.stop_rollback_path) and explicit disconfirmation."
                ),
                surface_id=sid,
            ))

    # ── Handoff stage ──
    rollback = decision.get("stop_rollback_path", "")
    if _is_lazy(rollback) or len(rollback.strip()) < 20:
        obs.append(PracticeObservation(
            move_id="handoff.stop_rollback_path",
            severity="warn" if is_irreversible else "advisory",
            summary="Stop / rollback path is vague",
            detail=(
                "The Handoff stage requires concrete rollback steps. 'Revert if needed' fails; "
                "'psql -c \"SELECT pg_cancel_backend(pid)\" against the migration session' passes. "
                "Without a concrete path, rollback feasibility is being assumed under planning-fallacy "
                "(Kahneman) pressure."
            ),
            surface_id=sid,
        ))

    # ── Article 79(1) AI Act trigger enumeration (when tier=high) ──
    if is_high_tier:
        triggers = risk.get("article_79_1_triggers", []) or []
        if len(triggers) == 0:
            obs.append(PracticeObservation(
                move_id="frame.constraint_regime",
                severity="advisory",
                summary="High-tier surface without Article 79(1) triggers",
                detail=(
                    "ai_act_tier is 'high' but article_79_1_triggers list is empty. EU AI Act Article "
                    "12(2)(a) compliance gap. Enumerate the specific triggers that put this decision "
                    "in the Article 79(1) risk class."
                ),
                surface_id=sid,
            ))

    return obs


# ─── Aggregate retrospective ─────────────────────────────────────────────


def observe_surfaces(
    surfaces: Iterable[Dict[str, Any]],
    *,
    period_from: Optional[str] = None,
    period_to: Optional[str] = None,
) -> PracticeRetrospective:
    """Build a retrospective across multiple surfaces.

    Counts per-move gap occurrences. Identifies the most frequent gaps so
    the operator can see which cognitive moves are repeatedly being shallow
    or skipped. This is the practice-quality signal — not a single score,
    but a pattern of recurring gaps.
    """
    all_obs: List[PracticeObservation] = []
    surfaces_list = list(surfaces)
    move_counts: Dict[str, int] = {}

    for surface in surfaces_list:
        obs = observe_surface(surface)
        all_obs.extend(obs)
        for o in obs:
            move_counts[o.move_id] = move_counts.get(o.move_id, 0) + 1

    # Sort by frequency descending
    sorted_moves = sorted(move_counts.items(), key=lambda kv: -kv[1])
    most_frequent = [move_id for move_id, _ in sorted_moves[:5]]

    return PracticeRetrospective(
        period_from=period_from,
        period_to=period_to,
        surfaces_examined=len(surfaces_list),
        observations=all_obs,
        move_gap_counts=dict(move_counts),
        most_frequent_gaps=most_frequent,
    )
