import type { ChainEntry, Protocol, TelemetryEvent } from "@/lib/types/episteme";

/**
 * Synthetic hash-chain. Not real SHA-256 — deterministic display-hashes that
 * look plausible and chain correctly. When live data ships, this gets replaced
 * by parseJSONL(protocols.jsonl) → markChainIntegrity.
 */
const h = (s: string): string => {
  // Deterministic pseudo-hash for display. DO NOT use for integrity.
  let seed = 0;
  for (let i = 0; i < s.length; i++) {
    seed = (seed * 31 + s.charCodeAt(i)) >>> 0;
  }
  const hex: string[] = [];
  let cur = seed;
  for (let i = 0; i < 16; i++) {
    cur = (cur * 1103515245 + 12345) >>> 0;
    hex.push(cur.toString(16).padStart(8, "0"));
  }
  return hex.join("").slice(0, 64);
};

const GENESIS = "0".repeat(64);

function entry(
  seq: number,
  kind: ChainEntry["kind"],
  label: string,
  ref: string,
  prev: string,
  tsOffsetSec: number,
): ChainEntry {
  const base = new Date("2026-04-22T04:00:00Z").getTime();
  const ts = new Date(base + tsOffsetSec * 1000).toISOString();
  return {
    seq,
    ts,
    kind,
    label,
    prev_hash: prev,
    this_hash: h(`${seq}|${kind}|${ref}|${prev}`),
    ref,
  };
}

const _raw: ChainEntry[] = [];
_raw.push({
  seq: 0,
  ts: "2026-04-22T04:00:00.000Z",
  kind: "genesis",
  label: "chain init",
  prev_hash: GENESIS,
  this_hash: h("genesis"),
  ref: "genesis",
});

for (let i = 1; i < 14; i++) {
  const prev = _raw[i - 1]!.this_hash;
  if (i === 1) _raw.push(entry(i, "surface_sealed", "RS · CP10 scaffolding", "rs-2026-04-22-cp10", prev, i * 45));
  else if (i === 2) _raw.push(entry(i, "protocol_synthesized", "cascade-graceful-degrade", "pr-cascade-degrade", prev, i * 45));
  else if (i === 3) _raw.push(entry(i, "verification_trace", "528 → 565 green", "vt-cp10-tests", prev, i * 45));
  else if (i === 4) _raw.push(entry(i, "cascade_detected", "sensitive-path write", "cd-kernel-state", prev, i * 45));
  else if (i === 5) _raw.push(entry(i, "deferred_discovery", "exempt kernel state files", "dd-kernel-state-exempt", prev, i * 45));
  else if (i === 6) _raw.push(entry(i, "protocol_applied", "fence-pattern validate", "pr-fence-pattern", prev, i * 45));
  else if (i === 7) _raw.push(entry(i, "surface_sealed", "RS · v1.0 tag prep", "rs-v1-0-tag", prev, i * 45));
  else if (i === 8) _raw.push(entry(i, "protocol_synthesized", "hash-chain-self-verify", "pr-self-verify", prev, i * 45));
  else if (i === 9) _raw.push(entry(i, "verification_trace", "565 → 565 green", "vt-v1-tag", prev, i * 45));
  else if (i === 10) _raw.push(entry(i, "deferred_discovery", "cross-ref counter precision", "dd-cross-ref-count", prev, i * 45));
  else if (i === 11) _raw.push(entry(i, "protocol_applied", "disconfirmation-required", "pr-disc-required", prev, i * 45));
  else if (i === 12) _raw.push(entry(i, "cascade_detected", "SUMMARY rebalance", "cd-summary-rebalance", prev, i * 45));
  else if (i === 13) _raw.push(entry(i, "surface_sealed", "RS · gtm-site init", "rs-gtm-init", prev, i * 45));
}

export const fixtureChain: ChainEntry[] = _raw;

