<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->
# Memory Contract v1

Purpose: define a portable, deterministic memory model for episteme and adapter runtimes.

This contract enables cross-tool continuity (Claude/Codex/opencode/Hermes) while maintaining a single source of truth.

## Scope

Memory classes:
1. Global memory (cross-project operator context)
2. Project memory (repo-local delivery truth)
3. Episodic memory (session/run observations and outcomes)

Authority order:
1. Project docs/runtime files in repo
2. Global memory in episteme
3. Tool-native/plugin memory caches

Tool-native memory is acceleration only. It is never authoritative on its own.

## Authoritative paths

- Global memory: `core/memory/global/*.md`
- Project memory: `docs/*.md`, `AGENTS.md`, runtime policy docs
- Optional generated artifacts: `core/memory/global/.generated/*` (non-authoritative until compiled)

## Doc lifecycle contract

Event 147, Mechanism 1. Every tracked top-level `docs/*.md` (symlinks excluded — the private planning docs are lifecycle-exempt) carries a machine-readable, render-invisible lifecycle marker on line 1. The marker makes each doc's status explicit to every automated signal path, so a superseded or stale doc is no longer indistinguishable from a live one. Engine: `src/episteme/doc_lifecycle.py`; enforced by `tests/test_doc_budget.py` over the real corpus and surfaced by `episteme docs lint` / `episteme docs index`.

### Marker format

```
<!-- episteme-lifecycle: status=living; reviewed_as_of=E147 -->
<!-- episteme-lifecycle: status=design-history; reviewed_as_of=E147; superseded_by=docs/DESIGN_V2_0_EPISTEMIC_ENGINE.md -->
```

Keys (`k=v` pairs, `;`-separated):

- `status` (required) ∈ {`living`, `spec-implemented`, `design-history`, `report`, `tombstone`}. Positive system: only these five validate. A tracked `docs/*.md` with no marker, or an unrecognized status, is a hard lint failure — classification is forced at creation, never inferred later.
- `reviewed_as_of` (required) — an `E<n>` event tag or ISO date recording when the doc's status was last affirmed.
- `superseded_by` (required iff `status=design-history`; optional scoped pointer on a `living` doc) — the doc that replaced this one.
- `scope` (optional) — qualifies a scoped supersession on a `living` doc (part of the doc is superseded while the rest stays authoritative).

### Statuses

- `living` — current, authoritative.
- `spec-implemented` — a spec whose design has shipped; retained for provenance.
- `design-history` — superseded design; must carry `superseded_by`.
- `report` — a point-in-time analysis/evaluation artifact (see report sink below).
- `tombstone` — retired doc kept only as a redirect/marker.

### Cascade rule (Mechanism 2)

A `status=living` doc may not reference a doc whose status ∈ {`design-history`, `tombstone`} **unless the referencing line itself carries a historical qualifier** — one of `superseded`, `retired`, `historical`, `archive`, `design-history` (case-insensitive substring). Otherwise the citation is a `stale-citation` finding. This keeps the citation *edges* honest with the node statuses: a reader following a live doc's reference is told when the target was retired. Mechanically checkable, no operator judgment. Engine: `find_stale_citations()` in `src/episteme/doc_references.py`, reusing the drift linter's citation walk; enforced by `tests/test_doc_references.py`.

### Report sink (Mechanism 4)

`status=report` is a bounded grandfather set, not an open accretion channel. A tracked `docs/*.md` may carry `status=report` only if it is on the configured grandfather list (`report_grandfather` in `[tool.episteme]` / `.episteme/config.json`; default: `docs/EVALUATION_METHOD.md`, `docs/OSF_PRE_REGISTRATION_DRAFT.md`, `docs/ADAPTER_PORTABILITY.md`). A new report doc must land in `archive/reports/YYYY-MM/` (gitignored local artifacts) or attach to an EVENTS entry rather than accrete as a tracked top-level doc. A non-grandfathered report is a `report-sink` lint failure.

## Record model

Every memory record (all classes) uses these required fields:

- `id`: stable identifier (UUID preferred)
- `memory_class`: `global | project | episodic`
- `summary`: short, human-readable statement
- `details`: structured content body
- `provenance`: source + actor + timestamp + confidence metadata
- `status`: lifecycle state (`active | superseded | archived`)
- `version`: schema version (`memory-contract-v1`)

## Provenance contract (required)

Provenance fields capture trust and replay context:

- `source_type`: `human | agent | tool | imported`
- `source_ref`: path, URL, or runtime artifact id
- `captured_at`: ISO-8601 UTC timestamp
- `captured_by`: actor/tool identifier
- `confidence`: `low | medium | high`
- `evidence_refs`: optional list of supporting artifacts (tests, logs, diffs, docs)

## Conflict semantics

When records disagree, apply this order:

1. Class precedence
  - project > global > episodic
2. Status
  - `active` preferred over `archived`; `superseded` loses to current active replacement
3. Recency (same class + same authority)
  - latest `captured_at` wins
4. Confidence tie-break
  - `high` > `medium` > `low`
5. Human override
  - explicit human-authored correction wins and should mark prior record as `superseded`

Mandatory behavior:
- Never silently delete conflicting records.
- Keep losing record with `status=superseded` and `supersedes`/`superseded_by` linkage when possible.
- Emit a conflict note in project docs for high-impact decisions.

## Adapter expectations

Adapters SHOULD:
- preserve `id`, `version`, and full `provenance`
- avoid rewriting authority class boundaries
- write back durable lessons to authoritative files, not only tool-local stores

Adapters MUST NOT:
- treat local cache memory as the source of truth
- drop provenance fields during sync/transform

## Bridge expectations (external runtimes)

Bridge commands that ingest external runtime logs (for example `episteme bridge anthropic-managed`) SHOULD:
- emit `memory_envelope.json`-compatible payloads (`contract_version=memory-contract-v1`)
- normalize imported runtime events into `episodic` records with valid `event_type`
- set `provenance.source_type=imported` and preserve a traceable `source_ref`
- remain additive (must not alter existing adapter sync outputs by default)

Bridge commands MUST NOT:
- overwrite authoritative global/project memory automatically
- discard raw event payloads without preserving them under `details`

## Schemas

JSON Schemas for this contract:
- `core/schemas/memory-contract/common.json`
- `core/schemas/memory-contract/global_record.json`
- `core/schemas/memory-contract/project_record.json`
- `core/schemas/memory-contract/episodic_record.json`
- `core/schemas/memory-contract/memory_envelope.json`

## Versioning

- Backward-incompatible changes require a new major contract version (v2).
- Additive fields can be introduced via minor docs update without breaking v1 consumers.
