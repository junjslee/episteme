"""Context injection — render a StepBoundary into typed prompt context.

This is the load-bearing anti-self-conditioning step. When step N+1's
prompt is assembled, the runtime emits each ledger item with a structural
tag that the model is system-prompted to treat non-fungibly:

    <fact id="..." method="..." source="...">...</fact>
    <inference id="..." model="..." confidence="0.84">...
        <promotion_blockers>...</promotion_blockers>
    </inference>
    <unknown id="..." cost="...">...</unknown>
    <assumption id="..." if_wrong_then="..." detectability="...">...</assumption>

A canary check downstream (not in this module) looks for the model
re-citing an <inference> id as if it were a <fact> — that pattern is a
promotion-violation and gets logged and flagged.

This module is pure rendering; no I/O.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from html import escape
from typing import List

from core.ptsp.types import StepBoundary


def _attr(value: str) -> str:
    """XML-attribute-safe escape — single line, no quotes."""
    return escape(str(value), quote=True).replace("\n", " ")


def _content(text: str) -> str:
    """Inner-content escape — multi-line allowed, but tag chars escaped."""
    return escape(text, quote=False)


def render_step_context(boundary: StepBoundary) -> str:
    """Render a sealed StepBoundary as a typed-tag context block.

    Returns a string suitable for direct injection into the next step's
    user/system prompt. The structural typing of the tags is what the
    model is system-prompted to respect.
    """
    parts: List[str] = []
    parts.append(
        f'<step_context step_index="{_attr(str(boundary.step_index))}" '
        f'session_id="{_attr(boundary.session_id)}" '
        f'parent_hash="{_attr(boundary.parent_hash or "")}">'
    )

    # ── Facts ──
    parts.append("  <facts>")
    for fact in boundary.knowns:
        parts.append(
            f'    <fact id="{_attr(fact.id)}" '
            f'verified_at="{_attr(fact.verified_at)}" '
            f'method="{_attr(fact.verification_method)}" '
            f'source="{_attr(fact.source_artifact.locator)}">'
        )
        parts.append(f"      {_content(fact.content)}")
        parts.append("    </fact>")
    parts.append("  </facts>")

    # ── Inferences (NOT facts; model is system-prompted to honor this) ──
    parts.append("  <inferences>")
    for inf in boundary.inferences:
        parts.append(
            f'    <inference id="{_attr(inf.id)}" '
            f'model="{_attr(inf.generated_by.model_name)}" '
            f'confidence_self_reported="{_attr(str(inf.confidence_self_reported))}">'
        )
        parts.append(f"      {_content(inf.content)}")
        if inf.promotion_blockers:
            parts.append("      <promotion_blockers>")
            for blocker in inf.promotion_blockers:
                parts.append(
                    f'        <blocker type="{_attr(blocker.type)}">{_content(blocker.detail)}</blocker>'
                )
            parts.append("      </promotion_blockers>")
        parts.append("    </inference>")
    parts.append("  </inferences>")

    # ── Unknowns ──
    parts.append("  <unknowns>")
    for u in boundary.unknowns:
        parts.append(
            f'    <unknown id="{_attr(u.id)}" '
            f'cost_of_ignorance="{_attr(u.cost_of_ignorance)}">'
        )
        parts.append(f"      {_content(u.question)}")
        parts.append("    </unknown>")
    parts.append("  </unknowns>")

    # ── Assumptions ──
    parts.append("  <assumptions>")
    for a in boundary.assumptions:
        parts.append(
            f'    <assumption id="{_attr(a.id)}" '
            f'if_wrong_then="{_attr(a.if_wrong_then)}" '
            f'detectability="{_attr(a.detectability)}">'
        )
        parts.append(f"      {_content(a.assumption)}")
        parts.append("    </assumption>")
    parts.append("  </assumptions>")

    parts.append("</step_context>")

    return "\n".join(parts)
