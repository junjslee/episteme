---
name: progress-handoff
description: Update progress and next-step docs so the next agent or session can resume with minimal context loss.
---
Use this skill near the end of a work session or after substantial progress.

**Convention check first:** if the project's `AGENTS.md` (or operating contract)
declares its own handoff convention — different file names, a different form —
**follow the project's declaration**. Repo files own repo mechanics; the two
moves below are the episteme default for projects that declare none.

Handoff is two moves, and only two:

1. **REPLACE `docs/NEXT_STEPS.md`.** Overwrite it with the current state — do not
   append. Include:
   - status (where things stand now, in one line: the "So-What Now?")
   - blockers / open unknowns
   - the exact next commands to run
   Keep it under ~10KB. Never append a "prior resume" block — append-stacks rot,
   and stacking them back up is the accretion disease this contract removed.

2. **Append exactly ONE line to `docs/EVENTS.md`** — one row in the history
   index (`| E<N> | date | one-line what happened | refs |`). Nothing more; no
   narrative body. Verbatim detail, if it must be kept, goes in `archive/`.

`docs/PROGRESS.md` is **retired** in this pattern. Do not create it and do not
write to it — its append-log shape was the disease compaction cured. The
one-line-per-event index (`EVENTS.md`) plus the REPLACE-form `NEXT_STEPS.md`
carry everything it used to.

Favor concise operational handoffs over narrative summaries.
