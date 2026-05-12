"""`episteme practice walk` — narrated walkthrough of the 5-stage practice.

For onboarding + 60-second comprehension. The walkthrough renders each
stage with:
  - Stage name + ordinal + purpose
  - The cognitive moves that constitute the stage
  - For each move: the System-1 failure it counters + the schema field
    where its residue lands

Optional `--interactive` mode pauses between stages waiting for [Enter]
so the operator can reflect rather than scroll. Non-interactive mode
prints all five stages in one continuous output (suitable for scripted
display or onboarding docs).
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from typing import List

from core.practice.cognitive_moves import (
    moves_by_stage,
    ordered_stages,
)
from episteme import _ui
from episteme._ui import Color


def render_stage(stage_idx_total: int, stage_idx: int, stage, *, color_for_stage: Color = "cyan") -> str:
    """Render one stage of the practice as a narrated section."""
    lines: List[str] = []
    title = f"Stage {stage_idx}/{stage_idx_total} · {stage.name}"
    lines.append(_ui.header(title, level=1, color=color_for_stage))
    lines.append("")
    lines.append(stage.purpose)
    lines.append("")
    lines.append(_ui.colored(f"Source: {stage.workflow_policy_anchor}", "grey"))
    lines.append(_ui.colored(f"Doc:    {stage.way_to_think_anchor}", "grey"))
    lines.append("")

    lines.append(_ui.header("Cognitive moves in this stage", level=2, color="grey"))
    moves = moves_by_stage(stage.id)
    for m in moves:
        lines.append("")
        lines.append(_ui.colored(f"  • {m.name}", "bold"))
        lines.append(f"    {m.description}")
        lines.append(_ui.colored(
            f"    Counters: {m.system_1_failure_counter}", "grey"
        ))
        if m.schema_field:
            lines.append(_ui.colored(f"    Residue:  {m.schema_field}", "grey"))
    lines.append("")
    return "\n".join(lines)


def run_walk(*, interactive: bool = False, color: Color = "cyan") -> int:
    """Print the 5-stage walkthrough. Returns exit code 0."""
    stages = ordered_stages()
    total = len(stages)

    # Intro
    print()
    print(_ui.header("episteme · the way to think (생각의 틀)", level=1, color="cyan"))
    print()
    print("A five-stage cognitive practice with mechanical teeth at the gates of")
    print("irreversible AI-assisted decisions. Anchored on Kahneman's System-2,")
    print("Dalio's Radical Transparency, Boyd's OODA, Munger's Latticework.")
    print()
    print(_ui.colored("Source of truth:", "grey"))
    print(_ui.colored("  • core/memory/global/cognitive_profile.md", "grey"))
    print(_ui.colored("  • core/memory/global/workflow_policy.md", "grey"))
    print(_ui.colored("  • docs/THE_WAY_TO_THINK.md", "grey"))
    print()
    print(_ui.divider())
    print()

    if interactive:
        try:
            input(_ui.colored("Press Enter to walk through Stage 1 (Frame)...", "grey"))
        except (EOFError, KeyboardInterrupt):
            return 0

    # Each stage
    for i, stage in enumerate(stages, start=1):
        print(render_stage(total, i, stage, color_for_stage=color))
        if interactive and i < total:
            try:
                next_name = stages[i].name
                input(_ui.colored(f"Press Enter to walk through Stage {i+1} ({next_name})...", "grey"))
            except (EOFError, KeyboardInterrupt):
                return 0
            print()

    # Outro
    print(_ui.divider())
    print()
    print(_ui.header("That is the practice", level=1, color="cyan"))
    print()
    print("Every signed Reasoning Surface is the residue of this practice performed")
    print("once. The schema fields exist to make each cognitive move structural —")
    print("not a polite request the model can ignore.")
    print()
    print("Try it now:")
    print(_ui.colored("  $ episteme surface author --interactive", "cyan"))
    print()
    print("Or see a worked example:")
    print(_ui.colored("  $ episteme practice demo", "cyan"))
    print()
    return 0
