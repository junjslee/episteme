<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->
# Deterministic Safety Hooks

Hooks run deterministically — the model cannot override them. Each hook is a named counter to a specific class of unsafe or inconsistent action; together they form the execution-time enforcement layer for kernel invariants.

## Governance packs

Packs are applied via `episteme sync` or `episteme setup --sync`.

| Pack       | Contents                                                                                                   |
|------------|------------------------------------------------------------------------------------------------------------|
| `minimal`  | Baseline safety only: `block_dangerous`, formatter, test runner, checkpoint, quality gate.                 |
| `balanced` | `minimal` + workflow / context / prompt advisories (**default**).                                          |
| `strict`   | `balanced` + removes the generic `PermissionRequest` auto-allow fallback while preserving custom permissions. |

## Hook reference

The default `episteme sync` registers **19 hook scripts** (balanced governance mode)
across the Claude Code event surface. Regenerate this table from the source of
truth — `build_settings()` in `src/episteme/adapters/claude.py` — after any hook
change; it is the actual registry, not this prose.

| Hook | Event · matcher | What it does |
|------|-----------------|--------------|
| `reasoning_surface_guard.py` | `PreToolUse Bash\|Write\|Edit\|MultiEdit` | Blocks high-impact / irreversible ops and architectural-cascade edits that lack a valid Reasoning Surface |
| `block_dangerous.py` | `PreToolUse Bash` | Blocks `rm -rf`, `git reset --hard`, `git push --force`, `sudo`, destructive SQL, and more |
| `_arm_a_pre.py` | `PreToolUse Write\|Edit\|MultiEdit` | Cognitive Arm A pre-snapshot of watched profile/policy files for trajectory diffing |
| `workflow_guard.py` | `PreToolUse Write\|Edit\|MultiEdit` (balanced/strict) | Targeted DOC ADVISORY (E173): names the docs whose citations claim to describe the edited path — the reverse index of `episteme docs map`, derived from citation edges — with lifecycle state; falls back to the generic `EVENTS.md` / `NEXT_STEPS.md` nudge when no doc cites the path (positive system) or the index is unavailable (non-git project, plugin-only install) |
| `prompt_guard.py` | `PreToolUse Write\|Edit\|MultiEdit` (balanced/strict) | Advisory prompt-injection detection when writing durable context |
| `format.py` | `PostToolUse Write\|Edit\|MultiEdit` (async) | Auto-runs `ruff` (Python) / `prettier` (JS/TS) after a file write |
| `test_runner.py` | `PostToolUse Write\|Edit\|MultiEdit` | Runs pytest / jest when the edited file is a test |
| `_arm_a_post.py` | `PostToolUse Write\|Edit\|MultiEdit` | Cognitive Arm A post-record — diffs pre vs post and emits trajectory entries |
| `state_tracker.py` | `PostToolUse Bash` | Records agent-written files for the guard's indirect-exec scan |
| `calibration_telemetry.py` | `PostToolUse Bash` | Writes the outcome record paired to the guard's PreToolUse prediction |
| `episodic_writer.py` | `PostToolUse Bash` | Appends redacted command episodes to the episodic-memory stream |
| `fence_synthesis.py` | `PostToolUse Bash` | Finalizes Fence / constraint-safety protocol markers when the op exits 0 |
| `context_guard.py` | `PostToolUse Bash\|Edit\|Write\|MultiEdit\|Agent\|Task` (balanced/strict) | Advisory warning as session context approaches compaction thresholds |
| `session_context.py` | `SessionStart` | Prints branch, git status, and `NEXT_STEPS.md` at session open (if present) |
| `conclusion_guard.py` | `UserPromptSubmit` | Emits factual context for the v2 Epistemic Engine conclusion trigger |
| `precompact_backup.py` | `PreCompact` (async) | Backs up session transcripts before context compaction |
| `quality_gate.py` | `Stop` | Blocks completion if tests fail (opt-in via `.quality-gate` in project root) |
| `conclusion_gate.py` | `Stop` | One-shot livelock-proof conclusion nudge, fired before checkpoint |
| `checkpoint.py` | `Stop`, `SubagentStop` | Auto-commits uncommitted changes as `chore(chkpt):` after every turn / subagent |

`contract_gate.py` is an opt-in `Stop` hook (not in the default sync set); it runs
declared contract tests when enabled in settings.json with a `contracts/` directory
present — see [`CONTRACT_GATE.md`](./CONTRACT_GATE.md).

**Plugin subset.** The marketplace plugin (`hooks/hooks.json`) ships a **13-hook
subset**: `block_dangerous`, `reasoning_surface_guard`, `workflow_guard`, `format`,
`session_context`, `quality_gate`, `precompact_backup`, `conclusion_guard`,
`conclusion_gate`, `state_tracker`, `calibration_telemetry`, `episodic_writer`,
`fence_synthesis`. The six sync-only hooks (`_arm_a_pre`, `_arm_a_post`,
`test_runner`, `prompt_guard`, `context_guard`, `checkpoint`) are delivered by
`episteme sync` into settings.json.

## Customization

Hook scripts live in `core/hooks/`. They run with whichever Python invoked the CLI (`sys.executable`). Paths resolve dynamically so the same scripts work on any machine. Pin a specific runtime via:

```bash
export EPISTEME_PYTHON_PREFIX=/path/to/prefix    # e.g. ~/miniconda3, .venv
# or pick the binary directly:
export EPISTEME_PYTHON=/path/to/bin/python
```

Set `EPISTEME_REQUIRE_CONDA=1` to enforce Conda `base` in `episteme doctor`.

## Invariant mapping

See [`kernel/HOOKS_MAP.md`](../kernel/HOOKS_MAP.md) for the mapping from kernel invariants to the hooks that enforce them at runtime, and for the Reasoning Surface state file (`.episteme/reasoning-surface.json`) + integrity manifest commands.
