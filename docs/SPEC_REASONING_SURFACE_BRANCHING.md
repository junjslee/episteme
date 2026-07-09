<!-- episteme-lifecycle: status=spec-implemented; reviewed_as_of=E147 -->
# Spec — Reasoning Surface branching

**Status:** proposed (Tier 2.3 design spec, Event 110, 2026-05-08). Implementation deferred to Tier 3 — see § Implementation path below for decomposition.

**Motivation:** Pi.dev's session-as-tree (`/tree`, branch / fork / clone any prior point) is an ergonomic for "let me try this without polluting the main thread." Episteme's analog is the Reasoning Surface — but today the surface is single-state: one file at `.episteme/reasoning-surface.json`. There is no notion of "hold two surfaces side-by-side because I'm exploring two competing analyses" or "let me probe this change without losing the surface I had for the main thread."

Branching addresses this. A branch is a copy of the surface under a named slot (`.episteme/reasoning-surface.{branch}.json`); the operator can create, switch, abandon, or merge branches; the gate resolves the active branch first and falls back to the default surface only when no branch is active. The kernel's invariants (gate enforcement, schema validation, hash chain) hold at every branch — branching is a topology change to the surface, not an escape from the gate.

---

## Surface

### Filesystem

| Path | Purpose | Lifecycle |
| --- | --- | --- |
| `.episteme/reasoning-surface.json` | The default surface. Always exists once `.episteme/` is initialized. | Permanent. |
| `.episteme/reasoning-surface.{branch}.json` | A named branch surface. `{branch}` is kebab-case alphanumeric (regex: `[a-z0-9][a-z0-9-]{0,63}`). | Created on `branch create`; removed on `branch drop` or after `branch merge`. |
| `.episteme/reasoning-surface.active` | Single line containing the active branch name, OR empty (default branch active). | Always exists once a branch has been created at least once. Empty means default. |
| `.episteme/archive/reasoning-surface.{branch}.{timestamp}.json` | Archive of a branch's last surface state on merge or drop. | Append-only; rotation policy = manual. |

### CLI

```
episteme branch                                    # print active branch + list of branches
episteme branch list                               # one-row-per-branch table (name, mtime, surface validity)
episteme branch create <name> [--from <branch>]    # copy {from-or-active} surface to {name}; switch active to {name}
episteme branch switch <name>                      # set active branch to {name}; '-' switches to default
episteme branch merge <name> [--into default]      # overwrite default with {name}; archive {name}; switch active to default
episteme branch drop <name> [--force]              # remove {name} (after confirmation unless --force); switch active to default if {name} was active
episteme branch diff <a> [<b>]                     # show field-level diff between two branches (default: active vs default)
episteme branch --json                             # machine-readable list (active, branches, validity per branch)
```

---

## Semantics

### Branch creation

```
episteme branch create explore-fence-removal --from default
```

1. Read source surface (`--from` or current active or default).
2. Validate source surface (must pass Blueprint D before branching — branching from an invalid surface refuses).
3. Write to `.episteme/reasoning-surface.explore-fence-removal.json`.
4. Update `.episteme/reasoning-surface.active` to `explore-fence-removal`.
5. Log a chain envelope: `{type: "branch_create", name: "explore-fence-removal", source: "default", timestamp: "..."}`.

### Branch switch

```
episteme branch switch <name>
```

1. Verify `.episteme/reasoning-surface.<name>.json` exists.
2. Verify it validates against Blueprint D (warn but switch on validation failure — operator may be mid-edit).
3. Update `.episteme/reasoning-surface.active`.
4. Log a chain envelope.

The special argument `-` (single dash) switches to default branch (i.e., empties `.episteme/reasoning-surface.active`).

### Branch merge

```
episteme branch merge <name> [--into default]
```

1. Verify `<name>` exists and validates.
2. Read `<name>`'s surface; archive default surface to `.episteme/archive/reasoning-surface.default.<timestamp>.json` (so merge is reversible by manual restore).
3. Write `<name>`'s contents to default surface.
4. Archive `<name>` to `.episteme/archive/reasoning-surface.<name>.<timestamp>.json`.
5. Remove `.episteme/reasoning-surface.<name>.json`.
6. Switch active to default.
7. Log a chain envelope: `{type: "branch_merge", name, source_archived: "...", target_archived: "..."}`.

`--into <other-branch>` allows merging into a non-default branch — operator pattern when one exploratory branch supersedes another without affecting the main reasoning thread.

### Branch drop

```
episteme branch drop <name> [--force]
```

1. Confirm with operator (skipped under `--force`).
2. Archive `<name>` to `.episteme/archive/reasoning-surface.<name>.<timestamp>.json`.
3. Remove `.episteme/reasoning-surface.<name>.json`.
4. If `<name>` was active, switch to default.
5. Log a chain envelope.

### Branch diff

```
episteme branch diff <a> [<b>]
```

Field-level structural diff between two branches' surfaces. Defaults to comparing active vs default when only one argument is given. Output format: per-field added / removed / changed lines, similar to `git diff --no-index` shape but JSON-aware. Implementation hint: dictdiffer + custom formatter.

---

## Hook integration

At every PreToolUse fire, the gate at `core/hooks/reasoning_surface_guard.py` resolves the active branch first:

