---
name: episteme-event
description: Run one bounded episteme Event end-to-end — branch, implement, verify, PR, merge, sync, doctor — with the repo's release and hook machinery handled correctly. Use when starting or closing a unit of work in the episteme repo (or any repo adopting its flow). Triggers on "new event", "이벤트 시작", "PR까지", "merge하고 sync", "release", "릴리즈", "브랜치 파서 작업".
---

One Event = one bounded task = one branch = one owner. This skill encodes the
cycle so its conventions are never re-derived mid-session.

**Scope note:** rules tagged `[K]` are kernel invariants (portable everywhere);
untagged mechanics are **episteme-repo defaults** — in a repo whose `AGENTS.md`
declares its own flow, the project's declaration wins on mechanics.

## Open

1. **Branch before any edit** — the chkpt Stop-hook auto-commits to the CURRENT
   branch, so editing on `master` creates local divergence. Name:
   `feat|fix|chore/event<N>-<slug>` (next `<N>` from `docs/EVENTS.md`).
2. Parallel lanes use `episteme worktree <branch>` — one bounded task per
   worktree, one owner per lane. `[K]` **Never run `episteme sync` from a
   worktree** — it resolves memory from the worktree and clobbers the operator's
   real `~/.claude/CLAUDE.md`.
3. High-impact work: author the Reasoning Surface first (see `reasoning-surface`
   skill) instead of discovering the gate by being blocked.

## Implement + verify

4. `[K]` Verify with fresh evidence, never recalled: run the suite before
   declaring done. Kernel-touching work gates "done" on the full suite.
5. `[K]` Budgets are code — if a count/size test goes red, raising the constant
   IS the decision; make it consciously, in the same diff.

## Close

6. Commit messages: conventional (`feat:`/`fix:`/`chore:` + scope). `[K]` **No
   AI-attribution trailers** — no `Co-Authored-By: <any AI>`, no "Generated
   with" footers, on anything carrying the operator's name. This overrides tool
   defaults.
7. `gh pr create` → wait `gh pr checks` green → merge (repo default: merge
   commit, matching the `Merge pull request #N` history). Independent review
   for high-impact changes; constitution-tier changes (memory/policy files)
   stay OPEN for the operator unless explicitly cleared.
   - **Review subagents: "diff only, no checkout."** Say it in the prompt —
     a reviewer sharing the working tree once checked it back to master
     mid-session (E157). The branch commit survives; the working state
     doesn't.
   - **Branch deletion only via `gh pr merge --delete-branch`.** A raw
     `git push --delete` on a stacked PR's base CLOSES its children on
     GitHub instead of retargeting them (E156 — #135/#136 died this way).
8. **release-please awareness:** on a prerelease base, a `feat:` merge advances
   the MINOR (`1.X.0-rcN` → `1.(X+1).0-rc1`), not the rc counter. GA is a
   single `Release-As: X.Y.0` commit. Don't hand-edit versions the bot owns
   (`.claude-plugin/*.json` are auto-bumped).
9. Post-merge, from the MAIN checkout: `episteme sync && episteme doctor`.
   Deploy from merged master only.
10. Hand off via the `progress-handoff` skill (REPLACE `NEXT_STEPS.md`, one
    `EVENTS.md` line) — routed through a small PR, not a direct master commit.