export const fixtureProtocols: Protocol[] = [
  {
    id: "pr-cascade-degrade",
    name: "cascade-graceful-degrade",
    summary:
      "Dispatch cascade detector before Fence via try/except ImportError so detector absence never breaks the guard pipeline.",
    because: {
      observed_signal:
        "Scenario detector hot path imports Blueprint D module unconditionally",
      inferred_cause:
        "Hard import creates a failure axis if the module ever ships in a broken state",
      decision:
        "Wrap the import in try/except ImportError and fall back to prior pipeline",
    },
    triggers: [
      "scenario_detector.py edited",
      "blueprint_d module referenced",
      "hot_path_import change detected",
    ],
    invocations: 4,
    confidence: 0.88,
    synthesized_at: "2026-04-22T04:01:30Z",
    last_chain_hash: _raw[2]!.this_hash,
    provenance: { decision_id: "cp10-scaffolding" },
  },
  {
    id: "pr-fence-pattern",
    name: "fence-pattern-validate",
    summary:
      "Preserve unexplained kernel constraints until their purpose is reconstructed. Removal requires named reason.",
    because: {
      observed_signal:
        "Refactor attempted to remove a constraint whose rationale was not cited",
      inferred_cause:
        "Hidden constraints become hidden objectives when silently removed",
      decision:
        "Block removal at validator; require named-reason to proceed",
    },
    triggers: [
      "kernel-adjacent deletion",
      "cross-ref count > 2",
      "unchanged-since-N commits",
    ],
    invocations: 11,
    confidence: 0.94,
    synthesized_at: "2026-04-22T04:04:15Z",
    last_chain_hash: _raw[6]!.this_hash,
    provenance: { decision_id: "cp10-scaffolding" },
  },
  {
    id: "pr-self-verify",
    name: "hash-chain-self-verify",
    summary:
      "On session start, walk the chain and report any prev_hash mismatch before admitting new writes.",
    because: {
      observed_signal:
        "Pillar 2 guarantees tamper-evidence only when the walk runs on boot",
      inferred_cause:
        "A silent corruption at rest is indistinguishable from a tampered replay",
      decision:
        "Mandatory walk-at-boot; fail-closed on mismatch with operator alert",
    },
    triggers: [
      "session start",
      "protocols.jsonl modified out-of-band",
      "prev_hash ≠ prior this_hash",
    ],
    invocations: 2,
    confidence: 0.91,
    synthesized_at: "2026-04-22T04:06:30Z",
    last_chain_hash: _raw[8]!.this_hash,
  },
  {
    id: "pr-disc-required",
    name: "disconfirmation-required",
    summary:
      "Reject a Reasoning Surface whose disconfirmation field is empty or tautological. A hypothesis without a failure mode is not a bet.",
    because: {
      observed_signal:
        "Surfaces were shipping with disconfirmation := 'if it fails, stop'",
      inferred_cause:
        "Tautological disconfirmation defeats Popper's criterion; rules out nothing",
      decision:
        "Validator checks disconfirmation string for tautological patterns and rejects",
    },
    triggers: [
      "surface sealed",
      "disconfirmation empty",
      "tautological pattern match",
    ],
    invocations: 6,
    confidence: 0.82,
    synthesized_at: "2026-04-22T04:08:45Z",
    last_chain_hash: _raw[11]!.this_hash,
  },
];

export const fixtureTelemetry: TelemetryEvent[] = [
  { id: "e1", ts: "2026-04-22T04:00:00Z", level: "info", code: "KRN.BOOT", message: "kernel boot · 565/565 tests green at HEAD 78c271f" },
  { id: "e2", ts: "2026-04-22T04:00:45Z", level: "signal", code: "RS.SEAL", message: "reasoning-surface sealed · cp10-scaffolding · domain=complicated" },
  { id: "e3", ts: "2026-04-22T04:01:30Z", level: "signal", code: "PR.SYN", message: "protocol synthesized · cascade-graceful-degrade · conf=0.88" },
  { id: "e4", ts: "2026-04-22T04:02:15Z", level: "info", code: "VT.PASS", message: "verification_trace · 528 → 565 passing" },
  { id: "e5", ts: "2026-04-22T04:03:00Z", level: "warn", code: "CD.FIRE", message: "cascade_detected · T2 sensitive-path · kernel/state/reasoning-surface.json" },
  { id: "e6", ts: "2026-04-22T04:03:45Z", level: "info", code: "DD.LOG", message: "deferred_discovery · exempt kernel state files · log-only for v1.0.1" },
  { id: "e7", ts: "2026-04-22T04:04:30Z", level: "signal", code: "PR.APP", message: "protocol_applied · fence-pattern-validate · invocations=11" },
  { id: "e8", ts: "2026-04-22T04:05:15Z", level: "info", code: "RS.SEAL", message: "reasoning-surface sealed · v1-0-tag-prep · domain=complicated" },
  { id: "e9", ts: "2026-04-22T04:06:00Z", level: "signal", code: "PR.SYN", message: "protocol synthesized · hash-chain-self-verify · conf=0.91" },
  { id: "e10", ts: "2026-04-22T04:06:45Z", level: "info", code: "VT.PASS", message: "verification_trace · 565 → 565 green · pre-tag" },
];
