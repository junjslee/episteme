#!/usr/bin/env python3
"""PreToolUse advisory guard for edits outside tracked workflow files.

This is intentionally non-blocking. It nudges the agent to keep authoritative
project docs in sync when editing implementation files directly.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


ALLOWED_DOC_PATHS = {
    "AGENTS.md",
    "CLAUDE.md",
    "docs/REQUIREMENTS.md",
    "docs/PLAN.md",
    "docs/EVENTS.md",
    "docs/NEXT_STEPS.md",
    "docs/RUN_CONTEXT.md",
}


def _extract_tool_name(payload: dict) -> str:
    return str(payload.get("tool_name") or payload.get("toolName") or "").strip()


def _extract_path(payload: dict) -> str:
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if isinstance(tool_input, dict):
        return str(
            tool_input.get("file_path")
            or tool_input.get("path")
            or tool_input.get("target_file")
            or ""
        ).strip()
    return ""


def _is_doc_or_policy_path(path_str: str) -> bool:
    p = path_str.replace("\\", "/").lstrip("./")
    if p in ALLOWED_DOC_PATHS:
        return True
    if p.startswith("docs/"):
        return True
    if p.startswith(".planning/"):
        return True
    return False


def _project_has_authoritative_docs(cwd: Path) -> bool:
    required = [
        cwd / "AGENTS.md",
        cwd / "docs" / "PLAN.md",
        cwd / "docs" / "EVENTS.md",
        cwd / "docs" / "NEXT_STEPS.md",
    ]
    return any(p.exists() for p in required)


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    tool_name = _extract_tool_name(payload)
    if tool_name not in {"Write", "Edit", "MultiEdit"}:
        return 0

    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = payload.get("toolInput")
    if not isinstance(tool_input, dict):
        tool_input = {}

    if payload.get("session_type") == "task" or bool(tool_input.get("is_subagent")):
        return 0

    target_path = _extract_path(payload)
    if not target_path:
        return 0

    if _is_doc_or_policy_path(target_path):
        return 0

    cwd = Path(payload.get("cwd") or os.getcwd())
    if not _project_has_authoritative_docs(cwd):
        return 0

    advisory = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"WORKFLOW ADVISORY: Editing '{Path(target_path).name}' outside authoritative docs. "
                "Keep docs/PLAN.md, docs/EVENTS.md, and docs/NEXT_STEPS.md aligned with this change."
            ),
        }
    }
    sys.stdout.write(json.dumps(advisory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
