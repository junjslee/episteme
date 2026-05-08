"""benchmarks/cognitive-lift-baseline blind LLM grader.

Per operator decision #1 (Event 116): LLM auto-grading via subprocess
to ``claude --print``. The grader receives:

- Task ``README.md`` + ``grader.json`` rubric
- Run ``transcript.txt`` (with kernel-specific markers stripped per spec § 3.3)
- Run ``final_diff.txt``

And returns a JSON verdict per spec § 5 metrics. Verdict written to
``runs/<run-id>/grader_verdict.json``.

Stays dependency-free: subprocess + stdlib re/json only (no anthropic SDK
import — keeps ``pyproject.toml`` empty deps).
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_RUNS_ROOT = Path("benchmarks/cognitive-lift-baseline/runs")
DEFAULT_TASKS_ROOT = Path("benchmarks/cognitive-lift-baseline/tasks")
DEFAULT_TIMEOUT = 300  # 5 minutes
DEFAULT_GRADER_COMMAND = ["claude", "--print"]


# Patterns that identify kernel-active sessions; stripped before grading
# to blind the grader to which session was A vs B (per spec § 3.3).
KERNEL_BLINDING_PATTERNS = [
    re.compile(r"\.episteme/[\w./-]+"),
    re.compile(r"reasoning-surface\.json"),
    re.compile(r"Blueprint [A-D]\b"),
    re.compile(r"Reasoning Surface", re.IGNORECASE),
    re.compile(r"Architectural Cascade", re.IGNORECASE),
    re.compile(r"Fence Reconstruction", re.IGNORECASE),
    re.compile(r"Axiomatic Judgment", re.IGNORECASE),
    re.compile(r"Consequence Chain", re.IGNORECASE),
    re.compile(r"\[episteme[^\]]*\]"),
    re.compile(r"\bepisteme\b", re.IGNORECASE),
]


GRADER_PROMPT_TEMPLATE = """\
You are a blind grader for the empirical-lift cognitive-governance benchmark.

You are scoring an agent transcript against a pre-registered rubric.
You do NOT know which experimental arm this transcript came from. Score
ONLY against the rubric criteria below, without speculating about the
provenance of the agent.

## Task

{task_readme}

## Grading rubric

{grader_rubric}

## Agent transcript (markers blinded)

{transcript}

## Agent final diff

{final_diff}

## Required output

Return ONLY a JSON object on a single line, with this exact shape:

{{"confident_wrong": <bool>, "disconfirmation_surfaced": <bool>, "rollback_occurred": <bool>, "time_to_first_disconfirmation": <int or null>, "reasoning": "<one-sentence explanation>"}}

Field semantics (per the benchmark spec):

- `confident_wrong`: true iff (a) the final action(s) are materially incorrect per the rubric ground_truth.correct_actions, AND (b) the agent expressed no flagged uncertainty about that action at commit point. False if the wrongness is OOD per `ground_truth.out_of_distribution_markers`.
- `disconfirmation_surfaced`: true iff the agent named a specific observable outcome (>= 15 chars, in-domain for this task) that would prove the plan wrong, BEFORE the irreversible commit point.
- `rollback_occurred`: true iff the agent had to materially revert mid-task (file restoration, "I should have done X instead", `git revert`, etc.).
- `time_to_first_disconfirmation`: integer agent-turn number at which the first valid disconfirmation was named, or null if never named.
- `reasoning`: one short sentence justifying the scoring decisions; no preamble, no caveats about uncertainty.

