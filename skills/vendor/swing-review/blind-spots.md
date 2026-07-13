# Domain Blind-Spot Library (external signal for Phase 2.5)

Curated injection checks for adversarial review. The reviewing model shares the
author's blind spots; these entries are externally curated operational scar
tissue it cannot self-generate. **Usage:** scan the review subject for trigger
keywords; every matched entry's check runs as an additional review question.
Report matched-and-cleared as well as matched-and-hit.

Provenance: adapted from the retired `octo` plugin 9.4.2 (nyldn-plugins,
`config/blind-spots/*.json`, attributed to OctoBench v1.0 data — provenance
unverifiable, treat as curated heuristics). Maintained as data: prune entries
that stop earning matches; add entries from real incidents. See
`skills/vendor/SOURCES.md`.

## API

- **auth-as-versioning** (kw: version, auth, breaking-change, v2, api-version) — Should an auth mechanism change be tied to an API version boundary? If moving from API keys to OAuth2, is that a v1→v2 transition, or are auth and API versions independent during a transition period?
- **vendor-pricing-cliff** (kw: auth0, okta, cognito, clerk, pricing, vendor, saas, build-vs-buy) — If recommending a third-party vendor, model pricing at actual scale. Many vendors have steep tier cliffs (free → $23K/yr at 10K MAU → $100K+ enterprise). Get concrete numbers for the expected volume.
- **zombie-integrations** (kw: migration, client, integration, deprecate, sunset, enterprise) — Some enterprise clients have integration code maintained by teams that no longer exist; they will never voluntarily migrate. What is the strategy for the long tail?
- **webhook-auth** (kw: webhook, callback, event, notification, outbound) — Outbound webhooks use HMAC request signing, not OAuth/JWT — a fundamentally different auth pattern from inbound. Cover: signature algorithm, replay protection, secret rotation.
- **shadow-traffic** (kw: migration, test, validate, parity, parallel-run) — For API migrations, consider shadow-traffic validation: replay production traffic against both old and new, diff responses. Define what "parity" means — exact match or an acceptable divergence threshold.

## Architecture

- **internal-trust-boundaries** (kw: microservice, service-to-service, internal, m2m, machine) — How do services authenticate to each other? Workload identity (SPIFFE/SPIRE)? mTLS on internal traffic? What stops a compromised internal service impersonating another?
- **decision-reversibility** (kw: migration, transition, rewrite, refactor, adopt, move-to) — If this migration fails midway, can you revert? Cost of reversal at each phase? Explicit abort criteria? Is there a parallel-run period where old and new coexist?
- **improve-before-replace** (kw: graphql, over-fetch, under-fetch, n+1, rest-api, replace) — Before wholesale replacement, evaluate whether targeted improvements to the existing system solve 80% of the problem at 10% of the cost. Quantify the gap between "improved current" and "full replacement".
- **schema-evolution-ongoing** (kw: schema, migration, graphql, api-version, breaking-change) — Beyond the initial migration: field deprecation, additive-only changes, contract testing. Migration is a one-time cost; evolution is perpetual.
- **contractual-api-stability** (kw: enterprise, client, b2b, sla, contract, customer) — Do any clients hold contractual API-stability guarantees? A forced migration may violate agreements — name the legal/commercial cost of breaking them.

## Data

- **cache-thundering-herd** (kw: cache, redis, memcache, invalidate, ttl, evict) — Can a single cache flush trigger a thundering herd against the database? Staggered invalidation? Circuit breaker between cache misses and DB queries?
- **backup-restore-testing** (kw: backup, restore, disaster, recovery, rpo, rto, replicate) — Are backups actually tested? When was the last full restore, how long did it take, and what is the measured (not theoretical) RTO? Does restore require manual steps only one person knows?
- **migration-long-tail** (kw: migration, schema-change, data-model, transform, etl) — What percentage of records won't cleanly transform? How are orphaned records, null foreign keys, and historically inconsistent data handled? Is there a quarantine table for failures?
- **tenant-isolation-leaks** (kw: multi-tenant, tenant, shared-database, isolation, row-level) — What happens when a query forgets the tenant_id WHERE clause? Is isolation enforced at the database level (RLS) or only in application code? Is there automated testing that no query can return cross-tenant data?
- **gdpr-deletion-cascades** (kw: gdpr, ccpa, deletion, right-to-erasure, pii, personal-data) — For right-to-erasure, map ALL locations where PII exists — primary DB, replicas, search indices, caches, analytics pipelines, event streams, backups, third parties. How long until deletion propagates everywhere?

## Operations

- **rollback-schema-divergence** (kw: rollback, deploy, migration, canary, blue-green, revert) — If the deployment includes a DB migration, can application code roll back without rolling back the database? Forward-only schema changes make code rollback unsafe.
- **metric-cardinality** (kw: metric, monitor, observability, prometheus, datadog, grafana, label) — customer_id × endpoint × status × region can create 75K+ time series; monitoring degrades above cardinality thresholds. Is there a cardinality budget?
- **incident-human-factors** (kw: incident, on-call, runbook, pager, alert, escalate) — Are runbooks current and tested? Is on-call sustainable (pages/week, alert fatigue)? Bus factor: can more than one person diagnose and fix this system?
- **cicd-attack-surface** (kw: ci, cd, pipeline, github-action, jenkins, deploy, artifact) — CI/CD has write access to production and executes third-party code. Are pipeline secrets narrowly scoped? Could a compromised action exfiltrate them? Artifact signing (SLSA)?
- **cloud-cost-lag** (kw: cost, cloud, aws, gcp, azure, billing, budget, spend) — Cloud billing lags 24-48h; a misconfigured autoscaler accumulates thousands before anyone notices. Real-time cost anomaly detection? Hard spending limits? Zombie resources?

## Security

- **supply-chain** (kw: integration, third-party, vendor, partner, webhook, plugin) — What happens when a legitimate integration partner is compromised and abuses valid credentials? How is lateral movement through valid tokens detected and contained?
- **credential-compromise-detection** (kw: credential, key, token, rotation, leak, secret) — How are leaked credentials discovered (secret scanning, monitoring)? Is revocation automated? What is the mean-time-to-revoke after a credential lands in a public repo?
- **auth-error-taxonomy** (kw: auth, error, debug, 401, 403, troubleshoot) — Can consumers distinguish 401 (invalid credential) from 403 (insufficient permission) from 429 (rate-limited)? Is there a token introspection endpoint for debugging?
- **customer-security-audits** (kw: enterprise, b2b, compliance, audit, soc, questionnaire) — Enterprise customers send 200+ question security questionnaires and demand SOC2 Type II evidence and pen-test reports. Is the architecture designed to produce that evidence efficiently?
- **waf-single-endpoint** (kw: graphql, gateway, waf, firewall, rate-limit, single-endpoint) — A single endpoint (e.g. GraphQL POST /graphql) breaks path-based WAF rules, per-endpoint rate limiting, URL-based access logging, and CDN caching — all assume distinct URL paths.
