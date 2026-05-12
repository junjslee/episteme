"""The cognitive practice layer.

This package is the source-of-truth registry for the 5-stage practice
(Frame → Decompose → Execute → Verify → Handoff) and the cognitive moves
that constitute each stage. Both the hook error messages and the
`episteme practice` CLI dereference this registry so the practice
vocabulary stays consistent across surfaces.

The registry is authored against the operator's existing
`core/memory/global/cognitive_profile.md` + `workflow_policy.md`. This
module does not invent practice; it indexes the operator's authored
practice into machine-readable form.

The package also provides `core.practice.quality` — surface-quality
observation generation (gap-finding, not single-score grading) used by
`episteme practice retro` for retrospective reporting.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from core.practice.cognitive_moves import (
    STAGES,
    COGNITIVE_MOVES,
    CognitiveMove,
    Stage,
    StageName,
    get_move,
    get_stage,
    move_for_field,
    moves_by_stage,
)
from core.practice.quality import (
    PracticeObservation,
    PracticeRetrospective,
    observe_surface,
    observe_surfaces,
)

__all__ = [
    # cognitive_moves
    "STAGES",
    "COGNITIVE_MOVES",
    "CognitiveMove",
    "Stage",
    "StageName",
    "get_move",
    "get_stage",
    "move_for_field",
    "moves_by_stage",
    # quality
    "PracticeObservation",
    "PracticeRetrospective",
    "observe_surface",
    "observe_surfaces",
]
