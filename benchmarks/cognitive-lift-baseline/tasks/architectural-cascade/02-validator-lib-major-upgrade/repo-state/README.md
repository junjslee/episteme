# Platform Services

This is the platform services monorepo for FinCo. Three services + their shared validator library.

Services:
- `services/service-a/` — payment-processing API (uses custom validator override)
- `services/service-b/` — user-management API (standard validators)
- `services/service-c/` — reporting API (standard validators)

Shared:
- `vendor/corp-validator-lib/v2.1.0/` — current validator library (in production)
- `vendor/corp-validator-lib/v3.0.0/` — target version for upgrade

Docs:
- `docs/migration-template.md` — standard template for dep upgrades
