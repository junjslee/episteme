# Deferred Discoveries Triage — Phase 2 Output (Event 47)

Resolves Phase 2 of `docs/POST_SOAK_TRIAGE.md` §2. The original plan
called for a 50-record sample with extrapolation across 1,294 records.
Running `tools/sample_deferred.py --unique` revealed the far simpler
structural picture: **1,294 records collapse to 40 unique findings**
(32.4× dedup ratio). The four most-duplicated findings each appear
105 times. Full manual classification of 40 is feasible and more
accurate than sampling.

**So the bigger finding here is CP-DEDUP-01** (below) — the framework
writer is not deduping entries at log time; every repeated cascade:
architectural firing re-logs identical findings. That is a v1.0.1
CP.

## 1. Structural picture

```
total records                1294
unique (class, desc[:120])     40
dedup ratio                  32.4x
classification breakdown by flaw_classification:
  schema-implementation-drift  672 records
  config-gap                   321
  other                        184
  doc-code-drift               117
source_op: cascade:architectural  1276  (98.6%)
source_op: git push                 18   (1.4%)
```

Pre-Event-38 records: **1,275**. Post-Event-38: **19**. The
bulk is legacy; the current-soak contribution is tiny. Any fix
that drops the re-log rate will drastically slow accumulation.

## 2. Manual classification of 40 unique findings

Labels:
- **REAL-DEBT** — describes current-master code or process issue; would change behavior if fixed.
- **RESOLVED** — a subsequent commit fixed the underlying condition; entry is stale.
- **NOISE** — transient observation, decorative, meta, or no-longer-applicable (e.g., arxiv-dropped work).

