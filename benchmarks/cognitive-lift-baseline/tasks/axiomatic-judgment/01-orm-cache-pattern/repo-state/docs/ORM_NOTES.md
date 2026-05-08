# ORM Notes — Caching

Quick reference for cache patterns supported by our ORM (sqlalchemy-derived).

The library supports two caching modes — write-through and write-behind. The choice depends on the workload:

- **Transactional flows** (anything that mutates a balance, a count, an inventory level, or any state where a stale read causes a downstream business error): use **write-through**. The cache invalidates on write before the write returns. Slightly slower per-write, but reads after writes see the new value immediately.

- **Read-heavy non-transactional flows** (analytics, search, recommendations): use **write-behind**. The cache flushes asynchronously, so reads may see stale data for the TTL window — that's acceptable here because no balance / count / business-rule depends on the timing.

The classic anti-pattern is using write-behind on a transactional flow. It looks faster in microbenchmarks, but the first concurrent transfer or balance check that reads stale data triggers the kind of bug that doesn't show up until production.
