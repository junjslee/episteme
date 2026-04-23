#!/usr/bin/env python3
"""PostToolUse hook: write a per-decision episodic record.

Implements the episodic-tier writer from kernel/MEMORY_ARCHITECTURE.md. The
kernel memory architecture declares four write triggers for an episodic
record:

  1. High-impact action (matches the reasoning_surface_guard pattern set).
  2. Hook-blocked or escalated action.
  3. Disconfirmation fired (full or partial).
  4. Operator-elected record.

This first-pass writer fires on #1 only. Hook-blocked actions never reach
PostToolUse on most runtimes; #3 and #4 need signals this hook does not yet
have. Those arrive in later phases; the writer is structured so adding a
trigger is a matter of a new `_should_record` branch, not a rewrite.

Output: `~/.episteme/memory/episodic/YYYY-MM-DD.jsonl`, append-only, one
JSON record per line, conforming to `core/schemas/memory-contract/
episodic_record.json` (+ the `common.json` base).

Never blocks. Any exception → return 0. Memory writes must not interfere
with the agent's execution path.

Kernel anchors:
- kernel/MEMORY_ARCHITECTURE.md  (tier contract + write triggers)
- core/schemas/memory-contract/episodic_record.json  (record shape)
- core/schemas/memory-contract/common.json            (base envelope)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Mirrors reasoning_surface_guard.HIGH_IMPACT_BASH but kept local so this
# hook has no sibling import dependency. The two pattern sets drift over
# time; if they diverge, the consequence is a false-negative here (no
# episodic record for an action the guard treated as high-impact), which
# is preferable to a crash.
_HIGH_IMPACT_BASH = [
    (re.compile(r"\bgit\s+push\b"), "git push"),
    (re.compile(r"\bgit\s+merge\b(?!\s+--abort)"), "git merge"),
    (re.compile(r"\bnpm\s+publish\b"), "npm publish"),
    (re.compile(r"\byarn\s+publish\b"), "yarn publish"),
    (re.compile(r"\bpnpm\s+publish\b"), "pnpm publish"),
    (re.compile(r"\bpoetry\s+publish\b"), "poetry publish"),
    (re.compile(r"\bcargo\s+publish\b"), "cargo publish"),
    (re.compile(r"\btwine\s+upload\b"), "twine upload"),
    (re.compile(r"\bpip\s+install\b(?!.*--dry-run)"), "pip install"),
    (re.compile(r"\bpip\s+uninstall\b"), "pip uninstall"),
    (re.compile(r"\balembic\s+upgrade\b"), "alembic upgrade"),
    (re.compile(r"\bprisma\s+migrate\s+deploy\b"), "prisma migrate deploy"),
    (re.compile(r"\bterraform\s+apply\b"), "terraform apply"),
    (re.compile(r"\bterraform\s+destroy\b"), "terraform destroy"),
    (re.compile(r"\bkubectl\s+(?:delete|apply)\b"), "kubectl delete/apply"),
    (re.compile(r"\baws\s+s3\s+rm\b"), "aws s3 rm"),
    (re.compile(r"\bgcloud\b.*\bdelete\b"), "gcloud delete"),
    (re.compile(r"\bDROP\s+(?:TABLE|DATABASE|SCHEMA)\b", re.I), "SQL DROP"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.I), "SQL TRUNCATE"),
    (re.compile(r"\bgh\s+pr\s+merge\b"), "gh pr merge"),
    (re.compile(r"\bgh\s+release\s+create\b"), "gh release create"),
]

_NORMALIZE_SEPARATORS = re.compile(r"[,'\"\[\]\(\)\{\}`]")


def _episodic_path(ts: str) -> Path:
    return Path.home() / ".episteme" / "memory" / "episodic" / f"{ts[:10]}.jsonl"


def _tool_name(payload: dict) -> str:
    return str(payload.get("tool_name") or payload.get("toolName") or "").strip()


def _tool_input(payload: dict) -> dict:
    raw = payload.get("tool_input") or payload.get("toolInput") or {}
    return raw if isinstance(raw, dict) else {}


def _bash_command(payload: dict) -> str:
    ti = _tool_input(payload)
    return str(ti.get("command") or ti.get("cmd") or ti.get("bash_command") or "")


def _cwd(payload: dict) -> str:
    return str(payload.get("cwd") or os.getcwd())


def _matched_high_impact(cmd: str) -> list[str]:
    if not cmd:
        return []
    normalized = _NORMALIZE_SEPARATORS.sub(" ", cmd)
    hits: list[str] = []
    for pat, label in _HIGH_IMPACT_BASH:
        if pat.search(normalized):
            hits.append(label)
    return hits


def _extract_exit_code(payload: dict):
    resp = payload.get("tool_response") or payload.get("toolResponse") or {}
    if not isinstance(resp, dict):
        return None
    for key in ("exit_code", "exitCode", "returncode", "return_code", "status_code"):
        v = resp.get(key)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.strip().lstrip("-").isdigit():
            return int(v.strip())
    for wrapper_key in ("metadata", "meta"):
        wrapper = resp.get(wrapper_key)
        if isinstance(wrapper, dict):
            for key in ("exit_code", "exitCode", "returncode", "return_code"):
                v = wrapper.get(key)
                if isinstance(v, int):
                    return v
    return None


def _extract_status(payload: dict) -> str:
    resp = payload.get("tool_response") or payload.get("toolResponse") or {}
    if not isinstance(resp, dict):
        return "unknown"
    if "is_error" in resp:
        return "error" if resp["is_error"] else "success"
    if "error" in resp and resp["error"]:
        return "error"
    s = resp.get("status")
    if isinstance(s, str) and s:
        return s.lower()
    return "unknown"


def _correlation_id(payload: dict, cmd: str, ts: str) -> str:
    """Same algorithm as calibration_telemetry so the two records join."""
    rid = payload.get("tool_use_id") or payload.get("toolUseId") or payload.get("request_id")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    cwd = _cwd(payload)
    bucket = ts.split(".")[0]
    seed = f"{bucket}|{cwd}|{cmd}".encode("utf-8", errors="replace")
    return "h_" + hashlib.sha1(seed).hexdigest()[:16]


def _session_id(payload: dict, ts: str) -> str:
    sid = (
        payload.get("session_id")
        or payload.get("sessionId")
        or payload.get("conversation_id")
    )
    if isinstance(sid, str) and sid.strip():
        return sid.strip()
    # Fallback: a stable-ish session bucket by date + cwd so records within
    # a single day in the same project cluster together even without a
    # runtime-provided id.
    seed = f"{ts[:10]}|{_cwd(payload)}".encode("utf-8")
    return "s_" + hashlib.sha1(seed).hexdigest()[:12]


def _canonical_project_root(cwd: Path) -> Path:
    """Resolve project root so surface lookup survives subdirectory cwd.
    Mirrors reasoning_surface_guard._canonical_project_root. Duplicated
    here for hook-isolation (each hook is a standalone script; no shared
    import path). Path-A Event 42 fix."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=2,
        )
        if out.returncode == 0 and out.stdout.strip():
            return Path(out.stdout.strip())
    except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
        pass
    probe = cwd.resolve() if cwd.exists() else cwd
    for _ in range(8):
        if (probe / ".episteme").is_dir():
            return probe
        if probe.parent == probe:
            break
        probe = probe.parent
    return cwd


