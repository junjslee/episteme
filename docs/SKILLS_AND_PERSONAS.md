<!-- episteme-lifecycle: status=living; reviewed_as_of=E153 -->
# Skills and Agent Personas

Two extension surfaces shipped with episteme: **skills** (reusable operator capabilities) and **personas** (subagent definitions). Both propagate via `episteme sync`.

## Skills

### Custom (your own)

`epistemic-interrogation` · `reasoning-surface` · `episteme-event` · `overnight-loop` · `progress-handoff` · `repo-bootstrap`

(E153 usage-based triage: `requirements-to-plan`, `worktree-split`, `bounded-loop-runner`, `review-gate`, `research-synthesis` retired — absorbed by `kickoff`, `episteme-event`, `overnight-loop`, or dormant with zero invocations.)

### Vendor (curated upstream)

`swing-clarify` · `swing-research` · `swing-review` · `swing-mortem`

(E153: the zero-use vendor tail — `swing-options`, `swing-trace`, and the seven-skill PM pack — was pruned; `swing-mortem` absorbs `pre-mortem`, which was the same Gary Klein technique imported twice.)

### Adding your own

Drop a folder under `skills/custom/` with a `SKILL.md`. Experimental skills that should never sync globally live under `skills/private/` — that directory's name encodes a **sync-exemption boundary** (skills there are tracked publicly but not propagated by `episteme sync`), distinct from the `~/episteme-private/` symlink pattern used for operator-private profile content.

### Vendor skill provenance (inspired, not copied)

- Required vendor attribution map: `skills/vendor/SOURCES.md`.
- Every vendor skill should include a `## Provenance` section in its `SKILL.md` when imported or adapted.
- Run `episteme validate` to surface manifest or provenance warnings before shipping.

## Agent personas

Eleven subagent definitions install into `~/.claude/agents/` on sync.

**Execution:** `planner` · `researcher` · `implementer` · `reviewer` · `test-runner` · `docs-handoff`.

**Structural governance:** `domain-architect` · `reasoning-auditor` · `governance-safety` · `orchestrator` · `domain-owner`.

Every delegated task begins with a **Shared Context Brief** and ends with a **Verification Artifact** — see the workflow convention in [`../AGENTS.md`](../AGENTS.md).
