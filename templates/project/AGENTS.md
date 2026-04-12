# Agent Operating Manual

## Purpose
This file is the vendor-neutral operating manual for agents working in this repository.

## Required Memory Files
Read in this order at session start:
- `docs/NEXT_STEPS.md` — current priority and next actions
- `docs/PROGRESS.md` — current state and key decisions
- `HARNESS.md` — project harness: execution profile, workflow constraints, safety rules (if present)
Read on demand:
- `CLAUDE.md`
- `docs/REQUIREMENTS.md`
- `docs/PLAN.md`
- `docs/RUN_CONTEXT.md`

## Workflow
1. Read project memory before planning or code changes.
2. Clarify the active objective in `docs/REQUIREMENTS.md`.
3. Update `docs/PLAN.md` before substantial implementation.
4. Track completed work, decisions, and validation in `docs/PROGRESS.md`.
5. Keep `docs/NEXT_STEPS.md` current as the handoff for the next session.
6. Use git worktrees for non-trivial parallel work, with one bounded objective per worktree.
7. Use Conventional Commits for final commit messages.

## Worktree Naming
- `feat/<name>` — new feature
- `fix/<name>` — bug fix
- `research/<name>` — investigation or query work
- `ops/<name>` — infra, scripts, tooling
- `docs/<name>` — documentation handoff

## Guardrails
- Prefer the smallest useful verification step first.
- Do not duplicate large prompt blocks in chat when they belong in project memory.
- Record environment limits, APIs, and rate limits in `docs/RUN_CONTEXT.md`.
- Keep `CLAUDE.md` short — use it as an index into live docs, not a content store.

## Bounded Automation
When running any unattended or semi-attended loop, record before starting:
- objective
- candidate set or input parameters
- max iterations or time limit
- evaluation rubric
- expected artifact outputs
- stop condition
- human review checkpoint

No unattended code-writing, auto-merge, or production-promotion loops.

## Review Gate
Review is required before merge for:
- logic changes to core domain code
- data pipeline or artifact generation changes
- any change that touches shared production artifacts

## Logging
Use `agent_logs/action_log.md` for substantive runs only:
remote executions, cleanup passes, bounded loops, major audits, branch handoffs.
Do not log every shell command. Source of truth remains `docs/PROGRESS.md`.

## Publication Boundary
Safe to commit:
- `AGENTS.md`, `CLAUDE.md`, `docs/*.md`, shared runtime files, code, tests, research artifacts.

Keep local only:
- `.claude/settings.local.json`, user auth, trust settings, `.env*`, `secrets/`, private keys, large local datasets.

## Runtime Policy
- `agent-os` is the source of truth for the project scaffold.
- Local Python-backed `agent-os` work runs in Conda `base` at `{{CONDA_ROOT}}`.
- Homebrew Python is not the supported runtime for `agent-os`.
