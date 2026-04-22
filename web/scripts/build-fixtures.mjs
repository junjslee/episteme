#!/usr/bin/env node
/**
 * Emit static JSONL / JSON snapshots under public/data/ so that:
 *   · v1 ships with ready-to-serve static artifacts
 *   · v2 API route handlers have a known-shape file to fall back to
 *   · v3 external consumers can hit the raw artifact from /data/*
 *
 * Source of truth for this snapshot lives in src/lib/fixtures/*.ts —
 * we re-declare the shapes inline here to keep this script ESM-portable
 * without a TS build step. Edits must be mirrored.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const OUT = join(ROOT, "public", "data");
mkdirSync(OUT, { recursive: true });

// Deterministic display-hash — matches src/lib/fixtures/chain.ts::h
function h(s) {
  let seed = 0;
  for (let i = 0; i < s.length; i++) {
    seed = (seed * 31 + s.charCodeAt(i)) >>> 0;
  }
  const hex = [];
  let cur = seed;
  for (let i = 0; i < 16; i++) {
    cur = (cur * 1103515245 + 12345) >>> 0;
    hex.push(cur.toString(16).padStart(8, "0"));
  }
  return hex.join("").slice(0, 64);
}

const GENESIS = "0".repeat(64);
const base = new Date("2026-04-22T04:00:00Z").getTime();

const steps = [
  ["surface_sealed", "RS · CP10 scaffolding", "rs-2026-04-22-cp10"],
  ["protocol_synthesized", "cascade-graceful-degrade", "pr-cascade-degrade"],
  ["verification_trace", "528 → 565 green", "vt-cp10-tests"],
  ["cascade_detected", "sensitive-path write", "cd-kernel-state"],
  ["deferred_discovery", "exempt kernel state files", "dd-kernel-state-exempt"],
  ["protocol_applied", "fence-pattern validate", "pr-fence-pattern"],
  ["surface_sealed", "RS · v1.0 tag prep", "rs-v1-0-tag"],
  ["protocol_synthesized", "hash-chain-self-verify", "pr-self-verify"],
  ["verification_trace", "565 → 565 green", "vt-v1-tag"],
  ["deferred_discovery", "cross-ref counter precision", "dd-cross-ref-count"],
  ["protocol_applied", "disconfirmation-required", "pr-disc-required"],
  ["cascade_detected", "SUMMARY rebalance", "cd-summary-rebalance"],
  ["surface_sealed", "RS · gtm-site init", "rs-gtm-init"],
];

const chain = [
  {
    seq: 0,
    ts: new Date(base).toISOString(),
    kind: "genesis",
    label: "chain init",
    prev_hash: GENESIS,
    this_hash: h("genesis"),
    ref: "genesis",
  },
];

steps.forEach(([kind, label, ref], i) => {
  const seq = i + 1;
  const prev = chain[seq - 1].this_hash;
  chain.push({
    seq,
    ts: new Date(base + seq * 45_000).toISOString(),
    kind,
    label,
    prev_hash: prev,
    this_hash: h(`${seq}|${kind}|${ref}|${prev}`),
    ref,
  });
});

const protocols = [
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
    last_chain_hash: chain[2].this_hash,
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
      decision: "Block removal at validator; require named-reason to proceed",
    },
    triggers: [
      "kernel-adjacent deletion",
      "cross-ref count > 2",
      "unchanged-since-N commits",
    ],
    invocations: 11,
    confidence: 0.94,
    synthesized_at: "2026-04-22T04:04:15Z",
    last_chain_hash: chain[6].this_hash,
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
    last_chain_hash: chain[8].this_hash,
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
    triggers: ["surface sealed", "disconfirmation empty", "tautological pattern match"],
    invocations: 6,
    confidence: 0.82,
    synthesized_at: "2026-04-22T04:08:45Z",
    last_chain_hash: chain[11].this_hash,
  },
];

const surface = {
  schema: "episteme/reasoning-surface@1",
  timestamp: "2026-04-22T04:30:00.000Z",
  domain: "complicated",
  core_question:
    "Does the Blueprint D scaffolding land the four-trigger cascade detector and six-field validator without orphan-reference regression across the declared blast radius?",
  hypothesis:
    "The cascade detector fires correctly on architectural edits and the validator can be admitted through the guard's existing Fence slot without regressing the 528/528 baseline.",
  knowns: [
    "HEAD is 78c271f after CP9; 528/528 tests passing before commit",
    "Cascade detector and six-field validator modules are written with the four-trigger selector",
    "architectural_cascade blueprint YAML is populated with compound-selector metadata",
    "Scenario detector dispatches cascade before Fence via try/except graceful-degrade",
  ],
  unknowns: [
    "Whether the detector short-circuits before cross-ref lookup on non-cascade ops so p95 latency stays under 100ms",
    "Whether the sensitive-path pattern list covers kernel-adjacent directories without firing on prose mentions",
    "Whether the deferred-discovery writer lands one hash-chained record per entry with deterministic surfacing",
  ],
  assumptions: [
    "The Reasoning Surface write to state currently passes the cascade detector via a documented bypass",
    "The v1.0 RC soak begins immediately after CP10 lands; no further blueprints before v1.0.1",
    "A Blueprint D selector that false-positives on its own shipping commit is the strongest signal the selector needs tightening",
  ],
  disconfirmation:
    "Off-track if: (1) final test count drops below 528 — regression from wiring; (2) an unrelated Bash op fires Blueprint D after CP10 — detector over-triggers; (3) guard admits cascade ops whose surface lacks the six required fields — validation is broken.",
  flaw_classification: "schema-implementation-drift",
  posture_selected: "refactor",
  blast_radius_map: [
    { surface: "hooks/cascade-detector-module", status: "needs_update" },
    { surface: "hooks/blueprint-d-module", status: "needs_update" },
    { surface: "blueprints/architectural-cascade-yaml", status: "needs_update" },
    { surface: "hooks/scenario-detector-module", status: "needs_update" },
    { surface: "hooks/guard-module", status: "needs_update" },
    { surface: "tests/blueprint-d-cascade-tests", status: "needs_update" },
    { surface: "docs/design-v1-0-spec", status: "needs_update" },
    {
      surface: "kernel/constitution",
      status: "not-applicable",
      rationale: "Philosophy is set; this is scaffolding",
    },
  ],
  deferred_discoveries: [
    {
      description:
        "Blueprint D detector fires on writes to the kernel's own state files because the sensitive-path pattern matches broadly",
      observable:
        "Write tool call with file_path in kernel state directory produces exit 2 with cascade label",
      log_only_rationale:
        "Fix requires editing the detector to exempt kernel state files, which ALSO fires the detector — chicken and egg. Logged for v1.0.1.",
    },
    {
      description:
        "Cross-ref count proxy uses byte-occurrence; a file mentioning a basename 3 times counts as 3 cross-refs",
      observable:
        "A file with 3 mentions of a basename but 1 import crosses the 2-threshold on name alone",
      log_only_rationale:
        "Per-file presence counting needs walking files individually. Accept the proxy for RC; tighten if FPs accumulate post-soak.",
    },
    {
      description:
        "Kernel SUMMARY should reference Blueprint D by name now that all four blueprints are realized",
      observable: "grep for Blueprint D in kernel SUMMARY returns zero hits",
      log_only_rationale:
        "30-line budget makes surgical insert tricky without full rebalance. Logged for post-soak pass.",
    },
  ],
};

const toJSONL = (arr) => arr.map((o) => JSON.stringify(o)).join("\n") + "\n";

writeFileSync(join(OUT, "chain.jsonl"), toJSONL(chain));
writeFileSync(join(OUT, "protocols.jsonl"), toJSONL(protocols));
writeFileSync(
  join(OUT, "reasoning-surface.json"),
  JSON.stringify(surface, null, 2) + "\n",
);

console.log(`wrote ${chain.length} chain entries → public/data/chain.jsonl`);
console.log(`wrote ${protocols.length} protocols → public/data/protocols.jsonl`);
console.log(`wrote reasoning-surface.json`);
