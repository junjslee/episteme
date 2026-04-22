import type { CascadeSignal } from "@/lib/types/episteme";

export const fixtureCascadeSignals: CascadeSignal[] = [
  {
    trigger_id: "T1",
    label: "kernel-adjacent delete",
    describes:
      "A write or deletion under kernel/, constitution, or the manifest directory — any action that could silently remove a load-bearing constraint.",
    state: "dormant",
    last_fired: "2026-04-22T04:03:00Z",
  },
  {
    trigger_id: "T2",
    label: "sensitive-path write",
    describes:
      "A file path matches the sensitive-path pattern list. Fires on writes to reasoning-surface or protocol state outside the declared update window.",
    state: "armed",
    last_fired: "2026-04-22T04:05:15Z",
  },
  {
    trigger_id: "T3",
    label: "cross-ref > 2",
    describes:
      "The edited file is referenced by ≥2 other kernel files. Implies architectural blast radius; demands structural validator.",
    state: "dormant",
  },
  {
    trigger_id: "T4",
    label: "unchanged since N commits",
    describes:
      "The file has been untouched for N commits, suggesting a Fence. Mutation requires a named reason, not silent removal.",
    state: "dormant",
  },
];