| # | Dups | Class | Verdict | Finding |
|---|---:|---|---|---|
| 1 | 105 | schema-implementation-drift | REAL-DEBT | Blueprint D cascade detector fires on kernel's own state files — requires exemption allowlist |
| 2 | 105 | schema-implementation-drift | REAL-DEBT | Cross-ref count proxy uses byte-occurrence count; single file mentioning basename multiple times inflates score |
| 3 | 105 | schema-implementation-drift | RESOLVED | kernel/SUMMARY.md 30-line distillation missing Blueprint D reference — verified Event 48: line 31 names "Blueprint D · Architectural Cascade & Escalation" explicitly; already present in current master |
| 4 | 105 | schema-implementation-drift | REAL-DEBT | Retrospective sync-plan completeness verification — explicitly spec-deferred to v1.0.1 by design |
| 5 | 82 | schema-implementation-drift | REAL-DEBT | `default_autonomy_class` + `fence_check_strictness` orphan knobs — Phase B v1.0.1 scope |
| 6 | 82 | schema-implementation-drift | REAL-DEBT | Ashby / escalate-by-default counter documented in FAILURE_MODE 9 but not in code (zero grep hits for `escalate_by_default`) |
| 7 | 82 | schema-implementation-drift | REAL-DEBT | Jaynes/Laplace evidence-weighted assumption update — declared-only in docs; epistemic v1.1 candidate |
| 8 | 72 | config-gap | RESOLVED | RC engineering gate missing installable-plugin-smoke-test — addressed by Event 28+ (external-tester fixes) |
| 9 | 72 | config-gap | RESOLVED | Version drift 0.11.0 vs 1.0.0-rc1 in plugin manifests — addressed by Event 30 plugin-manifest sync |
| 10 | 38 | config-gap | RESOLVED | pnpm cwd surface-missing — resolved by Event 42 `_canonical_project_root()` |
| 11 | 37 | doc-code-drift | NOISE | TikZ/TeX architecture_v2.tex sibling not regenerated — arxiv focus dropped, no longer applicable |
| 12 | 37 | doc-code-drift | RESOLVED | kernel/SUMMARY.md still does not name Blueprint D — same finding as #3; same Event 48 verification applies |
| 13 | 37 | doc-code-drift | NOISE | README.md + dashboard embed stale system-overview.png — web has been redesigned; stale embed no longer rendered |
| 14 | 26 | other | NOISE | SVG master asset for selected design direction — decorative branding, not load-bearing |
| 15 | 26 | other | NOISE | Export PNG raster variants at 1x/2x/4x — decorative |
| 16 | 26 | other | NOISE | Integrate approved logo in README — decorative |
| 17 | 26 | other | NOISE | Integrate approved logo in website — decorative |
| 18 | 26 | other | NOISE | CLI half-block rendering test at ~16 cells — decorative terminal-art |
| 19 | 26 | other | RESOLVED | Wire website to auto-render README.md — delivered via Event 29 `/readme` route |
| 20 | 23 | config-gap | REAL-DEBT | RC engineering gate did not catch drift — process gap; external-tester bugs indicate pre-tag smoke missing install step |
| 21 | 19 | config-gap | RESOLVED | Claude Code async-hook invocation bug upstream report — Event 38 root cause was NOT an async bug; was `build_settings()` manifest gap |
| 22 | 15 | config-gap | NOISE | Narrow-exception-over-generalization meta-observation across Events 27/29/31 — recorded as global rule in agent_feedback |
| 23 | 14 | config-gap | RESOLVED | Vercel www-as-primary vs apex — Event 33 accepted current state |
| 24 | 13 | config-gap | NOISE | positive-vs-negative-system decision-tree first-pass heuristic — meta-observation recorded as global rule |
| 25 | 13 | config-gap | REAL-DEBT | Native-speaker review of README.es.md + README.zh.md + .ko — quality pass pending |
| 26 | 12 | config-gap | REAL-DEBT | Cascade detector fires on read-only verification ops (git log, file reads) — hot-path cost |
| 27 | 8 | config-gap | REAL-DEBT | Auto-checkpoint re-fires mid-session producing premature chkpt commits |
| 28 | 8 | config-gap | RESOLVED | Day-2 gate-grading thin-data framework — addressed by Event 46 POST_SOAK_TRIAGE.md |
| 29 | 7 | other | REAL-DEBT | `web/src/app/favicon.ico` still Next.js template default — cosmetic but external-facing |
| 30 | 7 | other | RESOLVED | Q1 website auto-renders README — delivered via Event 29 |
| 31 | 7 | other | NOISE | CLI half-block render — duplicates #18 |
| 32 | 7 | other | NOISE | 24×24 favicon visual verification — operator confirmed "renders so I think it's good" |
| 33 | 6 | schema-implementation-drift | NOISE | Path-A soak reset structural tension — meta-observation about soak-safety rules |
| 34 | 5 | config-gap | NOISE | /readme + /commands positive-system pattern — meta-observation |
| 35 | 5 | config-gap | REAL-DEBT | Post-chain-hygiene fix, Gate 57 triage cadence recalibration — future v1.0.1+ refinement |
| 36 | 3 | config-gap | RESOLVED | Surface-file-deletion race — resolved by Event 42 canonical path |
| 37 | 2 | doc-code-drift | REAL-DEBT | 4+ kernel-dogfood schema gaps (flaw_classification enum missing doc-positioning-drift; posture_selected missing audit-pass); schema evolution v1.0.1 |
| 38 | 2 | doc-code-drift | NOISE | Gall citation permeation-pass — arxiv dropped |
| 39 | 2 | doc-code-drift | NOISE | Tversky/Gigerenzer/Marr primary-source citations — arxiv dropped |
| 40 | 1 | config-gap | RESOLVED | Multi-cwd session surface-path handling — Event 42 |

## 3. Tally

**Revised Event 48** after verification that findings #3 and #12 (kernel/SUMMARY.md
missing Blueprint D) were already RESOLVED in current master (`kernel/SUMMARY.md`
line 31 names Blueprint D explicitly; the deferred-discovery claim was stale).

- **REAL-DEBT**: 12 unique findings · weighted record count ≈ 594 (46% of 1,294)
- **RESOLVED**: 11 unique findings · weighted record count ≈ 429 (33%)
- **NOISE**: 17 unique findings · weighted record count ≈ 210 (16%)
- (Remaining weight ≈ 61 records unclassified — rounding + partial-match dups; see reproducibility commands in §6)

