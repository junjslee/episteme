# Spec — `episteme rigor` (rigor knob)

**Status:** proposed (Tier 2.3 design spec, Event 110, 2026-05-08). Implementation deferred to Tier 3 — see § Implementation path below for decomposition.

**Motivation:** Pi.dev's mid-conversation `/model` switch lets a user route routine work through a cheap fast model and switch to a more capable model when the work demands it. Episteme's analog is the *cognitive rigor* the gate enforces — today the gate runs at one fixed rigor floor. Different work calls for different rigor: routine refactoring, an exploratory probe, and a release decision should not pay the same rigor tax. The `rigor` knob makes that switch explicit, surfaceable, and auditable.

This is **not** an escape hatch. The kernel's invariants (feedforward control, Reasoning Surface as gate, blueprint set as the vocabulary) hold at every rigor level. What changes is which blueprints are *active*, what the staleness TTL is, and whether the verdicts are *advisory* or *blocking*. The minimum floor is named explicitly so a level cannot be misused as a way around the gate.

---

## Surface

### CLI

```
episteme rigor                       # print current level + scope (project | global)
episteme rigor [low|medium|high]     # set the current project's rigor level
episteme rigor --global [low|medium|high]
                                     # set the operator's default level (overridden per-project)
episteme rigor --explain             # describe each level's semantics + which blueprints fire
episteme rigor --json                # machine-readable view (current, scope, source, last_changed)
```

### Persistence

Two sources, in resolution order (most specific wins):

1. **Per-project**, at `<project>/.episteme/rigor` — single line containing `low`, `medium`, or `high`. Created/updated by `episteme rigor [level]`. Read by the gate at every PreToolUse fire (hot-path-cheap; one filesystem stat + read).
2. **Operator default**, at `~/.episteme/rigor` — same shape; used when the project has no `.episteme/rigor` file. Created/updated by `episteme rigor --global [level]`.
3. **Compiled fallback**, hard-coded constant `medium` in the validator. Used when neither file exists.

`episteme rigor` (no args) prints the current resolution: which file fired, what level was found, when it was last changed (file mtime).

---

## Levels

The vocabulary is `low | medium | high`. Each is a named bundle, not a slider — fewer cliffs, more legible audits. The bundles map onto specific gate behavior:

### Level `low` — exploratory / routine

Active scenarios in the gate:

| Behavior | Effect |
| --- | --- |
| Blueprint set | `Axiomatic Judgment` only — the rest are advisory-not-block |
| Cascade detector | Fires advisory only; never blocks |
| Surface staleness TTL | 60 minutes (vs 30 default) |
| Disconfirmation field minimum | 15 chars (default) |
| All-not-applicable cascade-theater advisory | Suppressed |

When to use: routine refactoring on already-shipped code; exploratory probes whose disconfirmation will land in a follow-up Event; doc-only edits that don't touch the kernel/runtime layer.

When NOT to use: irreversible ops; production releases; kernel/blueprint edits; anything the operator would regret if it slipped past the gate.

### Level `medium` — default

Active scenarios in the gate:

| Behavior | Effect |
| --- | --- |
| Blueprint set | All four — Axiomatic Judgment, Fence Reconstruction, Consequence Chain, Architectural Cascade — fire per their existing selector triggers |
| Cascade detector | Fires per current behavior; blocks on missing fields |
| Surface staleness TTL | 30 minutes (current default) |
| Disconfirmation field minimum | 15 chars (default) |
| All-not-applicable cascade-theater advisory | Active |

This is the existing v1.1.0-rc1 behavior. The default for a new project + the operator default until explicitly overridden.

### Level `high` — high-stakes / release-class

Active scenarios in the gate:

| Behavior | Effect |
| --- | --- |
| Blueprint set | All four + Consequence Chain forced on every irreversible-class op (terraform apply / kubectl apply / npm publish / gh release create / docker push / git push --force / etc.) regardless of cascade selector firing |
| Cascade detector | Fires per current behavior; blocks on missing fields |
| Surface staleness TTL | 15 minutes (half of medium) |
| Disconfirmation field minimum | 30 chars (forces sharper observable than 15-char threshold allows) |
| All-not-applicable cascade-theater advisory | Active + escalates to block on second firing within 24h on the same project |

When to use: release windows; production-affecting work; kernel-touching edits; legally / financially / operationally consequential decisions.

---

## Hook integration

The gate at `core/hooks/reasoning_surface_guard.py` reads the resolved rigor level at every PreToolUse fire and dispatches:

