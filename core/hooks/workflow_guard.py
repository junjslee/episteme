#!/usr/bin/env python3
"""PreToolUse advisory guard for edits outside tracked workflow files.

This is intentionally non-blocking. It nudges the agent to keep authoritative
project docs in sync when editing implementation files directly.

Event 173: when the governed project's tracked markdown cites the edited path
(exactly, or via an enclosing directory), the advisory names those docs with
their lifecycle state instead of the generic two-file reminder — the citation
walk is episteme.doc_references' (one notion of "what a doc cites"), imported
from this checkout's src/ with the E172 self-resolve pattern. Any failure on
that path — package unimportable (plugin context), project not a git repo,
no citing docs — falls back to the original generic advisory, never a crash.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

#: Cap on docs named inline; the overflow is counted, never silently dropped.
_MAX_ADVISORY_DOCS = 6

#: Advisory log rotation: rewrite keeping the newest lines once the file
#: exceeds the byte cap (budgets are code — the log must not grow unbounded).
_ADVISORY_LOG_MAX_BYTES = 262_144
_ADVISORY_LOG_KEEP_LINES = 500


ALLOWED_DOC_PATHS = {
    "AGENTS.md",
    "CLAUDE.md",
    "docs/REQUIREMENTS.md",
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
        cwd / "docs" / "EVENTS.md",
        cwd / "docs" / "NEXT_STEPS.md",
    ]
    return any(p.exists() for p in required)


def _load_doc_references():
    """Import ``episteme.doc_references`` from this checkout's ``src/``.

    E172 self-resolve pattern: the hook file lives inside the episteme
    checkout, so ``src/`` is findable from ``__file__`` regardless of the
    governed project's cwd. ``None`` on ANY failure — the caller keeps the
    generic advisory; a plugin install without the package must not break.
    """
    try:
        src = Path(__file__).resolve().parents[2] / "src"
        if src.is_dir() and str(src) not in sys.path:
            sys.path.insert(0, str(src))
        from episteme import doc_references  # noqa: PLC0415

        return doc_references
    except Exception:
        return None


def _relative_to_cwd(cwd: Path, target_path: str) -> str:
    try:
        return str(Path(target_path).resolve().relative_to(cwd.resolve()))
    except (ValueError, OSError):
        return Path(target_path).name


def _log_advisory(cwd: Path, rel_path: str, docs: list) -> None:
    """Append one JSONL record per targeted advisory (E174 dashboard feed).

    A log, not a queue (M1-clean: nothing awaits a drain) — it exists so the
    viewer can SHOW docs being tracked as code changes. Written only where
    ``.episteme/`` already exists (same footprint rule as the doc-map cache),
    size-capped by rewrite, and failure-silent: observability must never
    break the edit it observes.
    """
    try:
        state_dir = cwd / ".episteme" / "state"
        if not (cwd / ".episteme").is_dir():
            return
        state_dir.mkdir(parents=True, exist_ok=True)
        log = state_dir / "doc_advisories.jsonl"
        from datetime import datetime, timezone

        record = json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "path": rel_path,
                "docs": docs[:_MAX_ADVISORY_DOCS],
                "doc_count": len(docs),
            }
        )
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(record + "\n")
        if log.stat().st_size > _ADVISORY_LOG_MAX_BYTES:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            tmp = log.with_suffix(f".jsonl.tmp.{os.getpid()}")
            tmp.write_text(
                "\n".join(lines[-_ADVISORY_LOG_KEEP_LINES:]) + "\n",
                encoding="utf-8",
            )
            tmp.replace(log)
    except Exception:
        pass


def _targeted_advisory(cwd: Path, target_path: str) -> "str | None":
    """The doc-map advisory for ``target_path``, or ``None`` for fallback.

    ``None`` whenever the answer is unavailable (no package, no git, IO
    error) or genuinely empty (positive system: no citation, no obligation).
    """
    dr = _load_doc_references()
    if dr is None:
        return None
    try:
        index = dr.cached_reverse_index(cwd)
        edges = dr.edges_for_path(cwd, target_path, index=index)
        if not edges:
            return None
        docs = [e.doc for e in edges]
        labels = dict(dr.annotate_docs(cwd, docs))
        rel = _relative_to_cwd(cwd, target_path)
        _log_advisory(cwd, rel, docs)
        lines = [f"DOC ADVISORY: {len(docs)} doc(s) claim to describe '{rel}' —"]
        for e in edges[:_MAX_ADVISORY_DOCS]:
            label = labels.get(e.doc, "")
            via = f"  [via {e.target}/]" if e.kind == "dir" else ""
            lines.append(
                f"  {e.doc}" + (f"  ({label})" if label else "") + via
            )
        overflow = len(docs) - _MAX_ADVISORY_DOCS
        if overflow > 0:
            lines.append(
                f"  … and {overflow} more — `episteme docs map '{rel}'` lists all."
            )
        lines.append(
            "Verify they still tell the truth about this edit; "
            "repair in the same change or record why not."
        )
        return "\n".join(lines)
    except Exception:
        return None


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

    cwd = Path(payload.get("cwd") or os.getcwd())

    # E173 repair of a latent bug: harness payloads carry ABSOLUTE file paths,
    # and `lstrip("./")` strips a character set, not a prefix, so the doc-path
    # suppression never matched absolute spellings — the guard nagged on doc
    # edits it was designed to stay silent on. Normalize to the project-relative
    # spelling before the policy test. Textual prefix-strip FIRST: this repo's
    # authoritative docs are symlinks into a private tree, and resolve() would
    # follow them out of the project and defeat the suppression for exactly the
    # files it exists to cover; resolve() is only the fallback for spelling
    # mismatches like /tmp vs /private/tmp.
    policy_path = target_path
    if os.path.isabs(target_path):
        norm_t = os.path.normpath(target_path)
        norm_c = os.path.normpath(str(cwd))
        if norm_t.startswith(norm_c + os.sep):
            policy_path = norm_t[len(norm_c) + 1 :].replace(os.sep, "/")
        else:
            try:
                policy_path = str(
                    Path(target_path).resolve().relative_to(cwd.resolve())
                ).replace(os.sep, "/")
            except (ValueError, OSError):
                policy_path = target_path

    if _is_doc_or_policy_path(policy_path):
        return 0

    if not _project_has_authoritative_docs(cwd):
        return 0

    context = _targeted_advisory(cwd, target_path) or (
        f"WORKFLOW ADVISORY: Editing '{Path(target_path).name}' outside authoritative docs. "
        "Keep docs/EVENTS.md and docs/NEXT_STEPS.md aligned with this change."
    )
    advisory = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": context,
        }
    }
    sys.stdout.write(json.dumps(advisory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
