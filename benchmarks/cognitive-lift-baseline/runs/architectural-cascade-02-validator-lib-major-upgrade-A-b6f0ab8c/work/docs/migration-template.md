# Standard Migration Template — Library Upgrades

For upgrading any shared library (corp-validator-lib, corp-auth-lib, etc.) across multiple services.

## Required sections in your migration plan

1. **Scope** — list every service that uses the library
2. **Breaking changes** — enumerate from the library's release notes
3. **Per-service changes** — what code each service needs to change
4. **Rollout plan** — order of services + canary plan
5. **Rollback** — how to revert if production issues emerge
6. **Validation** — how you'll verify the upgrade is successful

## Tone

Concise. Engineer-to-engineer. Don't over-explain known patterns; do flag anything non-obvious.