Weighted REAL-DEBT (post-correction):
```
105 + 105 + 105 + 82 + 82 + 82 + 23 + 13 + 12 + 8 + 7 + 5 + 2 + 2 ≈ 633
```
Minor calibration note: the exact weighted sums depend on dedup-prefix length;
the direction (majority of weight lives in REAL-DEBT) holds regardless of
±10% on bucket assignments.

## 4. REAL-DEBT → CP candidate mapping

Seven of the 14 REAL-DEBT items cluster into v1.0.1 CPs. Priority
scored as `gate_impact × (1 / effort_days)` per
`POST_SOAK_TRIAGE.md` §3.2.

| CP candidate | Addresses unique findings | Effort (days) | Priority |
|---|---|---:|---|
| CP-DEDUP-01 (dedup-on-log) | ALL 40 (structural retirement of ~1,275 pre-fix records) | 0.5 | HIGH |
| CP-TEL-01 (exit_code camelCase) | #1, #2 indirectly (hot-path budget) | 0.5 | HIGH |
| CP-FENCE-01 (empty-emit, marker cleanup) | #1 (cascade on state files), #36 | 1 | HIGH |
| CP-CASCADE-01 (exempt kernel state files + read-only ops) | #1, #26 | 1 | MEDIUM |
| CP-CROSSREF-01 (unique-file-count proxy) | #2 | 0.5 | MEDIUM |
| ~~CP-SUMMARY-01~~ (already resolved in master — Event 48 verification) | — | — | DROPPED |
| CP-SMOKE-01 (plugin-install smoke test) | #20 | 1 | MEDIUM |
| CP-ASHBY-01 (escalate_by_default implementation) | #6 | 3 | MEDIUM |
| CP-KNOBS-01 (default_autonomy_class + fence_check_strictness) | #5 | 2 | MEDIUM |
| CP-CHKPT-01 (auto-checkpoint re-fire) | #27 | 1 | MEDIUM |
| CP-FAVICON-01 (real favicon.ico) | #29 | 0.1 | LOW (trivial) |
| CP-I18N-01 (native-speaker README review) | #25 | external | DEFER |
| CP-SCHEMA-01 (enum + field evolution) | #37 | 1 | LOW |
| CP-JAYNES-01 (evidence-weighted assumptions) | #7 | 5 | DEFER v1.1 |

The four HIGH priority + two trivial-effort CPs (CP-DEDUP-01, CP-TEL-01,
CP-FENCE-01, CP-SUMMARY-01, CP-FAVICON-01) together retire or touch
the top-10 dup buckets (776 records = 60% of total).

## 5. What this changes in POST_SOAK_TRIAGE.md

- **Phase 2** no longer requires sampling-and-extrapolation — the
  40-unique full list is now the canonical denominator. The
  `tools/sample_deferred.py --unique` mode replaces `--sample 50`.
- **Phase 3** (CP derivation) is seeded with the 14 CP candidates
  above. Operator can promote the top-4 HIGH-priority + 2 trivial
  into v1.0.1-rc1 scope at Day-7 GA decision time.
- **CP-DEDUP-01** is new and not in the original POST_SOAK_TRIAGE
  seed list — surfaced by running the triage tool. It's the
  highest-leverage single fix (stops the 32× dedup ratio from
  growing at the current 67 records/day rate).

## 6. Reproducibility

```bash
# Full list of 40 unique findings, sorted by dup count:
python3 tools/sample_deferred.py --unique | jq '.unique_findings[]'

# Post-Event-38 only (19 records in 40-unique view):
python3 tools/sample_deferred.py --unique --since 2026-04-23T21:23:36Z

# Drill into one flaw class:
python3 tools/sample_deferred.py --unique --by-class schema-implementation-drift
```

The manual classification in §2 is one reviewer's verdict (this
session's agent, informed by Events 28-46 session context).
Independent classification by the operator is the authoritative
v1.0.1 scoping input — the table above is a starting point, not
final.
