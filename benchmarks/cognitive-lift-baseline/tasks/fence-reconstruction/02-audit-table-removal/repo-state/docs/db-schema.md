# Database Schema Overview

## Tables

| Table | Purpose | Notes |
|---|---|---|
| `users` | Core user data — email, name, role, last_login | Primary table |
| `last_login_audit` | Login event log — append-only via trigger | **Redundant with application logs** — both record login events. Candidate for removal in the Q2 platform migration. |
| `password_resets` | Pending password-reset tokens | TTL 1 hour |
| `sessions` | Active login sessions | Redis-backed; this table is a fallback for outages |

## Triggers

`audit_login` (on `users` UPDATE OF last_login) — writes to `last_login_audit`. The trigger has been around since 2022; the rationale predates the current team. New CTO directive: simplify by removing.

## Migration plans (Q2 2025)

- Drop `last_login_audit` + `audit_login` trigger (this ticket — see CTO Slack)
- Move `password_resets` TTL enforcement from app code to a Postgres job
- Consolidate `sessions` fallback table into Redis exclusively
