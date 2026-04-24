# Prepared Patches — v1.0.1 Hook Fixes (Event 47)

Soak-sensitive fixes that require `core/hooks/` edits. Diagnosed and
written here during Event 47 but **deliberately not committed** to
preserve the Event-38 fresh soak clock. Operator applies post-soak
(v1.0.1) OR — if calibration telemetry is judged load-bearing for
Day-7 grading — mid-soak with explicit Path-A-class authorization.

Apply after the Day-7 grading produces its baseline, not before —
the patched hooks will start producing correct data, and grading
against a mixed pre/post-patch corpus is harder to reason about
than grading the pre-patch corpus as-is.

---

## CP-TEL-01 — exit_code extraction camelCase fix

**Root cause** (confirmed Event 47 via `core/hooks/calibration_telemetry.py`
lines 66-90 + `core/hooks/fence_synthesis.py` lines 60-92): both
hooks' `_extract_exit_code()` and `_extract_status()` look for
snake_case keys on `tool_response` (`is_error`, `exit_code`,
`returncode`, …). Claude Code's Bash tool_response uses camelCase
`isError` + `stdout` / `stderr` / `interrupted`, and does NOT include
a numeric `exit_code` field at all.

Evidence: 3,357 predictions logged vs 80 outcomes captured across
5 days (42× gap). Of the 80 outcomes captured, 80/80 have
`exit_code: null` and `status: "unknown"`. Consistent with the
extraction logic finding zero matches in the payload's
tool_response.

**Symmetric hook-level handling** for camelCase already exists on
`tool_name` / `tool_input` keys (see `_tool_name()` / `_tool_input()`
helpers) — the authors knew about the duality. It's a code-inconsistency
bug, not a design limitation.

### Prepared diff — `core/hooks/calibration_telemetry.py`

Replace the `_extract_exit_code` function body with:

```python
def _extract_exit_code(payload: dict) -> int | None:
    """Walk the tool_response structure for a numeric exit code.

    Claude Code's Bash tool_response provides `isError` (camelCase
    bool) — 0 on False, 1 on True. Other runtimes may provide
    explicit numeric exit codes. This handles both shapes.
    """
    resp = (
        payload.get("tool_response")
        or payload.get("toolResponse")
        or {}
    )
    if not isinstance(resp, dict):
        return None
    for key in (
        "exit_code", "exitCode", "returncode", "return_code",
        "status_code",
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
                "exit_code", "exitCode", "returncode", "return_code",
            ):
                v = wrapper.get(key)
                if isinstance(v, int):
                    return v
    # Claude Code shape — map isError / is_error bool to 0 or 1.
    for bool_key in ("isError", "is_error"):
        if bool_key in resp:
            return 1 if resp[bool_key] else 0
    return None
```

And the `_extract_status` function:

```python
def _extract_status(payload: dict) -> str:
    """Best-effort status string: 'success' / 'error' / 'unknown'."""
    resp = (
        payload.get("tool_response")
        or payload.get("toolResponse")
        or {}
    )
    if not isinstance(resp, dict):
        return "unknown"
    for bool_key in ("isError", "is_error"):
        if bool_key in resp:
            return "error" if resp[bool_key] else "success"
    if "error" in resp and resp["error"]:
        return "error"
    s = resp.get("status")
    if isinstance(s, str) and s:
        return s.lower()
    return "unknown"
```

### Prepared diff — `core/hooks/fence_synthesis.py`

Same pattern — replace `_extract_exit_code` body with the block above
(the fence hook's version already had the `is_error` fallback; add
`isError` variant next to it).

### Verification procedure

After applying:

1. Run any Bash command via Claude Code.
2. `tail -1 ~/.episteme/telemetry/$(date -u +%F)-audit.jsonl | jq .`
3. Confirm `exit_code` is `0` (not `null`) and `status` is `"success"`
   (not `"unknown"`).
4. Run 10 commands; confirm 10 outcomes with valid exit codes.
5. Retire the `100% null exit_code` blocker on Gate 22 grading.

---

## CP-FENCE-01 — fence synthesis empty-emit + orphan markers

**Root cause** (confirmed Event 47):
1. **Downstream of CP-TEL-01.** `fence_synthesis.finalize_on_success()`
   writes a protocol iff `exit_code == 0`. Exit code is None for every
   invocation, so the `if exit_code == 0:` branch never fires. Fix
   CP-TEL-01 → fence synthesis starts producing.
2. **Orphan markers.** `~/.episteme/state/fence_pending/` contains 88
   `h_*.json` marker files from the pre-fix era when `tool_use_id`
   was not present in PreToolUse payloads and the correlation_id fell
   back to the SHA-1 hash. PostToolUse then computed a different
   correlation_id (from `toolu_*`), never found the marker, never
   called `delete_pending_marker()`. Each orphan is tiny but they
   accumulate.

### Prepared fix A — unblock protocol writes

**No code change needed.** Fix CP-TEL-01 and fence synthesis starts
working. Verify by:

1. Run any high-impact Bash command that fires fence_reconstruction.
2. Check `~/.episteme/framework/protocols.jsonl` exists after the
   command.