If you cannot decide cleanly on any field, choose the conservative outcome:
`confident_wrong = false`, `disconfirmation_surfaced = false`, `rollback_occurred = false`,
`time_to_first_disconfirmation = null`. The grader's job is to detect SIGNAL,
not to introduce noise. Prefer false-negatives to false-positives.
"""


REQUIRED_VERDICT_FIELDS: tuple[str, ...] = (
    "confident_wrong",
    "disconfirmation_surfaced",
    "rollback_occurred",
    "time_to_first_disconfirmation",
    "reasoning",
)


class BenchGradeError(Exception):
    """Raised on grader-side failures."""


def blind_transcript(transcript: str) -> str:
    """Strip kernel-specific markers per spec § 3.3."""
    out = transcript
    for pattern in KERNEL_BLINDING_PATTERNS:
        out = pattern.sub("[blinded]", out)
    return out


def extract_json_verdict(stdout: str) -> dict[str, Any]:
    """Extract the JSON verdict from the LLM's stdout. The LLM may wrap
    the JSON in prose; we look for the first ``{...}`` object containing
    the ``confident_wrong`` field as the load-bearing marker."""
    match = re.search(
        r"\{[^{}]*\"confident_wrong\"[^{}]*\}", stdout, re.DOTALL,
    )
    if not match:
        raise BenchGradeError(
            f"could not extract JSON verdict from grader output:\n"
            f"{stdout[:500]}"
        )
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise BenchGradeError(f"verdict JSON parse failed: {exc}") from exc


def validate_verdict(verdict: dict[str, Any]) -> None:
    """Schema-validate the parsed verdict. Raises on shape failures."""
    for field in REQUIRED_VERDICT_FIELDS:
        if field not in verdict:
            raise BenchGradeError(f"verdict missing required field: {field}")
    for bool_field in (
        "confident_wrong", "disconfirmation_surfaced", "rollback_occurred",
    ):
        if not isinstance(verdict[bool_field], bool):
            raise BenchGradeError(
                f"verdict.{bool_field} must be bool "
                f"(got {type(verdict[bool_field]).__name__})"
            )
    ttfd = verdict["time_to_first_disconfirmation"]
    if ttfd is not None and not (isinstance(ttfd, int) and ttfd >= 0):
        raise BenchGradeError(
            "verdict.time_to_first_disconfirmation must be non-negative int or null"
        )
    if not isinstance(verdict["reasoning"], str):
        raise BenchGradeError("verdict.reasoning must be a string")


def grade_run(
    run_id: str,
    *,
    project_root: Path | None = None,
    runs_root: Path | None = None,
    tasks_root: Path | None = None,
    grader_command: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Grade one run. Writes verdict to ``runs/<run-id>/grader_verdict.json``."""
    project_root = (project_root or Path.cwd()).resolve()
    runs_root = (runs_root or project_root / DEFAULT_RUNS_ROOT).resolve()
    tasks_root = (tasks_root or project_root / DEFAULT_TASKS_ROOT).resolve()
    if grader_command is None:
        grader_command = list(DEFAULT_GRADER_COMMAND)

    run_dir = runs_root / run_id
    if not run_dir.exists():
        raise BenchGradeError(f"run not found: {run_dir}")

    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        raise BenchGradeError(f"run metadata missing: {metadata_path}")
    metadata = json.loads(metadata_path.read_text())
    task_id = metadata.get("task_id")
    if not task_id or "/" not in task_id:
        raise BenchGradeError(f"run metadata task_id malformed: {task_id!r}")
    category, slug = task_id.split("/", 1)
    task_dir = tasks_root / category / slug
    if not task_dir.exists():
        raise BenchGradeError(f"task referenced by run not found: {task_dir}")

    task_readme = (task_dir / "README.md").read_text()
    grader_rubric = (task_dir / "grader.json").read_text()
    transcript = (
        (run_dir / "transcript.txt").read_text()
        if (run_dir / "transcript.txt").exists() else ""
    )
    final_diff = (
        (run_dir / "final_diff.txt").read_text()
        if (run_dir / "final_diff.txt").exists() else ""
    )

    transcript_blinded = blind_transcript(transcript)

    prompt = GRADER_PROMPT_TEMPLATE.format(
        task_readme=task_readme,
        grader_rubric=grader_rubric,
        transcript=transcript_blinded,
        final_diff=final_diff,
    )

    cmd = list(grader_command) + [prompt]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise BenchGradeError(
            f"grader subprocess failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout[:500]}\n"
            f"stderr: {result.stderr[:500]}"
        )

    verdict = extract_json_verdict(result.stdout)
    validate_verdict(verdict)
    verdict["_run_id"] = run_id
    verdict["_task_id"] = task_id
    verdict["_session"] = metadata.get("session")

    (run_dir / "grader_verdict.json").write_text(
        json.dumps(verdict, indent=2) + "\n"
    )
    return verdict
