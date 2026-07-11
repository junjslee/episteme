# Hooks → Kernel Mapping

Which runtime hook enforces which kernel invariant. Adapters register these hooks into the host runtime's PreToolUse / PostToolUse / SessionStart / Stop events.

## Kernel element → enforcing hook

| Kernel element | Hook | Event | Enforcement |
|---|---|---|---|
| Constraint regime — forbidden actions | `block_dangerous.py` | PreToolUse/Bash | hard block on rm -rf, force push, sudo, mkfs, etc. |
| Reasoning Surface — presence before high-impact op | `reasoning_surface_guard.py` | PreToolUse/Bash\|Write\|Edit\|MultiEdit | **blocks by default** (exit 2) when `.episteme/reasoning-surface.json` is missing, stale, incomplete, or contains lazy placeholders (none, n/a, tbd, 해당 없음, ...). Command text is normalized to catch `subprocess.run(['git','push'])` / `os.system('git push')` bypass shapes. Opt-out per-project: `touch .episteme/advisory-surface`. |
| Frame stage — session boot context | `session_context.py` | SessionStart | prints git state, NEXT_STEPS, and Reasoning Surface status |
| Execute stage — docs alignment advisory | `workflow_guard.py` | PreToolUse/Write\|Edit\|MultiEdit | nudges agent to keep docs/PLAN.md, docs/EVENTS.md, and docs/NEXT_STEPS.md aligned |
| Execute stage — prompt-injection defense | `prompt_guard.py` | PreToolUse/Write\|Edit\|MultiEdit | flags suspicious patterns in docs/, AGENTS.md, CLAUDE.md |
| Execute stage — context pressure awareness | `context_guard.py` | PostToolUse | warns when compaction is near |
| Verify stage — tests | `test_runner.py` | PostToolUse | runs affected tests after edits |
| Verify stage — gate | `quality_gate.py` | Stop | opt-in pytest gate (presence of `.quality-gate`) |
| Handoff stage — git snapshot | `checkpoint.py` | Stop / SubagentStop | auto-commits session state |
| Memory preservation | `precompact_backup.py` | PreCompact | backs up memory before compaction |

## Reasoning Surface state file

Path: `.episteme/reasoning-surface.json` in project cwd.

```
{
  "timestamp": "2026-04-17T14:00:00Z",
  "core_question": "<one question this work answers>",
  "knowns": ["..."],
  "unknowns": ["..."],
  "assumptions": ["..."],
  "disconfirmation": "<what evidence would prove this wrong>"
}
```

TTL: 30 minutes. Any high-impact op (git push, publish, migrations, cloud deletes, DB DROP, lockfile edits) requires a fresh Surface. **Missing / stale / incomplete / lazy → hard block (exit 2).** Validator enforces: `disconfirmation` and each `unknowns` entry must be ≥ 15 chars and must not match the lazy-token blocklist (`none`, `n/a`, `tbd`, `nothing`, `null`, `해당 없음`, `없음`, `모름`, `-`, ...). To downgrade to advisory mode for a specific project, create `.episteme/advisory-surface`. The legacy `.episteme/strict-surface` marker is a no-op (strict is now the default).

## Integrity manifest

`kernel/MANIFEST.sha256` tracks sha256 of every managed kernel file. Regenerate after intentional kernel edits:

```
episteme kernel update
episteme kernel verify
```

`episteme doctor` surfaces drift as a non-blocking warning.