```python
def _resolve_active_surface_path(cwd: Path) -> Path:
    active_marker = cwd / ".episteme" / "reasoning-surface.active"
    if active_marker.exists():
        branch = active_marker.read_text().strip()
        if branch:
            branched_path = cwd / ".episteme" / f"reasoning-surface.{branch}.json"
            if branched_path.exists():
                return branched_path
    return cwd / ".episteme" / "reasoning-surface.json"
```

This is the *only* gate-side change. Everything else (staleness check, schema validation, blueprint dispatch) operates on the resolved path identically.

The hook latency budget (< 100ms p95) absorbs one extra filesystem stat + small read; measurement before promotion to confirm.

---

## Concurrency model

- Only one active branch at a time per project. Switching is atomic via single-file write to `.episteme/reasoning-surface.active`.
- Multiple Claude Code sessions in the same project share the active marker. If two sessions switch branches simultaneously, last-write-wins (this is acceptable because the marker is a single line and the operator is the one driving the switch).
- The branched surface files are independently editable by the operator (e.g., via direct file edit) when not active. Edits to the active branch surface are picked up by the next hook fire (no caching).

---

## Lifecycle examples

```
# Operator is mid-Event on the main thread.
$ ls .episteme/
reasoning-surface.json    advisory-surface

# Branches off to explore an alternate decomposition.
$ episteme branch create explore-decomp-b --from default
Created branch 'explore-decomp-b' from 'default'.
Switched active branch to 'explore-decomp-b'.

# Operator edits .episteme/reasoning-surface.explore-decomp-b.json directly,
# proposes a different blast_radius_map, runs a probe op.
# Hook reads explore-decomp-b's surface, not default's. Default is unchanged.

$ episteme branch list
* explore-decomp-b   (active)   modified 2m ago     valid
  default                       modified 3h ago     valid

# Decides explore-decomp-b is correct. Merges into default.
$ episteme branch merge explore-decomp-b
Archived 'default' to .episteme/archive/reasoning-surface.default.2026-05-08T07-30-00Z.json
Archived 'explore-decomp-b' to .episteme/archive/reasoning-surface.explore-decomp-b.2026-05-08T07-30-00Z.json
Default updated. Switched active branch to 'default'.

# Or — decides explore-decomp-b is wrong. Drops it.
$ episteme branch drop explore-decomp-b
Archive 'explore-decomp-b' to .episteme/archive/reasoning-surface.explore-decomp-b.2026-05-08T07-30-00Z.json [Y/n]? Y
Dropped branch 'explore-decomp-b'. Switched active branch to 'default'.
```

---

## Failure modes branching counters

- **Surface contamination during exploration.** Today, an operator who wants to try a different decomposition on a hard problem must overwrite the surface and lose the original framing. Branching preserves the original.
- **Concurrent analysis pressure.** The pi-vs-episteme analysis (Event 109) is the canonical case — operator wanted to think about both the comparison AND continue with the main thread. Branching makes that natural.
- **Probe-then-revert friction.** Today, "let me try this approach for one tool call and see if the surface validates differently" requires manually editing the surface and remembering to revert. A branch is the explicit form.

---

## Failure modes branching does NOT counter

- **Bad surface content.** A branched surface is still subject to Blueprint D validation. Branching does not relax the schema.
- **Branch sprawl.** No automatic cleanup; the operator is responsible for `branch drop` of stale branches. Mitigation: `episteme branch list` shows mtime; future enhancement could surface "stale > 14d" warning.
- **Cross-project branching.** Branches are per-project (live under `<project>/.episteme/`). Cross-project surface sharing is out of scope.
- **Branch naming collisions.** Resolution: kebab-case regex restricts to `[a-z0-9][a-z0-9-]{0,63}` so collisions are detected at create time.

---

## Implementation path

Decomposes into four independent sub-Events, each with its own Reasoning Surface:

1. **`core/hooks/_branch.py`** — branch resolution module. Reads `.episteme/reasoning-surface.active`, returns resolved path. ~50 LOC + tests. *Reversible: pure-additive new module.*
2. **`core/hooks/reasoning_surface_guard.py` integration** — replace one hardcoded path read with `_branch.resolve_active_surface_path(cwd)`. ~5-line change. *Reversible: revert restores default-only behavior.*
3. **`src/episteme/cli.py` subcommand** — `episteme branch [...]` implements all 6 verbs (list, create, switch, merge, drop, diff). ~250 LOC + tests. *Reversible: additive subcommand.*
4. **Chain integration** — log create/switch/merge/drop envelopes via `_framework.write_*`. ~30 LOC. *Reversible: additive.*

Each sub-Event multi-day. Total estimate: 4-7 days of bounded engineering work + soak window before promotion.

---

## Out of scope for this spec

- Branch sharing across machines / repositories (multi-machine sync) — out of kernel scope; could ride substrate-bridge if needed later.
- Three-way merge with conflict markers — declined; merge is an overwrite. Field-level diff via `episteme branch diff` is the conflict-resolution surface.
- The `episteme rigor` design — see [`SPEC_RIGOR_KNOB.md`](./SPEC_RIGOR_KNOB.md). The two specs are independent and can land in either order.
- Hot-reload of branched surface mid-session — out of scope for this spec; belongs to the Tier 3 hot-reload Event.

---

## Provenance

Tier 2.3 design spec, Event 110, 2026-05-08. Drives Tier 3 implementation. See `docs/PRIVATE_ANALYSIS_PI_VS_EPISTEME.md` for the comparison that surfaced the need.
