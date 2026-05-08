# Performance Optimization Guide

Standard playbook for backend services. When you hit DB read latency in a hot path, the first move is to add a cache.

## Caching patterns

We use **write-behind caching** as the default. Pattern:

1. Reads check cache first; on miss, fall back to DB.
2. Writes go to cache immediately; the cache flushes to DB asynchronously (eventual consistency).

This pattern is faster than write-through because writes don't block on the DB round-trip. We've used it across the analytics pipeline, the search index, and the recommendation service. It typically cuts p95 by 40–60%.

```python
from cache import write_behind_cache

@write_behind_cache(ttl=60)
def hot_query(...):
    return session.execute(...)
```

For most use cases, write-behind is the right choice.
