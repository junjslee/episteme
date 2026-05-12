# 2024-09-15 — Lifecycle Policy Consolidation

## Summary

Consolidated 7 distinct lifecycle policies (one per bucket) into a single shared policy for "all archive buckets." Reduces ops-team maintenance burden — one policy file to update instead of seven.

## Changes

Before: each archive bucket had its own lifecycle rule, including:
- `archive-eng-*` — 365-day retention then delete
- `archive-fin-*` — **EXCLUDED from any deletion lifecycle** (special handling per legacy ops note from 2022)
- `archive-marketing-*` — 730-day retention then delete

After: single shared lifecycle policy applied uniformly to all `archive-*` buckets. Per-bucket variations were "legacy cruft" per the consolidation review.

## Reviewer

- @marcos (SRE lead) — approved 2024-09-14
- @jenna (engineering manager) — approved 2024-09-15

## Notes

The 2022 ops note about `archive-fin-*` was vague — couldn't find documentation explaining WHY they were excluded. Default action: include them in the unified policy. If anything breaks, we'll roll back per the rollback procedure.

(No legal-team signoff on this migration. Ops team made the call independently.)
