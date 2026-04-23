#!/usr/bin/env python3
"""PostToolUse hook: finalize Fence Reconstruction synthesis on success.

Pairs with `reasoning_surface_guard.py`. When the guard admits a
constraint-removal op under Blueprint B (Fence Reconstruction) with
reversibility = reversible, it writes a pending-synthesis marker to
`~/.episteme/state/fence_pending/<correlation_id>.json`. This
PostToolUse hook fires after the same tool call completes, joins by
`correlation_id`, and — on `exit_code == 0` — appends a
constraint-safety protocol to `~/.episteme/framework/protocols.jsonl`
with `format_version: "cp5-pre-chain"`. CP7 retroactively hash-chains
these entries per Pillar 2.

Rules:

- Only fires on Bash tool calls (Fence's RC scope).
- On `exit_code != 0`: delete the pending marker, do NOT synthesize.
- On missing marker (non-Fence op): no-op.
- On any exception: return 0 — PostToolUse hooks must never block.

Records are append-only JSONL, local-only. Episteme never transmits
them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _fence_synthesis import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    correlation_id as _correlation_id,
    finalize_on_success as _finalize_on_success,
)
import _spot_check  # noqa: E402  # pyright: ignore[reportMissingImports]


def _tool_name(payload: dict) -> str:
    return str(
        payload.get("tool_name") or payload.get("toolName") or ""
    ).strip()


def _bash_command(payload: dict) -> str:
    ti = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(ti, dict):
        return ""
    return str(
        ti.get("command")
        or ti.get("cmd")
        or ti.get("bash_command")
        or ""
    )


def _extract_exit_code(payload: dict) -> int | None:
    """Walk the tool_response for an exit code. Same shape the
    calibration-telemetry hook uses."""
    resp = payload.get("tool_response") or payload.get("toolResponse") or {}
    if not isinstance(resp, dict):
        return None
    for key in (
        "exit_code", "exitCode", "returncode", "return_code", "status_code"
    ):
        v = resp.get(key)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.strip().lstrip("-").isdigit():
            return int(v.strip())
    for wrapper_key in ("metadata", "meta"):
        wrapper = resp.get(wrapper_key)
        if isinstance(wrapper, dict):
            for key in (
                "exit_code", "exitCode", "returncode", "return_code"
            ):
                v = wrapper.get(key)
                if isinstance(v, int):
                    return v
    # No explicit exit_code field — infer from status / is_error.
    if "is_error" in resp:
        return 1 if resp["is_error"] else 0
    status = resp.get("status")
    if isinstance(status, str):
        if status.lower() in ("success", "ok"):
            return 0
        if status.lower() in ("error", "failed", "failure"):
            return 1
    return None


def _hook_log(msg: str) -> None:
    """Persistent per-invocation log mirroring episodic_writer's
    loud-failure-mode approach (2026-04-23 Path-A hotfix). Writes to
    ~/.episteme/state/hooks.log; never raises."""
    try:
        from datetime import datetime as _dt, timezone as _tz
        from pathlib import Path as _Path
        path = _Path.home() / ".episteme" / "state" / "hooks.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{_dt.now(_tz.utc).isoformat()} fence_synthesis {msg}\n")
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
        if _tool_name(payload) != "Bash":
            _hook_log(f"skipped: tool={_tool_name(payload)!r}")
            return 0
        cmd = _bash_command(payload)
        if not cmd:
            _hook_log("skipped: empty cmd")
            return 0
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        correlation = _correlation_id(payload, cmd, ts)
        # Finalize synthesis first so we know whether a protocol was
        # produced. CP8: pass the synthesis signal into the spot-check
        # sampler; the multiplier lands before the sample roll.
        envelope = _finalize_on_success(
            correlation, _extract_exit_code(payload)
        )
        if envelope is not None:
            _hook_log(f"synthesized protocol: correlation={correlation[:16]}")
        try:
            ctx = _spot_check.build_post_context(correlation)
            if ctx is not None:
                _spot_check.maybe_sample(
                    correlation_id=correlation,
                    op_label=ctx["op_label"],
                    blueprint=ctx["blueprint"],
                    context_signature=ctx["context_signature"],
                    surface_snapshot=ctx["surface_snapshot"],
                    synthesis_produced=envelope is not None,
                    cwd=ctx["cwd"],
                )
        except Exception as spot_exc:
            _hook_log(f"spot-check EXCEPTION: {type(spot_exc).__name__}: {spot_exc}")
    except Exception as exc:
        _hook_log(f"EXCEPTION: {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
