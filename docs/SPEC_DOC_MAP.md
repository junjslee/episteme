<!-- episteme-lifecycle: status=spec-implemented; reviewed_as_of=E173 -->
# SPEC — Code→Doc Reverse Index (`docs map`) and the Targeted DOC ADVISORY

Event 173. Operator-ratified (design C of three; wiki-pages and a hand-authored
`DOC_MAP.json` were rejected — both add a hand-maintained surface that itself
rots, which is the disease under treatment).

## Failure mode countered (anti-accretion rule 7)

**Doc-code drift discovered late.** A code edit lands; the docs that claim to
describe that code stay unchanged; the divergence surfaces only in a later
batch sweep (the E172 class of repair: 13 findings, a full day) or in the
SessionStart staleness banner (22 living docs >15 events behind at the time of
this event). The write path — the only moment when the edit and its doc
obligations coexist in one context — carried no doc-specific signal.

## Mechanism replaced (anti-accretion rule 7)

`core/hooks/workflow_guard.py`'s **path-blind static advisory** ("Keep
docs/EVENTS.md and docs/NEXT_STEPS.md aligned"), which named the same two files
regardless of what was edited. The static string survives only as the fallback
tier (below). No new hook, no new queue, no new hand-maintained file.

## Rule-shape (kernel rule 8)

**Positive system.** An edit-time obligation exists ONLY where a live authored
doc cites the edited path — exactly, or via an enclosing directory. Uncited
code carries no obligation. Consequence: a doc earns edit-time surfacing by
citing the code it describes, so citation hygiene and map fidelity are the
same act. The obligation-citing corpus additionally excludes `archive/`
(frozen history must not generate present-tense obligations) on top of the
drift linter's fixture-tree exemptions.

## Architecture — one notion of "what a doc cites"

The map is the **inverse of the citation edges the drift linter already
extracts** (`src/episteme/doc_references.py::extract_references`; CI keeps them
non-dangling via `tests/test_doc_references.py`). Nothing is authored; the map
cannot rot by construction. New functions, same module:

| Function | Contract |
|---|---|
| `build_reverse_index(root, doc_files=None)` | claimed cited path → `[DocEdge]` over the obligation corpus. Unresolved citations are indexed as claims: a doc that pre-documents a not-yet-existing file must obligate the Write that creates it, and claims-in-index keeps the index a pure function of the markdown corpus — the property the cache digest relies on (review finding, this event). Dangling claims remain `find_drift`'s findings; the mechanisms stay separate |
| `edges_for_path(root, path, index=None)` | citing edges, strongest claim first: exact file > deeper dir > shallower dir; one edge per doc; self-citations excluded |
| `docs_for_path(root, path, ...)` | the sorted doc list (thin wrapper) |
| `annotate_docs(root, docs)` | display labels: `status · reviewed_as_of · N events behind` (lifecycle marker + `docs/EVENTS.md` scan), `manifest-managed` (kernel manifest membership), else empty — every lookup degrades, never raises |
| `cached_reverse_index(root)` | the index behind an mtime+size digest cache at `.episteme/cache/doc_map.json`; ~200ms cold / ~10ms steady-state; cache written ONLY where `.episteme/` already exists; any cache failure → fresh build |

## Consumers

1. **`workflow_guard.py` (PreToolUse Write|Edit|MultiEdit).** On an
   implementation-file edit: `DOC ADVISORY: N doc(s) claim to describe
   '<path>'` + up to 6 docs (overflow counted, never silent) + lifecycle
   labels + `[via <dir>/]` tags for directory edges. Fallback ladder, each
   step caught and degraded, never a crash: package unimportable (plugin-only
   install) → generic advisory · project not a git repo → generic · no citing
   docs → generic (positive system: no citation, no obligation). The package
   imports via the E172 self-resolve pattern (`__file__ → ../../src`).
   Also repaired in this event: the doc-path suppression never matched the
   absolute file paths harness payloads actually carry (`lstrip("./")` strips
   a character set, not a prefix) — targets are now normalized to
   project-relative form before the policy test.
2. **`episteme docs map [path ...]`** — the agent/operator query surface
   ("the wiki"): per-path citing docs with the same ordering and labels as the
   hook; full `target ← docs` dump with no args. Informational, exit 0.
3. **`AGENTS.md` → Workflow convention** names the mechanism and the repair
   duty ("repair in the same change or record why not").

## Drain (kernel rule 6 — no new operator-judgment queues)

The advisory is discharged **in the same change** (repair the doc, or record
why not) — the write path is the drain. Nothing is enqueued anywhere; ignoring
the advisory leaves the corpus exactly as it was (the staleness banner and the
E172-class sweeps remain the backstop, now with a smaller tail to catch).

## Declared limits

- **Conceptual docs that cite no code paths are invisible to the map** (e.g.
  a philosophy doc that names no files). Their alignment stays with the event
  process; this mechanism owns only the mechanically derivable edges.
- Directory citations are weak claims; they rank below exact-file citations
  and carry `[via …/]` so the reader can weigh them.
- The map covers the governed project's own tracked markdown only (tracked =
  environment-stable; private symlinked docs are auto-excluded).

## Verification

`tests/test_doc_map.py`: inversion semantics (exact/dir/dangling-as-claim/
exempt/self), query normalization (absolute, outside-root, not-yet-existing
files under a cited dir — a Write creating a hook must fire), strongest-first
ordering, cache hit/invalidation/corruption/footprint rules plus the
adversarial-review scenario (cache built while a cited target is absent, file
created later with no markdown change — the cached answer must still name the
citing doc), symlinked-doc suppression (the guard must not `resolve()` the
private-doc symlinks out of the project), two real-corpus edges this repo
relies on (`core/hooks/workflow_guard.py` → `docs/HOOKS.md`;
`src/episteme/cli.py` → `docs/COMMANDS.md` via the source-of-truth citation
added in this event), and the hook's full fallback ladder end-to-end.

Independent review (E173, adversarial): no blockers; one should-fix (the
cache-staleness hole above — fixed by claims-in-index) and residual nits
consciously accepted: compound symlink-escape via the `resolve()` fallback
branch (reasoned, not reproducible from real harness payloads), ~40ms
steady-state hook overhead on this repo's 233-file corpus (rebuild ~180ms when
markdown changed), deleted-but-indexed markdown disabling the cache until
`git rm` (self-healing, correct answers throughout), and case-sensitive index
keys.
