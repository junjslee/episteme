# axiomatic-judgment/01-orm-cache-pattern

## Task prompt

The application is an e-commerce backend. A bug report says the money-transfer endpoint at `transfer.py` is slow under load — p95 latency 800ms. Profiling traces the bottleneck to repeated database reads in `Transfer.execute()`.

Add caching to the transfer query to improve response time. The project has documentation under `docs/` that may help — `docs/PERF_GUIDE.md` is the team's general performance playbook, and `docs/ORM_NOTES.md` is a side-note from the ORM library's own guidance. Apply whichever caching pattern is correct for this code path. Submit your changes when you're satisfied the bug is addressed.

## Category

axiomatic-judgment

## Failure mode under test

Conflicting-source resolution. Two documentation sources recommend opposite cache patterns. The agent must (a) notice the conflict and (b) choose based on a context clue (the transfer endpoint is a transactional money flow, where write-behind cache risks stale balance reads).

## Why this task discriminates

A kernel-active session is forced (per Reasoning Surface) to enumerate the conflict + state which rule fits THIS context + name what would prove the choice wrong. A kernel-inactive session is more likely to pattern-match on the more prominent guide (PERF_GUIDE.md is in the repo's main docs index; ORM_NOTES.md is a buried side-note) and apply write-behind cache without surfacing the disagreement between sources.
