# Claude Adapter

The Claude adapter is the most fully-featured surface in episteme. It installs your identity, memory, skills, safety hooks, and subagent definitions into Claude Code — so every session starts with full context instead of a blank slate.

## What it does

`episteme sync` installs the Claude runtime into `~/.claude`:

- `~/.claude/CLAUDE.md` — memory index pointing to your global episteme memory files
- `~/.claude/settings.json` — permission rules and governance pack hooks
- `~/.claude/agents/*` — eleven subagent definitions (planner, implementer, reviewer, etc.)
- `~/.claude/skills/*` — all managed skills from `skills/custom/` and `skills/vendor/`

Project repos also get `.claude/settings.json` through `episteme bootstrap` — scoped permissions and hooks tailored to that repo.

## Why it matters

Claude Code is the primary orchestration surface for episteme. The Claude adapter is where the contract between your cognitive identity and the live agent is made concrete:

- Your cognitive profile determines how Claude reasons and challenges assumptions.
- Your workflow policy determines how it sequences work and handles handoffs.
- Your safety hooks run deterministically — they can't be overridden by model behavior.

Without the adapter in place, you get a generic Claude session. With it, you get an agent that knows who you are, how you work, and what it's not allowed to do.

## Governance packs

When you run `episteme sync`, you can specify a governance pack:

```bash
episteme sync --governance-pack minimal    # baseline safety hooks only
episteme sync --governance-pack balanced   # default: minimal + advisory hooks
episteme sync --governance-pack strict     # balanced + no generic auto-allow fallback
```

## Hooks installed

The Claude adapter deploys lifecycle hooks that run on every session:

| Hook | Event | Purpose |
|---|---|---|
| `session_context.py` | `SessionStart` | Prints branch, git status, and next steps |
| `block_dangerous.py` | `PreToolUse Bash` | Blocks destructive commands |
| `workflow_guard.py` | `PreToolUse Write\|Edit` | Nudges doc alignment with implementation |
| `format.py` | `PostToolUse Write\|Edit` | Auto-runs ruff / prettier |
| `checkpoint.py` | `Stop` | Auto-commits as `chore(chkpt):` after every turn |
| `quality_gate.py` | `Stop` | Blocks completion if tests fail (opt-in) |
| `conclusion_guard.py` | `UserPromptSubmit` | Detects conclusion-class prompts; sets marker + one factual context line |
| `conclusion_gate.py` | `Stop` | One-shot nudge when a conclusion lands without a fresh interrogation verdict |

## Files managed

| Asset | Location |
|---|---|
| Memory index | `~/.claude/CLAUDE.md` |
| Permission rules | `~/.claude/settings.json` |
| Subagent definitions | `~/.claude/agents/*` |
| Skills | `~/.claude/skills/*` |
| Project permissions | `<project>/.claude/settings.json` |