3. Gate 26 grading: `python3 tools/grade_gates.py` should report
   Gate 26 as PARTIAL (≥ 1 protocol) or PASS (≥ 1 reasoning-shape
   protocol).

### Prepared fix B — orphan-marker cleanup (optional)

Add a small tool that walks `fence_pending/` and deletes markers
whose `written_at` is > 24 hours old (existing TTL). Either:

**Option B-1**: Standalone cleanup script at
`tools/fence_marker_cleanup.py`:

```python
#!/usr/bin/env python3
"""One-shot cleanup of stale fence_pending markers beyond TTL."""
from pathlib import Path
from datetime import datetime, timezone
import json, sys

MARKER_TTL_SECONDS = 24 * 60 * 60
pending = Path.home() / ".episteme" / "state" / "fence_pending"
now = datetime.now(timezone.utc)
removed = 0
for p in pending.glob("*.json"):
    try:
        with open(p) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        p.unlink(missing_ok=True); removed += 1; continue
    written = data.get("written_at", "")
    try:
        age = (now - datetime.fromisoformat(written.replace("Z", "+00:00"))).total_seconds()
    except ValueError:
        age = float("inf")
    if age > MARKER_TTL_SECONDS:
        p.unlink(missing_ok=True)
        removed += 1
print(f"removed {removed} stale markers", file=sys.stderr)
```

**Option B-2**: Inline sweep at top of `fence_synthesis.py` main() —
walks pending/ and deletes stale markers on each invocation. Bounded
cost (typical dir size < 100 files).

Recommend Option B-1 for a v1.0.1 that doesn't re-edit hot-path code.

### Verification procedure

1. Before: `ls ~/.episteme/state/fence_pending/ | wc -l` reports 89+.
2. Run `python3 tools/fence_marker_cleanup.py` (or re-run hook 24h
   after applying Option B-2).
3. After: only markers < 24h old remain.

---

## CP-DEDUP-01 — deferred-discovery dedup on log (NEW — Event 47)

**Observation** (Phase 2 triage): 1,294 deferred_discoveries records
collapse to 40 unique findings. 32× dup rate. Cause: every
`cascade:architectural` firing re-logs identical `deferred_discovery`
entries without checking whether the same finding already exists.

**Prepared fix** — add a pre-write dedup check in the framework
writer. Candidate location: wherever `deferred_discoveries[]`
entries are chained into the framework stream (likely in
`core/hooks/_framework.py` or the cascade detector). Write
pseudocode:

```python
def append_deferred_discovery(new: dict, framework_path: Path) -> bool:
    """Return True if written, False if suppressed as duplicate."""
    new_class = new.get("flaw_classification", "")
    new_desc = (new.get("description") or "")[:120]
    # Walk last N entries (bounded; full scan is O(n) per write)
    cutoff = max(0, total_entries - 200)  # check last 200 only
    for existing in tail_entries(framework_path, n=200):
        existing_payload = existing.get("payload", {})
        if existing_payload.get("type") != "deferred_discovery":
            continue
        if (existing_payload.get("flaw_classification", "") == new_class
                and (existing_payload.get("description") or "")[:120]
                    == new_desc):
            return False  # duplicate
    append_chained(framework_path, new)
    return True
```

**Design constraint**: cannot break chain integrity — append must
still produce valid hash-chained entries. Dedup suppression is the
write-path behavior, not a chain-level change.

### Verification procedure

1. Pre-fix: count records per day in deferred_discoveries.jsonl.
2. Apply fix.
3. Post-fix: new records only when description/class actually novel.
   Monitor for 24 hours; expect <10 new records vs pre-fix ~70/day.

---

## CP-PHASE12-01 — operator action

**Resolved Event 47** (see POST_SOAK_TRIAGE §1.5). No code change
needed. Operator action required before Day-7 grading:

```bash
episteme profile audit --write
```

This writes to `~/.episteme/memory/reflective/profile_audit.jsonl`.
Gate 25 grades against that file.

---

## Application order recommendation

When the operator is ready to apply these (post-soak or
Path-A-authorized mid-soak):

1. **CP-PHASE12-01** — operator runs `episteme profile audit
   --write` (no code change).
2. **CP-TEL-01** — apply the exit_code/status patches. Verify
   non-null outcomes start appearing.
3. **CP-FENCE-01** — no code change (downstream of #2); verify
   protocols.jsonl starts populating. Then run the orphan cleanup
   script once.
4. **CP-DEDUP-01** — design + apply the dedup check. Requires
   design review for the tail-scan bound.
5. **Re-run Phase 1 grading**. Gates 22, 25, 26 should materially
   move.

## Risk assessment

| Patch | Soak impact if applied mid-soak | Effort |
|---|---|---|
| CP-TEL-01 | LOW — adds keys to extraction; cannot break existing data | 30 min |
| CP-FENCE-01 A | LOW — downstream of CP-TEL-01, no own code change | 0 min |
| CP-FENCE-01 B-1 | NONE — standalone cleanup script, run once | 30 min |
| CP-DEDUP-01 | MEDIUM — modifies framework write path; test required | 2-4 hrs |
| CP-PHASE12-01 | NONE — operator CLI invocation only | 5 min |

Total to unblock Gates 22, 25, 26: ~1 hour of operator time +
diff review.
