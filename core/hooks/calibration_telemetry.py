#!/usr/bin/env python3
"""PostToolUse hook: record the observed exit_code for calibration telemetry.

Pairs with `reasoning_surface_guard.py`. The PreToolUse guard writes a
`prediction` record to `~/.episteme/telemetry/YYYY-MM-DD-audit.jsonl` when a
high-impact Bash command is allowed through. This hook fires after the same
tool call completes and appends the matching `outcome` record carrying the
exit code.

Join key: `correlation_id` — derived from `tool_use_id` when present,
otherwise a SHA-1 over (second-bucket, cwd, cmd) so the two hooks produce
the same id for the same call.

Records are append-only JSONL, local-only, and strictly opt-in to external
use. Episteme never transmits them; they exist so an operator can audit
whether their predicted disconfirmations actually fired.

This hook must never block. Any exception → return 0.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def _redact(cmd: str) -> str:
    """Crude secret-redaction — command_executed must not carry tokens.

    Inlined (not imported from episodic_writer) because the hook is invoked
    as a standalone script with no guaranteed sys.path. If this pattern set
    diverges from episodic_writer._redact, unify by editing both.
    """
    if not cmd:
        return cmd
    patterns = [
        (re.compile(r"(?i)((?:password|passwd|token|secret|api[_-]?key|bearer))(\s*[=:]\s*)\S+"),
         r"\1\2<REDACTED>"),
        (re.compile(r"AKIA[0-9A-Z]{16}"), "<REDACTED-AWS-KEY>"),
        (re.compile(r"(?i)ghp_[a-z0-9]{30,}"), "<REDACTED-GH-TOKEN>"),
    ]
    redacted = cmd
    for pat, repl in patterns:
        redacted = pat.sub(repl, redacted)
    return redacted


def _tool_name(payload: dict) -> str:
    return str(payload.get("tool_name") or payload.get("toolName") or "").strip()


def _tool_input(payload: dict) -> dict:
    raw = payload.get("tool_input") or payload.get("toolInput") or {}
    return raw if isinstance(raw, dict) else {}


def _bash_command(payload: dict) -> str:
    ti = _tool_input(payload)
    return str(ti.get("command") or ti.get("cmd") or ti.get("bash_command") or "")


_RCI_EXIT_CODE_PATTERN = re.compile(r"exit\s+code\s+(-?\d+)", re.IGNORECASE)


def _extract_exit_code(payload: dict) -> int | None:
    """Walk the tool_response structure for a numeric exit code.

    Different runtimes spell this differently. This tries the common shapes
    and returns None if none match — the outcome record still carries a
    best-effort success/failure signal via `status`.

    Event 49 · CP-TEL-01 — Claude Code's Bash tool_response uses a
    different signalling pattern than documented runtime conventions.
    Actual keys observed: `returnCodeInterpretation` (None on success /
    non-empty string on error), `interrupted` (bool), `stdout`, `stderr`,
    `isImage`, `noOutputExpected`. No numeric `exit_code` field. This
    extractor:
      - Returns `0` when `returnCodeInterpretation` is absent/None AND
        `interrupted` is not True.
      - Tries to extract N from patterns like "exit code 127" in rci;
        falls back to 1 if rci is non-empty but unparseable.
      - Returns 130 on `interrupted: True` (SIGINT convention).
    Snake_case `is_error` / camelCase `isError` preserved for other
    runtimes / tests.
    """
    resp = payload.get("tool_response") or payload.get("toolResponse") or {}
    if not isinstance(resp, dict):
        return None
    for key in ("exit_code", "exitCode", "returncode", "return_code", "status_code"):
        v = resp.get(key)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.strip().lstrip("-").isdigit():
            return int(v.strip())
    # Some runtimes nest under a `metadata` or `meta` key.
    for wrapper_key in ("metadata", "meta"):
        wrapper = resp.get(wrapper_key)
        if isinstance(wrapper, dict):
            for key in ("exit_code", "exitCode", "returncode", "return_code"):
                v = wrapper.get(key)
                if isinstance(v, int):
                    return v
    # Event 49 · CP-TEL-01 — isError bool mapping for runtimes that use
    # it (Gemini CLI, some test payloads).
    for bool_key in ("isError", "is_error"):
        if bool_key in resp and isinstance(resp[bool_key], bool):
            return 1 if resp[bool_key] else 0
    # Event 49 · CP-TEL-01 — Claude Code pattern. Only reached when no
    # other shape matched.
    rci = resp.get("returnCodeInterpretation")
    interrupted = resp.get("interrupted")
    has_claude_code_shape = any(
        k in resp for k in ("returnCodeInterpretation", "interrupted", "isImage")
    )
    if has_claude_code_shape:
        if interrupted is True:
            return 130  # SIGINT convention
        if rci is None or (isinstance(rci, str) and not rci.strip()):
            return 0
        if isinstance(rci, str):
            m = _RCI_EXIT_CODE_PATTERN.search(rci)
            if m:
                try:
                    return int(m.group(1))
                except ValueError:
                    pass
            return 1
    return None


def _extract_status(payload: dict) -> str:
    """Best-effort status string: 'success' / 'error' / 'unknown'.

    Event 49 · CP-TEL-01 — recognizes Claude Code's returnCodeInterpretation
    + interrupted pattern alongside snake_case/camelCase conventions.
    """
    resp = payload.get("tool_response") or payload.get("toolResponse") or {}
    if not isinstance(resp, dict):
        return "unknown"
    for bool_key in ("isError", "is_error"):
        if bool_key in resp and isinstance(resp[bool_key], bool):
            return "error" if resp[bool_key] else "success"
    if "error" in resp and resp["error"]:
        return "error"
    s = resp.get("status")
    if isinstance(s, str) and s:
        return s.lower()
    # Event 49 · CP-TEL-01 — Claude Code pattern.
    if any(
        k in resp for k in ("returnCodeInterpretation", "interrupted", "isImage")
    ):
        if resp.get("interrupted") is True:
            return "error"
        rci = resp.get("returnCodeInterpretation")
        if rci is None or (isinstance(rci, str) and not rci.strip()):
            return "success"
        return "error"
    return "unknown"


def _correlation_id(payload: dict, cmd: str, ts: str) -> str:
    rid = payload.get("tool_use_id") or payload.get("toolUseId") or payload.get("request_id")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    cwd = str(payload.get("cwd") or os.getcwd())
    bucket = ts.split(".")[0]
    seed = f"{bucket}|{cwd}|{cmd}".encode("utf-8", errors="replace")
    return "h_" + hashlib.sha1(seed).hexdigest()[:16]


def _telemetry_path(ts: str) -> Path:
    return Path.home() / ".episteme" / "telemetry" / f"{ts[:10]}-audit.jsonl"


def _write_telemetry(record: dict) -> None:
    try:
        path = _telemetry_path(record["ts"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except (OSError, KeyError):
        pass


def _hook_log(msg: str) -> None:
    """Persistent per-invocation log (Path-A Event 39 follow-up to
    Event 36's loud-failure-mode pattern). Writes to
    ~/.episteme/state/hooks.log; never raises."""
    try:
        from datetime import datetime as _dt, timezone as _tz
        from pathlib import Path as _Path
        path = _Path.home() / ".episteme" / "state" / "hooks.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{_dt.now(_tz.utc).isoformat()} calibration_telemetry {msg}\n")
    except OSError:
        pass


def main() -> int:
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            _hook_log("invocation: stdin empty")
            return 0
        payload = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        _hook_log(f"invocation: payload parse failed — {type(exc).__name__}: {exc}")
        return 0

    try:
        tool = _tool_name(payload)
        if tool != "Bash":
            _hook_log(f"skipped: tool={tool!r}")
            return 0
        cmd = _bash_command(payload)
        if not cmd:
            _hook_log("skipped: empty cmd")
            return 0
        ts = datetime.now(timezone.utc).isoformat()
        correlation = _correlation_id(payload, cmd, ts)
        record = {
            "ts": ts,
            "event": "outcome",
            "correlation_id": correlation,
            "tool": "Bash",
            "cwd": str(payload.get("cwd") or os.getcwd()),
            "command_executed": _redact(cmd),
            "exit_code": _extract_exit_code(payload),
            "status": _extract_status(payload),
        }
        _write_telemetry(record)
        _hook_log(f"wrote outcome: correlation={correlation[:16]} exit={record['exit_code']} status={record['status']}")
        # CP8 — spot-check sampling at PostToolUse. Idempotent-by-
        # correlation-id: if `fence_synthesis.py` already queued an
        # entry for this id (with richer synthesis_produced signal),
        # this call is a no-op via maybe_sample's dedupe check. For
        # non-Fence ops the fence hook bailed early; this path is the
        # primary sampler.
        try:
            _hooks_dir = Path(__file__).resolve().parent
            if str(_hooks_dir) not in sys.path:
                sys.path.insert(0, str(_hooks_dir))
            from _spot_check import (  # type: ignore  # pyright: ignore[reportMissingImports]
                build_post_context,
                maybe_sample,
            )
            ctx = build_post_context(correlation)
            if ctx is not None:
                maybe_sample(
                    correlation_id=correlation,
                    op_label=ctx["op_label"],
                    blueprint=ctx["blueprint"],
                    context_signature=ctx["context_signature"],
                    surface_snapshot=ctx["surface_snapshot"],
                    synthesis_produced=False,
                    cwd=ctx["cwd"],
                )
        except Exception as spot_exc:
            _hook_log(f"spot-check EXCEPTION: {type(spot_exc).__name__}: {spot_exc}")
    except Exception as exc:
        _hook_log(f"EXCEPTION: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
