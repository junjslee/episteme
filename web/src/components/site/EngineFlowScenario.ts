/**
 * EngineFlowScenario — the scripted interrogation the engine stage plays.
 *
 * One real story, told twice on the page: the README memory-eval worked
 * example (7% thumbs-up lift / 30% length confound). The data lives here so
 * EngineFlowStatic (server, reduced-motion / no-JS) and EngineFlow (client,
 * animated) render the *same* scenario from the same source — the animation
 * and the static map can never drift apart.
 *
 * Mechanism facts the stage must encode (DESIGN_V2 §3):
 * - claims are tiered measured / cited / inferred / assumed; load-bearing flagged
 * - the verifier is a fresh context that receives ONLY the claim — never the
 *   draft's prose (the seal draws first; the ghost draft is shaken off at it)
 * - evidence verdicts per claim: supported / refuted / unverifiable
 * - opposition is argued as an advocate; weakest link names the cheapest
 *   decisive test; disconfirmation is pre-committed
 * - verdict enum: proceed / proceed-with-revision / stop — stop fails closed
 * - a non-null lesson becomes a context-scoped, hash-chained protocol
 */

export type ClaimTier = "measured" | "cited" | "inferred" | "assumed";
export type EvidenceResult = "supported" | "refuted" | "unverifiable";
export type Verdict = "proceed" | "proceed-with-revision" | "stop";

export interface EngineClaim {
  id: string;
  text: string;
  tier: ClaimTier;
  loadBearing: boolean;
  /** Only load-bearing claims are dispatched to the fresh-context verifier. */
  result?: EvidenceResult;
  /** One-line evidence note returned by the verifier. */
  evidence?: string;
}

export interface EngineScenario {
  decision: string;
  claims: EngineClaim[];
  opposition: string;
  weakestLink: string;
  disconfirmation: string;
  verdict: Verdict;
  lesson: string;
  /** Real first protocol reference (the falsifiability-night protocol). */
  protocolId: string;
}

export const SCENARIO: EngineScenario = {
  decision: "“memory system improves response quality — keep shipping.”",
  claims: [
    {
      id: "c1",
      text: "+7% thumbs-up lift over 30 days",
      tier: "measured",
      loadBearing: true,
      result: "supported",
      evidence: "reproduces in a clean query",
    },
    {
      id: "c2",
      text: "with-memory responses run ~30% longer",
      tier: "measured",
      loadBearing: false,
    },
    {
      id: "c3",
      text: "the lift comes from memory, not length",
      tier: "inferred",
      loadBearing: true,
      result: "unverifiable",
      evidence: "length was never controlled",
    },
    {
      id: "c4",
      text: "thumbs-up tracks answer quality",
      tier: "assumed",
      loadBearing: true,
      result: "refuted",
      evidence: "it tracks confidence, not correctness",
    },
  ],
  opposition:
    "length alone predicts thumbs-up — the lift may be the length effect wearing a memory badge.",
  weakestLink: "c3 · cheapest decisive test: re-run with length controlled",
  disconfirmation: "lift disappears under length control",
  verdict: "proceed-with-revision",
  lesson: "control for response length before attributing quality lift",
  protocolId: "lh_71f88adef21147df",
};

/** Claims that travel into the verifier, in checking order. */
export const VERIFIED_CLAIMS = SCENARIO.claims.filter(
  (c): c is EngineClaim & { result: EvidenceResult; evidence: string } =>
    c.loadBearing && c.result !== undefined && c.evidence !== undefined,
);

/* Token-only styling maps — shared so both renderers stamp identically. */

export const TIER_STYLES: Record<ClaimTier, string> = {
  measured: "border-line text-bone",
  cited: "border-line text-bone",
  inferred: "border-unknown/40 text-unknown",
  assumed: "border-disconfirm/40 text-disconfirm",
};

export const RESULT_STYLES: Record<EvidenceResult, string> = {
  supported: "border-verified/50 bg-verified/[0.05] text-verified",
  refuted: "border-disconfirm/50 bg-disconfirm/[0.06] text-disconfirm",
  unverifiable: "border-unknown/50 bg-unknown/[0.05] text-unknown",
};
