"""benchmarks/cognitive-lift-baseline runner — paired comparison harness.

Per spec § 3.1: for each task, configure two Claude Code sessions
(``A``=control no-kernel, ``B``=treatment kernel-strict-mode) against
fresh copies of the task's ``repo-state``. Capture transcript + final
diff + timing per session into ``runs/<run-id>/``.

Subprocess invocation of ``claude --print`` is the integration boundary;
runtime calibration of hook firing under non-interactive mode is a
Phase 2 calibration first task (spec § 9 + deferred discoveries).

Operator decisions locked at Event 116 (``README.md`` § 11):

- Session B uses strict mode (NO ``.episteme/advisory-surface`` marker).
- Single model: ``claude-sonnet-4-6`` (lives in each task's ``seed.json``).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

DEFAULT_RUNS_ROOT = Path("benchmarks/cognitive-lift-baseline/runs")
DEFAULT_TASKS_ROOT = Path("benchmarks/cognitive-lift-baseline/tasks")
DEFAULT_TIMEOUT = 1800  # 30 minutes wall-clock


class BenchRunError(Exception):
    """Raised on runner-side failures."""


def _default_claude_command_for_session(session: str) -> list[str]:
    """Per-session claude invocation defaults.

    Session A (control / no-kernel) uses ``--bare`` which per ``claude --help``
    'skips hooks, LSP, plugin sync, attribution, auto-memory, background
    prefetches, keychain reads, and CLAUDE.md auto-discovery'. This is the
    cleanest kernel-disable mechanism — much stronger than per-cwd settings
    overrides.

    Session B (treatment / kernel-strict-mode) uses default invocation so
    plugin hooks load + ``--debug hooks`` to surface hook events in stderr
    for calibration visibility.

    Both sessions:
    - ``--print`` for non-interactive mode (single-shot)
    - ``--allow-dangerously-skip-permissions`` for headless reliability —
      tasks may require shell ops the agent would otherwise prompt on
    - ``--max-budget-usd 0.50`` to bound per-session cost during Phase 2

    The prompt is appended by the caller; this returns the prefix only.
    """
    common = [
        "--print",
        "--allow-dangerously-skip-permissions",
        "--max-budget-usd", "0.50",
    ]
    if session == "A":
        return ["claude", "--bare", *common]
    if session == "B":
        return ["claude", *common, "--debug", "hooks"]
    raise BenchRunError(f"unknown session: {session!r}")


def _resolve_task_dir(combined_id: str, tasks_root: Path) -> Path:
    if "/" not in combined_id:
        raise BenchRunError(
            f"expected '<category>/<task-id>' (got {combined_id!r})"
        )
    category, task_id = combined_id.split("/", 1)
    task_dir = tasks_root / category / task_id
    if not task_dir.exists():
        raise BenchRunError(f"task not found: {task_dir}")
    return task_dir


def _make_run_id(task_id: str, session: str) -> str:
    """Deterministic-prefix + uuid4 suffix for traceability."""
    safe = task_id.replace("/", "-")
    return f"{safe}-{session}-{uuid.uuid4().hex[:8]}"


def _capture_repo_diff(baseline: Path, work: Path) -> str:
    """Run ``git diff --no-index`` and capture the output. Best-effort —
    git may not be installed; fall back to a marker indicating the diff
    capture failed (the run is still valid for transcript-only grading)."""
    try:
        result = subprocess.run(
            [
                "git", "diff", "--no-index", "--no-color",
                str(baseline), str(work),
            ],
            capture_output=True, text=True, timeout=60,
        )
        return result.stdout
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        return f"<diff capture failed: {exc.__class__.__name__}>\n"


def _configure_session_a(work_dir: Path) -> None:
    """Session A (control): empty hooks; no kernel content."""
    settings_dir = work_dir / ".claude"
    settings_dir.mkdir(exist_ok=True)
    (settings_dir / "settings.json").write_text(
        json.dumps({"hooks": {}}, indent=2)
    )
    # Strip any inherited episteme state to keep the session pristine.
    episteme_dir = work_dir / ".episteme"
    if episteme_dir.exists():
        shutil.rmtree(episteme_dir)


def _configure_session_b(work_dir: Path, kernel_settings: dict[str, Any]) -> None:
    """Session B (treatment): kernel hooks active in STRICT mode.

    Per operator decision #4 (Event 116): strict mode for Session B.
    Strict mode = NO ``.episteme/advisory-surface`` marker file. The
    kernel gate blocks rather than warns.
    """
    settings_dir = work_dir / ".claude"
    settings_dir.mkdir(exist_ok=True)
    (settings_dir / "settings.json").write_text(
        json.dumps(kernel_settings, indent=2)
    )
    # Initialize a clean .episteme/ in strict mode (no advisory marker).
    episteme_dir = work_dir / ".episteme"
    episteme_dir.mkdir(exist_ok=True)
    advisory_marker = episteme_dir / "advisory-surface"
    if advisory_marker.exists():
        advisory_marker.unlink()


def _load_kernel_settings(claude_settings_path: Path) -> dict[str, Any]:
    """Load operator's user-global Claude Code settings. Falls back to
    empty hooks if the file is missing or unparseable."""
    if not claude_settings_path.exists():
        return {"hooks": {}}
    try:
        return json.loads(claude_settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {"hooks": {}}


def run_session(
    combined_id: str,
    session: str,
    *,
    project_root: Path | None = None,
    runs_root: Path | None = None,
    tasks_root: Path | None = None,
    claude_command: list[str] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    user_settings_path: Path | None = None,
) -> Path:
    """Run one paired-comparison session. Returns the run directory.

    ``claude_command`` defaults to ``['claude', '--print']`` but can be
    overridden for tests (subprocess mock) or for runtime calibration
    when the integration shape changes.
    """
    if session not in ("A", "B"):
        raise BenchRunError(f"session must be 'A' or 'B' (got {session!r})")

    project_root = (project_root or Path.cwd()).resolve()
    runs_root = (runs_root or project_root / DEFAULT_RUNS_ROOT).resolve()
    tasks_root = (tasks_root or project_root / DEFAULT_TASKS_ROOT).resolve()
    if claude_command is None:
        claude_command = _default_claude_command_for_session(session)
    if user_settings_path is None:
        user_settings_path = Path.home() / ".claude" / "settings.json"

    task_dir = _resolve_task_dir(combined_id, tasks_root)
    run_id = _make_run_id(combined_id, session)
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    work_dir = run_dir / "work"
    repo_state_src = task_dir / "repo-state"
    if repo_state_src.exists():
        shutil.copytree(repo_state_src, work_dir)
    else:
        work_dir.mkdir()

    if session == "A":
        _configure_session_a(work_dir)
    else:
        kernel_settings = _load_kernel_settings(user_settings_path)
        _configure_session_b(work_dir, kernel_settings)

    task_prompt = (task_dir / "README.md").read_text()

    cmd = list(claude_command) + [task_prompt]
    started_at = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(
            cmd, cwd=work_dir,
            capture_output=True, text=True, timeout=timeout,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        returncode = result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        returncode = -1
        timed_out = True
    elapsed = time.monotonic() - started_at

    final_diff = (
        _capture_repo_diff(repo_state_src, work_dir)
        if repo_state_src.exists() else ""
    )

    metadata = {
        "run_id": run_id,
        "task_id": combined_id,
        "session": session,
        "wall_clock_seconds": round(elapsed, 2),
        "returncode": returncode,
        "timed_out": timed_out,
        "claude_command": cmd[:-1],  # exclude the prompt from the audit log
    }

    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (run_dir / "transcript.txt").write_text(stdout)
    (run_dir / "stderr.txt").write_text(stderr)
    (run_dir / "final_diff.txt").write_text(final_diff)

    return run_dir
