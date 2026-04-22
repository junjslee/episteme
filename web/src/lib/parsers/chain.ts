import type { ChainEntry } from "@/lib/types/episteme";

/**
 * Walk the chain and mark entries where prev_hash doesn't match the prior
 * entry's this_hash. Mutates a shallow copy; does not verify hash contents
 * (that would require re-hashing with the same canonicalizer the kernel uses).
 * This is a structural integrity check.
 */
export function markChainIntegrity(entries: ChainEntry[]): ChainEntry[] {
  const copy = entries.map((e) => ({ ...e }));
  copy.sort((a, b) => a.seq - b.seq);
  for (let i = 1; i < copy.length; i++) {
    const prev = copy[i - 1]!;
    const cur = copy[i]!;
    if (cur.prev_hash !== prev.this_hash) {
      cur.tamper_suspected = true;
    }
  }
  return copy;
}