def _read_reasoning_surface(cwd: str) -> dict | None:
    """Best-effort read of the Surface the guard evaluated against.

    The surface is the epistemic context the decision was made in; without
    it, the episodic record cannot be used for later similarity retrieval.
    Missing surface is not an error — some high-impact ops happen under
    advisory-mode with no surface. Returns None in that case; the record
    still writes, just without the surface field.
    """
    try:
        cwd_path = Path(cwd) if cwd else Path.cwd()
        path = _canonical_project_root(cwd_path) / ".episteme" / "reasoning-surface.json"
        if not path.is_file():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _redact(cmd: str) -> str:
    """Crude secret-redaction — command_executed must not carry tokens.

    Not a replacement for proper secret scanning. Catches obvious shapes
    (password=/token=/api_key=/secret=/bearer=/:, AWS-style keys, GitHub
    PATs) and leaves everything else alone. The write-never-writes-secrets
    rule in MEMORY_ARCHITECTURE.md is enforced defensively here; the
    primary fix for a leaked secret is the agent not emitting it in the
    first place.
    """
    if not cmd:
        return cmd
    patterns = [
        # key-value secret patterns — capture the key + separator, replace
        # only the value. Prior version evaluated the replacement at module
        # load time and appended "=<REDACTED>" after the full match, leaving
        # the secret intact.
        (re.compile(r"(?i)((?:password|passwd|token|secret|api[_-]?key|bearer))(\s*[=:]\s*)\S+"),
         r"\1\2<REDACTED>"),
        (re.compile(r"AKIA[0-9A-Z]{16}"), "<REDACTED-AWS-KEY>"),
        (re.compile(r"(?i)ghp_[a-z0-9]{30,}"), "<REDACTED-GH-TOKEN>"),
    ]
    redacted = cmd
    for pat, repl in patterns:
        redacted = pat.sub(repl, redacted)
    return redacted