```python
rigor = _resolve_rigor()         # 'low' | 'medium' | 'high'
behavior = _RIGOR_BEHAVIOR[rigor]  # named struct from a constants module

# Behavior carries:
#   active_blueprints: frozenset[str]
#   staleness_ttl_seconds: int
#   disconfirmation_min_len: int
#   cascade_advisory_blocks_on_repeat: bool
#   force_consequence_chain_on_irreversible: bool
#   suppress_all_na_advisory: bool
```

The existing `validate_blueprint_d` and the cascade-detector-priority dispatch read from this struct rather than hardcoded constants. A single new module `core/hooks/_rigor.py` owns the resolution + struct.

---

## Lifecycle

```
$ episteme rigor                   # → medium (operator default, ~/.episteme/rigor unset; falling back to compiled default)
$ episteme rigor low               # → wrote .episteme/rigor (project-local, level=low)
$ episteme rigor                   # → low (project-local, .episteme/rigor)
$ episteme rigor --global high     # → wrote ~/.episteme/rigor (level=high). Project still wins.
$ rm .episteme/rigor               # → operator default takes over: high
$ episteme rigor --explain
  low    : Axiomatic Judgment only · cascade advisory · TTL 60min · disconfirm 15ch
  medium : All 4 blueprints · cascade enforced · TTL 30min · disconfirm 15ch (default)
  high   : All 4 blueprints · forced Consequence Chain on irreversible · TTL 15min · disconfirm 30ch
```

The level is recorded into the episodic chain on change so the operator can audit *when* the rigor was lowered and what work fell under that window.

---

## Failure modes the rigor knob counters

- **Operator-friction during exploratory probes** (Finding F3 in the pi-vs-episteme analysis). Today every probe pays the medium-rigor tax. `low` exists for exactly this case.
- **Insufficient rigor on irreversible ops without operator notice.** Today the cascade detector + Consequence Chain blueprint catch most of these but rely on selector firing. `high` forces Consequence Chain on irreversible-class ops regardless.
- **Rigor erosion over time** — operator silently sets `low` and forgets. Mitigation: the level is logged into the episodic chain on every change, surfaced at SessionStart digest if the project has been running below `medium` for > 7 days.

---

## Failure modes the rigor knob does NOT counter

- **Operator deciding to override a specific blueprint** — that's a different mechanism (the existing `.episteme/advisory-surface` flag for project-wide advisory). The rigor knob is coarse-grained; surface-level overrides remain per-Event in the surface itself.
- **Bad surface content with high rigor** — a high-rigor gate cannot save a surface that has plausible-sounding but vacuous Knowns / Unknowns. The structural validators (already in the kernel) handle that orthogonally.
- **Schema gap** — the Tier 3 schema extension (Event 110) is the right tool for missing posture / status / shape values. Don't conflate with the rigor knob.

---

## Implementation path

Decomposes into four independent sub-Events, each with its own Reasoning Surface:

1. **`core/hooks/_rigor.py`** — resolution module. Reads `.episteme/rigor`, `~/.episteme/rigor`, falls back to compiled `medium`. Returns the named behavior struct. ~80 LOC + tests. *Reversible: pure-additive new module.*
2. **`core/hooks/reasoning_surface_guard.py` integration** — replace 5–6 hardcoded constants (TTL, disconfirmation min, blueprint set, advisory thresholds) with reads from the rigor struct. ~30-line change. *Reversible: revert restores prior behavior; behavior at `medium` is byte-identical to current.*
3. **`src/episteme/cli.py` subcommand** — `episteme rigor [...]` reads/writes the two persistence files. ~100 LOC + tests. *Reversible: additive subcommand.*
4. **Episodic chain integration** — log every rigor-level change via `_framework.write_*`. SessionStart digest gains a "rigor below medium for N days" advisory line. ~40 LOC. *Reversible: additive.*

Each sub-Event is multi-day with explicit Reasoning Surface. Total estimate: 3-5 days of bounded engineering work + soak window before promotion to default.

---

## Out of scope for this spec

- Per-blueprint rigor (e.g., low for Fence but high for Cascade) — bundling-only design; per-blueprint flexibility introduces too many states to audit.
- Time-based rigor scheduling (e.g., low between 9am–5pm, high otherwise) — declined; operator's `decision_cadence` profile axis already covers this.
- Network-effect rigor (e.g., high when CI is red) — out of kernel scope; belongs to project CI policy.
- The `episteme branch` design — see [`SPEC_REASONING_SURFACE_BRANCHING.md`](./SPEC_REASONING_SURFACE_BRANCHING.md). The two specs are independent and can land in either order.

---

## Provenance

Tier 2.3 design spec, Event 110, 2026-05-08. Drives Tier 3 implementation. See `docs/PRIVATE_ANALYSIS_PI_VS_EPISTEME.md` for the comparison that surfaced the need.
