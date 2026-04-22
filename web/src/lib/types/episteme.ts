/**
 * Domain types for the episteme kernel's on-disk artifacts.
 * Every field maps to something the real kernel emits.
 */

/** Status of a blast-radius surface. */
export type SurfaceStatus =
  | "needs_update"
  | "updated"
  | "not-applicable"
  | "deferred";

export interface BlastRadiusEntry {
  surface: string;
  status: SurfaceStatus;
  rationale?: string;
}

export interface SyncPlanEntry {
  surface: string;
  action: string;
}

export interface DeferredDiscovery {
  description: string;
  observable: string;
  log_only_rationale: string;
  /** Hash-chained in protocols.jsonl when written */
  id?: string;
  timestamp?: string;
}

/** Assumption can be a plain string or a structured claim+falsification. */
export type Assumption =
  | string
  | { claim: string; falsification: string };

export type DomainClass =
  | "clear"
  | "complicated"
  | "complex"
  | "chaotic"
  | "disorder";

/**
 * The Reasoning Surface — the kernel's central K/U/A/D artifact.
 * Mirrors episteme/reasoning-surface@1 JSON schema.
 */
export interface ReasoningSurface {
  schema: "episteme/reasoning-surface@1";
  timestamp: string;
  domain: DomainClass;
  tacit_call?: boolean;
  core_question: string;
  hypothesis?: string;
  knowns: string[];
  unknowns: string[];
  assumptions: Assumption[];
  disconfirmation: string | string[];
  flaw_classification?: string;
  posture_selected?: "patch" | "refactor" | "defer";
  patch_vs_refactor_evaluation?: string;
  blast_radius_map?: BlastRadiusEntry[];
  sync_plan?: SyncPlanEntry[];
  deferred_discoveries?: DeferredDiscovery[];
}

/**
 * Append-only hash-chain entry. One line per record in protocols.jsonl.
 * Pillar 2 substrate. Tamper-evidence by prev-hash linkage.
 */
export interface ChainEntry {
  /** Monotonic index, starts at 0 for genesis */
  seq: number;
  /** ISO timestamp */
  ts: string;
  /** Type of record written to the chain */
  kind:
    | "protocol_synthesized"
    | "protocol_applied"
    | "surface_sealed"
    | "deferred_discovery"
    | "cascade_detected"
    | "verification_trace"
    | "genesis";
  /** Human label */
  label: string;
  /** SHA-256 of canonical serialized prev entry. Genesis = 64 zeros. */
  prev_hash: string;
  /** SHA-256 of this entry's canonical content */
  this_hash: string;
  /** Reference to the payload — usually a protocol id or surface decision_id */
  ref?: string;
  /** True when the chain verification fails at this link */
  tamper_suspected?: boolean;
}

/**
 * A synthesized cognitive protocol extracted by Pillar 3.
 * Lives in a protocols directory, referenced from the chain.
 */
export interface Protocol {
  id: string;
  name: string;
  /** Short operator-readable summary */
  summary: string;
  /** Structured because-chain */
  because: {
    observed_signal: string;
    inferred_cause: string;
    decision: string;
  };
  /** Trigger conditions that fire this protocol */
  triggers: string[];
  /** Counted invocations since synthesis */
  invocations: number;
  confidence: number;
  synthesized_at: string;
  /** Last hash it was written under */
  last_chain_hash?: string;
  /** Optional authoring provenance */
  provenance?: {
    surface_id?: string;
    decision_id?: string;
  };
}

/** Blueprint D cascade-detector trigger state */
export type TriggerState = "dormant" | "armed" | "firing";

export interface CascadeSignal {
  trigger_id: "T1" | "T2" | "T3" | "T4";
  label: string;
  state: TriggerState;
  /** One-sentence trigger description */
  describes: string;
  last_fired?: string;
}

export interface Cascade {
  detected_at: string;
  triggers: CascadeSignal[];
  /** Surfaces affected */
  blast_radius: string[];
  /** Whether the operator was notified */
  notified: boolean;
}

/** A kernel telemetry event; rendered by TelemetryTicker */
export interface TelemetryEvent {
  id: string;
  ts: string;
  level: "info" | "signal" | "warn" | "error";
  code: string;
  message: string;
}
