# architectural-cascade/02-validator-lib-major-upgrade

## Task prompt

You're a senior platform engineer. CTO directive in the engineering all-hands deck:

> "We need to upgrade `corp-validator-lib` from v2.1.0 to v3.0.0 across all services. v2.x EOL is end of next quarter — we have ~4 months but I want to start now to avoid the rush. Plan the upgrade. Three services use this library: service-a, service-b, service-c. Standard upgrade template at `docs/migration-template.md`. Submit a migration plan when ready."

Read each service's usage of corp-validator-lib, read the v3.0.0 changelog, plan the upgrade. Output: a migration plan document covering all three services.

## Category

architectural-cascade

## Failure mode under test

WYSIATI on what release notes don't say + architectural-cascade on the silent break. v3.0.0 changed the validator override registry from case-INSENSITIVE to case-SENSITIVE class-name matching. The v3 CHANGELOG.md does NOT mention this change. Service A has a custom validator registered as `customValidator` (lowercase 'c'). Under v3, that registration silently fails — no error at startup, no warning at registration time. The downstream effect: Service A's payload validation falls back to the default validator, which accepts malformed payloads that Service A's custom validator was specifically designed to reject. Downstream consumer services panic on the malformed payloads.

The breaking change is discoverable ONLY by reading v3's `registry.py` source code and comparing to v2's. The CHANGELOG paints it as a minor release.

A naive agent reads the changelog, doesn't see anything alarming, plans a straightforward upgrade.

## Why this task discriminates

This task hits **D2** (the breaking change is genuinely outside what the prompt provides — release notes lie by omission, only the source code reveals it), **D5** (silent break — locally fine at upgrade time, downstream panic over weeks as malformed payloads accumulate), **D3** (release notes are misleading evidence pointing toward "minor changes only").

A kernel-active session running Architectural Cascade blueprint is forced to enumerate the full blast_radius_map (every service that uses the library + every CUSTOM EXTENSION POINT) and produce a sync_plan that explicitly checks each extension. The blueprint's discipline is what catches Service A's lowercase override — without it, the agent reads the changelog, plans the upgrade, ships, and the silent break lives in production for weeks.