def _build_record(payload: dict, cmd: str, hits: list[str]) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    cwd = _cwd(payload)
    exit_code = _extract_exit_code(payload)
    status = _extract_status(payload)
    correlation_id = _correlation_id(payload, cmd, ts)
    session_id = _session_id(payload, ts)
    surface = _read_reasoning_surface(cwd)
    redacted_cmd = _redact(cmd)

    summary = f"bash: {hits[0] if hits else 'unknown'}"
    if exit_code is not None:
        summary += f" (exit {exit_code})"
    elif status and status != "unknown":
        summary += f" ({status})"
    # Respect the schema's 500-char summary cap.
    if len(summary) > 500:
        summary = summary[:497] + "..."

    details: dict[str, Any] = {
        "tool": "Bash",
        "command": redacted_cmd,
        "cwd": cwd,
        "exit_code": exit_code,
        "status": status,
        "high_impact_patterns_matched": hits,
    }
    if surface is not None:
        # Snapshot — not a reference — because the Surface file rolls over.
        # `knowns` is required by the phase-12 profile-audit loop (Axis C
        # S1 scans it for constraint-reconstruction evidence). Omitting it
        # makes fence_discipline uncheckable against real records, so this
        # snapshot must stay in lockstep with the profile-audit signatures.
        details["reasoning_surface"] = {
            "core_question": surface.get("core_question"),
            "knowns": surface.get("knowns"),
            "unknowns": surface.get("unknowns"),
            "assumptions": surface.get("assumptions"),
            "disconfirmation": surface.get("disconfirmation"),
            "domain": surface.get("domain"),
            "tacit_call": surface.get("tacit_call"),
            "timestamp": surface.get("timestamp"),
        }

    # Confidence on the provenance: high when surface present + exit code
    # observed; medium when either is missing; low when neither.
    have_surface = surface is not None
    have_exit = exit_code is not None
    if have_surface and have_exit:
        provenance_conf = "high"
    elif have_surface or have_exit:
        provenance_conf = "medium"
    else:
        provenance_conf = "low"

    return {
        "id": str(uuid.uuid4()),
        "memory_class": "episodic",
        "summary": summary,
        "details": details,
        "provenance": {
            "source_type": "agent",
            "source_ref": "core/hooks/episodic_writer.py",
            "captured_at": ts,
            "captured_by": "episodic_writer",
            "confidence": provenance_conf,
            "evidence_refs": [f"correlation_id:{correlation_id}"],
        },
        "status": "active",
        "version": "memory-contract-v1",
        "tags": ["high-impact", "bash"] + hits,
        "session_id": session_id,
        "event_type": "action",
    }


def _append_record(record: dict) -> None:
    ts = record["provenance"]["captured_at"]
    path = _episodic_path(ts)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _should_record(payload: dict) -> tuple[bool, str, list[str]]:
    """Trigger logic. Returns (should_record, cmd, matched_patterns)."""
    if _tool_name(payload) != "Bash":
        return False, "", []
    cmd = _bash_command(payload)
    if not cmd:
        return False, "", []
    hits = _matched_high_impact(cmd)
    if not hits:
        return False, cmd, []
    return True, cmd, hits


def _hook_log_path() -> Path:
    """Persistent per-invocation log at ~/.episteme/state/hooks.log.
    Unconditional. Loud failure mode — 2026-04-23 Path-A hotfix
    replacing the prior `except Exception: pass` that made the writer
    appear functional in code while producing zero records for 3 days
    of real PostToolUse firings. Every invocation appends exactly one
    line; file rotates by hand if it gets too large (not expected in
    practice given 21 high-impact pattern regexes and mostly-skipped
    invocations).
    """
    return Path.home() / ".episteme" / "state" / "hooks.log"


def _log_line(msg: str) -> None:
    """Append one line to the per-invocation log. Never throws; if the
    log directory is unwritable the line goes to stderr as a fallback
    (Claude Code may surface stderr; it definitely surfaces a missing
    log file)."""
    ts = datetime.now(timezone.utc).isoformat()
    line = f"{ts} episodic_writer {msg}\n"
    try:
        path = _hook_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        # Fallback — if even the log path is unwritable, surface to
        # stderr so Claude Code's runtime may capture it. This path
        # should be unreachable in a healthy install; if it fires,
        # the user's ~/.episteme/ filesystem is itself broken.
        try:
            sys.stderr.write(line)
        except OSError:
            pass


def _verbose_enabled() -> bool:
    """Extra traceback detail on exceptions. Opt-in via
    EPISTEME_EPISODIC_DEBUG=1. The one-line invocation log above is
    always-on; this adds multi-line traceback for exceptions when
    requested."""
    return os.environ.get("EPISTEME_EPISODIC_DEBUG", "").strip() not in ("", "0", "false", "False")


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            _log_line("invocation: stdin empty")
            return 0
        payload = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        _log_line(f"invocation: payload parse failed — {type(exc).__name__}: {exc}")
        return 0

    try:
        record_it, cmd, hits = _should_record(payload)
        if not record_it:
            tool = _tool_name(payload)
            event = str(payload.get("hook_event_name") or payload.get("hookEventName") or "?")
            _log_line(
                f"skipped: event={event} tool={tool!r} "
                f"cmd_prefix={cmd[:40]!r} hits={hits}"
            )
            return 0
        record = _build_record(payload, cmd, hits)
        _append_record(record)
        _log_line(
            f"wrote: id={record['id'][:8]} hits={hits} "
            f"path={_episodic_path(record['provenance']['captured_at'])}"
        )
    except Exception as exc:
        _log_line(f"EXCEPTION: {type(exc).__name__}: {exc}")
        if _verbose_enabled():
            import traceback
            for line in traceback.format_exc().splitlines()[-6:]:
                _log_line(f"  traceback: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
