/** Gate loop phases, shared by the 3D scene and the DOM overlay. */
export type GatePhase = "approach" | "held" | "verified" | "reset";

/** The three Reasoning Surface fields the gate materialises while holding. */
export const SURFACE_FIELDS = ["core_question", "unknowns", "disconfirmation"] as const;
