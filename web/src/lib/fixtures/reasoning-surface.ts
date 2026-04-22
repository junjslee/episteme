import type { ReasoningSurface } from "@/lib/types/episteme";

/**
 * Demo surface — echoes the shape of the live .episteme/reasoning-surface.json
 * with fields trimmed for marketing display. The real surface runs longer.
 */
export const fixtureSurface: ReasoningSurface = {
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
