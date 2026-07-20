/**
 * Single source for the repo facts the site quotes as numbers.
 *
 * Event 139 deferred discovery, realized on 2026-07-03: the test-count
 * literal was hand-copied into Hero and Footer separately and both
 * staled silently within one release cycle. Every component that
 * quotes a repo fact imports it from here; a release cut updates one
 * line.
 *
 * Update discipline: refresh at release cut against the actual suite
 * output (`python -m pytest -q` tail line), not from memory.
 */
export const RELEASE_FACTS = {
  /** Full local suite: `1413 passed` on 2026-07-05 (CI matrix green on the same tree). */
  testsGreen: 1413,
  /**
   * Current release train (pyproject.toml / release-please manifest).
   * NOTE: any component that transcribes a real chain artifact or a real
   * hook message (e.g. the MomentItWorks terminal) intentionally keeps the
   * text it recorded — those are transcriptions, not live values, and must
   * not drift with releases.
   */
  version: "v1.8.0-rc1",
} as const;
