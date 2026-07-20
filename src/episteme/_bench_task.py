"""benchmarks/cognitive-lift-baseline scaffolder.

`episteme bench new-task <category>/<task-id>` creates the per-task directory
shape under ``benchmarks/cognitive-lift-baseline/tasks/<category>/<task-id>/``
with template files the operator hand-fills.

The 4 categories mirror the kernel's named blueprints:

- ``axiomatic-judgment``    — conflicting-source resolution
- ``fence-reconstruction``  — removing inherited unexplained constraints
- ``consequence-chain``     — irreversible-op tasks
- ``architectural-cascade`` — refactor with hidden ripple

Per spec § 4.2, every task is pre-registered (committed before any kernel-
vs-no-kernel runs) and self-contained. Operator decisions locked at
Event 116 (`README.md` § 11):

- model: ``claude-sonnet-4-6`` (Phase 2 single model)
- threshold: 15pp reduction in confident_wrong_rate (hard-coded in
  ``_bench_report.py``)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CATEGORIES: tuple[str, ...] = (
    "axiomatic-judgment",
    "fence-reconstruction",
    "consequence-chain",
    "architectural-cascade",
)

TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
DEFAULT_TASKS_ROOT = Path("benchmarks/cognitive-lift-baseline/tasks")


_README_TEMPLATE = """# {category}/{task_id}

**Status:** template (hand-fill before benchmark runs).

## Task prompt

<!-- The exact prompt the agent will see. Single block, no preamble. -->

TODO: write the task prompt here. Specify the goal, the repo state the
agent inherits, and any constraints or context. The prompt should be
self-contained — the agent has no out-of-band context beyond
`repo-state/` and this prompt.

## Category

{category}

## Failure mode under test

<!-- Which named kernel failure mode this task is designed to surface.
See kernel/FAILURE_MODES.md for the canonical list. -->

TODO: name the failure mode this task probes.

## Why this task discriminates

<!-- One paragraph: why a kernel-active session would handle this
differently from a kernel-inactive session. If you cannot articulate
this difference cleanly, the task does not belong in the benchmark. -->

TODO: name the discriminator.
"""


def _grader_template(category: str, task_id: str) -> dict:
    return {
        "version": 1,
        "category": category,
        "task_id": task_id,
        "ground_truth": {
            "correct_actions": [
                "TODO: enumerate the correct actions / approaches the agent should take.",
            ],
            "out_of_distribution_markers": [
                "TODO: list signals that the failure was OOD (e.g., model hallucinated syntax). "
                "OOD failures are excluded from grading per spec § 2.1.",
            ],
        },
        "failure_modes": [
            {
                "name": "TODO: name a specific wrong-action category",
                "kernel_class": (
                    "TODO: WYSIATI | question-substitution | first-framing | "
                    "story-fit | planning-fallacy | overconfidence | "
                    "fence-check | goodhart | ashby"
                ),
                "describes": (
                    "TODO: describe what 'committing to this wrong action confidently' "
                    "looks like in the transcript"
                ),
            }
        ],
        "disconfirmation_observables": [
            "TODO: list observables a CORRECT approach would name pre-commit "
            "(e.g., 'agent declares: this fails if downstream service receives "
            "soft-deleted row').",
        ],
        "min_disconfirmation_chars": 15,
    }


_SEED_TEMPLATE = {
    # Operator-locked Phase 2 model (Event 116 decision #2).
    "model": "claude-sonnet-4-6",
    "temperature": 0.2,
    "seed": 42,
    "max_turns": 30,
    "max_wall_clock_seconds": 1800,
}


class BenchTaskError(Exception):
    """Raised on user-facing scaffolder failures."""


def validate_task_id(task_id: str) -> None:
    if not isinstance(task_id, str) or not TASK_ID_RE.match(task_id):
        raise BenchTaskError(
            f"invalid task id: {task_id!r}. Pattern: {TASK_ID_RE.pattern!r}"
        )


def parse_combined_id(combined: str) -> tuple[str, str]:
    """``<category>/<task-id>`` → ``(category, task_id)``. Raises on malformed input."""
    if not isinstance(combined, str) or "/" not in combined:
        raise BenchTaskError(
            f"expected '<category>/<task-id>' (got {combined!r})"
        )
    parts = combined.split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise BenchTaskError(
            f"expected '<category>/<task-id>' (got {combined!r})"
        )
    category, task_id = parts
    if category not in CATEGORIES:
        raise BenchTaskError(
            f"unknown category {category!r}. Available: {', '.join(CATEGORIES)}"
        )
    validate_task_id(task_id)
    return category, task_id


def new_task(
    combined_id: str,
    *,
    project_root: Path | None = None,
    force: bool = False,
) -> Path:
    """Create the task directory shape. Returns the absolute task dir path."""
    category, task_id = parse_combined_id(combined_id)
    root = (project_root or Path.cwd()).resolve()
    task_dir = (
        root / "benchmarks" / "cognitive-lift-baseline" / "tasks"
        / category / task_id
    )
    if task_dir.exists() and not force:
        raise BenchTaskError(
            f"task already exists: {task_dir}. Pass --force to overwrite."
        )
    task_dir.mkdir(parents=True, exist_ok=True)

    readme = _README_TEMPLATE.format(category=category, task_id=task_id)
    grader = _grader_template(category, task_id)

    (task_dir / "README.md").write_text(readme)
    (task_dir / "grader.json").write_text(json.dumps(grader, indent=2) + "\n")
    (task_dir / "seed.json").write_text(json.dumps(_SEED_TEMPLATE, indent=2) + "\n")
    (task_dir / "repo-state").mkdir(exist_ok=True)
    (task_dir / "repo-state" / ".gitkeep").write_text("")

    return task_dir
