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

# Cap for inlined tool-call args / tool-result content in extracted transcript.
# The grader's prompt template has a budget; we keep extracted segments short.
_EXTRACT_TOOL_INPUT_MAX = 200
_EXTRACT_TOOL_RESULT_MAX = 500


class BenchRunError(Exception):
    """Raised on runner-side failures."""


def _is_jsonl_stream(text: str) -> bool:
    """Heuristic: first non-empty line parses as a JSON dict with a 'type' field.
    True iff the captured stdout is in stream-json format (Event 117 v2+).
    False for v1-style text output."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return False
        return isinstance(obj, dict) and "type" in obj
    return False


def _render_assistant_event(obj: dict) -> str | None:
    """Render an `assistant`-type stream-json event as human-readable text.
    Includes plain text content + a one-line marker per tool_use block."""
    message = obj.get("message", {})
    content = message.get("content", []) if isinstance(message, dict) else []
    rendered: list[str] = []
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text = block.get("text", "")
            if text:
                rendered.append(text)
        elif btype == "tool_use":
            tool_name = block.get("name", "?")
            try:
                tool_input = json.dumps(block.get("input", {}), ensure_ascii=False)
            except (TypeError, ValueError):
                tool_input = str(block.get("input", ""))
            if len(tool_input) > _EXTRACT_TOOL_INPUT_MAX:
                tool_input = tool_input[:_EXTRACT_TOOL_INPUT_MAX] + "...[truncated]"
            rendered.append(f"[Tool call: {tool_name}({tool_input})]")
    return "\n".join(rendered) if rendered else None


def _render_user_event(obj: dict) -> str | None:
    """Render a `user`-type stream-json event — typically tool_result blocks."""
    message = obj.get("message", {})
    content = message.get("content", []) if isinstance(message, dict) else []
    rendered: list[str] = []
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") != "tool_result":
            continue
        result_content = block.get("content", "")
        if isinstance(result_content, list):
            text_parts = [
                b.get("text", "") for b in result_content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            result_content = "\n".join(text_parts)
        result_text = str(result_content)
        if len(result_text) > _EXTRACT_TOOL_RESULT_MAX:
            result_text = result_text[:_EXTRACT_TOOL_RESULT_MAX] + "...[truncated]"
        rendered.append(f"[Tool result]\n{result_text}")
    return "\n".join(rendered) if rendered else None


def _render_event(obj: dict) -> str | None:
    """Render one stream-json event as a human-readable transcript segment.
    Returns None when the event is not transcript-relevant."""
    event_type = obj.get("type")
    if event_type == "assistant":
        return _render_assistant_event(obj)
    if event_type == "user":
        return _render_user_event(obj)
    if event_type == "system":
        subtype = obj.get("subtype", "")
        if subtype == "init":
            cwd = obj.get("cwd", "")
            return f"[session init] cwd={cwd}"
        if subtype.startswith("hook"):
            hook_name = obj.get("hook_name", "")
            hook_event = obj.get("hook_event", "")
            return f"[hook {subtype}] {hook_event}:{hook_name}"
        return None
    if event_type == "result":
        result_text = str(obj.get("result", ""))
        return f"[Final result]\n{result_text}"
    return None


def extract_human_transcript_from_jsonl(jsonl_text: str) -> str:
    """Extract a human-readable transcript from stream-json JSONL output.

    Each event becomes a transcript segment per ``_render_event``. Blank-line
    separators between segments. Lines that don't parse as JSON pass through
    verbatim (preserves any non-JSON noise in the captured stream)."""
    segments: list[str] = []
    for line in jsonl_text.splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            segments.append(line)
            continue
        rendered = _render_event(obj)
        if rendered:
            segments.append(rendered)
    return "\n\n".join(segments)


def _default_claude_command_for_session(session: str) -> list[str]:
    """Per-session claude invocation defaults — runner v2 (Event 117 calibration).

    v2 changes from v1:

    - Session A drops ``--bare`` (which strips OAuth — Calibration Finding C-1)
      and uses ``--setting-sources project`` instead. Per ``claude --help``,
      this loads only per-cwd ``.claude/settings.json`` — the runner writes
      that file with ``{"hooks": {}}`` so user-global hooks don't propagate.
      Calibration v2 must verify whether plugins respect setting-sources
      OR load regardless (in which case Session A needs another mechanism).
    - Both sessions switch from ``--print`` text output to
      ``--print --output-format stream-json --include-hook-events``. The
      stream-json format produces one JSON record per event (model chunk,
      tool call, hook fire, etc.) — survives abnormal termination and
      directly answers the load-bearing question 'did kernel hooks fire?'
      via discrete hook-event records.
    - Budget cap raised from $0.50 → $2.00 per session — v1 hit the cap
      at 40s before productive output (Finding C-2).
    - Session B drops ``--debug hooks`` since ``--include-hook-events`` is
      the structured replacement.

    The prompt is appended by the caller; this returns the prefix only.
    """
    common = [
        "--print",
        "--verbose",  # claude requires --verbose to pair with stream-json
        "--output-format", "stream-json",
        "--include-hook-events",
        "--allow-dangerously-skip-permissions",
        "--max-budget-usd", "2.00",
    ]
    if session == "A":
        return ["claude", *common, "--setting-sources", "project"]
    if session == "B":
        return ["claude", *common]
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
    # v3: if stdout is stream-json (JSONL), preserve raw + write extracted
    # human-readable transcript. Else (text mode) write stdout as transcript.txt.
    if _is_jsonl_stream(stdout):
        (run_dir / "transcript.jsonl").write_text(stdout)
        (run_dir / "transcript.txt").write_text(
            extract_human_transcript_from_jsonl(stdout)
        )
    else:
        (run_dir / "transcript.txt").write_text(stdout)
    (run_dir / "stderr.txt").write_text(stderr)
    (run_dir / "final_diff.txt").write_text(final_diff)

    return run_dir
