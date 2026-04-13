# Skill Labs

This directory is the private experimental area for tuning skills without touching
the live skill set under `skills/house` or `skills/vendor`.

## Workflow
1. Copy a live skill into `labs/skills/<skill-name>/candidate/`.
2. Enable the private Claude-only lab skill:
  - `cognitive-os private-skill enable skill-lab-autoresearch --tool claude`
3. Run the lab skill against the candidate copy, not the live source.
4. Write evaluation outputs and revised drafts into `labs/skills/<skill-name>/runs/`.
5. Review the candidate diff manually.
6. Promote accepted changes into the live skill by explicit manual copy or patch.

## Guardrails
- Never target `skills/house/*` directly.
- Never target `skills/vendor/*` directly.
- Never target synced copies under `~/.claude/skills` or `~/.codex/skills`.
- Candidate and run directories are intentionally ignored by Git.
- This area is private and experimental; it is not part of normal `cognitive-os sync`.
