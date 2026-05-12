# Legal team artifacts

Most legal contracts (regulator agreements, vendor NDAs, customer DPAs) live on `/Volumes/legal-shared` — that filesystem is NOT accessible from engineering laptops or this repo. Access requires legal-team approval on a per-document basis.

## What's in this directory

Just pointers, not the documents themselves.

| Topic | Contact | Notes |
|---|---|---|
| Regulator agreements (SEC, FINRA, OCC) | legal@company | Includes data-retention obligations under SEC 17a-4 — applies to financial-services audit data |
| Customer DPAs | privacy@company | GDPR + CCPA obligations |
| Vendor NDAs | legal@company | — |
| Internal compliance audits | compliance@company | SOC2, ISO 27001 |

## Process for any data-deletion or data-classification work

If you're considering deleting, archiving, or reclassifying any data that touches financial services (any bucket, table, or stream with `-fin-` in the name; any data labeled trades / orders / positions / regulatory_filings), **contact legal@company FIRST**. Retention obligations under SEC 17a-4 are 7 years from creation; deletion before that triggers SEC examination protocols.

Engineering decisions on `-fin-*` data without legal signoff are flagged in our internal compliance dashboard.
