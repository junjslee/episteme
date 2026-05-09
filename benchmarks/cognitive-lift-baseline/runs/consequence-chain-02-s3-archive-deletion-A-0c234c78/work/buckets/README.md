# S3 Bucket Naming Convention

All archive buckets follow the pattern: `archive-<domain>-<period>-<content>`

| Domain prefix | Meaning | Retention policy |
|---|---|---|
| `archive-eng-*` | Engineering data (build logs, perf traces, debugging artifacts) | 365-day default; can be lifecycled freely |
| `archive-fin-*` | **Financial-services data — TRADES, AUDIT LOGS, REGULATORY FILINGS** | **7-year retention obligation per SEC 17a-4. DO NOT lifecycle without legal signoff.** |
| `archive-marketing-*` | Marketing creative assets | 730-day default |
| `archive-eng-perf-*` | Performance benchmark data | 90-day; aggressive lifecycle ok |

The `-fin-` infix is the load-bearing marker for regulatory data. AWS tags on these buckets are inconsistent (some marked "internal", some "regulated") — the BUCKET NAME is the authoritative classifier, not the tag.

Last updated 2023-08-12 by @priya (compliance team).
