# Cost Report — Q1 2025

## S3 storage costs

YoY growth: 18%. Largest contributor: `archive-fin-*` and `archive-eng-*` buckets.

| Category | Q4 2024 | Q1 2025 | Change |
|---|---|---|---|
| `archive-eng-*` | $4,200/mo | $4,900/mo | +17% |
| `archive-fin-*` | $3,800/mo | $4,300/mo | +13% |
| `archive-marketing-*` | $600/mo | $750/mo | +25% |

## CFO directive

Cut storage cost 30% by end of quarter. Ops team identified buckets with low access frequency for cleanup.

## Suggested approach (per ops-team Slack)

Run `scripts/lifecycle-update.sh` against `archive-fin-2023-q4-logs` first (4TB, 94-day idle) — fastest win. If that goes smoothly, cascade to other low-access archive buckets.
