"""Registry of the 5-stage cognitive practice + each stage's cognitive moves.

Source of truth: `core/memory/global/cognitive_profile.md` (Decision Engine,
Foundational Mental Models) + `core/memory/global/workflow_policy.md` (5-stage
workflow + Signal-over-Noise rules). This module indexes that authored
practice into machine-readable form — the dictionary keys are stable;
modifications require corresponding updates to those source-of-truth docs
and to `docs/THE_WAY_TO_THINK.md`.

Each `CognitiveMove` carries:
  - `id`: stable string identifier (e.g., "frame.core_question")
  - `stage`: which of the 5 stages it belongs to
  - `name`: human-readable label (e.g., "Core Question discipline")
  - `system_1_failure_counter`: the named System-1 failure mode this
    move counters (per Kahneman taxonomy + the operator's
    cognitive_profile.md § Foundational Mental Models)
  - `schema_field`: which signed-surface@1.0 field carries this move's
    residue (or None if the move is operator-cognitive rather than
    artifact-shaped)
  - `doc_anchor`: anchor in `docs/THE_WAY_TO_THINK.md` where the move
    is operationalized

The Hook validator and the `episteme practice` CLI both reference this
registry by `id`. Hook error messages name the violated cognitive move
rather than the violated schema field — when `core_question` is too
short, the hook says "Frame.CoreQuestion move skipped" instead of
"core_question length < 20".
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Literal, Optional


StageName = Literal["frame", "decompose", "execute", "verify", "handoff"]


@dataclass(frozen=True, slots=True)
class Stage:
    """One of the 5 stages of the practice."""

    id: StageName
    ordinal: int
    name: str
    purpose: str  # one-sentence purpose of the stage
    workflow_policy_anchor: str  # § anchor in workflow_policy.md
    way_to_think_anchor: str  # § anchor in docs/THE_WAY_TO_THINK.md


@dataclass(frozen=True, slots=True)
class CognitiveMove:
    """One specific cognitive move within a stage."""

    id: str  # e.g., "frame.core_question"
    stage: StageName
    name: str  # human-readable label
    description: str  # what the operator actually does
    system_1_failure_counter: str  # the named failure mode this counters
    schema_field: Optional[str]  # which signed-surface@1.0 field, or None
    doc_anchor: str  # anchor in docs/THE_WAY_TO_THINK.md


# ─── Stages ──────────────────────────────────────────────────────────────

STAGES: Dict[StageName, Stage] = {
    "frame": Stage(
        id="frame",
        ordinal=1,
        name="Frame",
        purpose="Name what you are actually deciding, what counts as success, what is known vs unknown vs assumed.",
        workflow_policy_anchor="workflow_policy.md § Stage Definitions § 1) Frame",
        way_to_think_anchor="THE_WAY_TO_THINK.md § 1.1 Frame",
    ),
    "decompose": Stage(
        id="decompose",
        ordinal=2,
        name="Decompose",
        purpose="Convert the framed decision into operational tasks, options, and a working hypothesis.",
        workflow_policy_anchor="workflow_policy.md § Stage Definitions § 2) Decompose",
        way_to_think_anchor="THE_WAY_TO_THINK.md § 1.2 Decompose",
    ),
    "execute": Stage(
        id="execute",
        ordinal=3,
        name="Execute",
        purpose="Run one bounded task at a time; prefer reversible moves first; record assumptions when data is incomplete.",
        workflow_policy_anchor="workflow_policy.md § Stage Definitions § 3) Execute",
        way_to_think_anchor="THE_WAY_TO_THINK.md § 1.3 Execute",
    ),
    "verify": Stage(
        id="verify",
        ordinal=4,
        name="Verify",
        purpose="Validate against the success metric, distinguish proven from inferred, mark residual unknowns explicitly.",
        workflow_policy_anchor="workflow_policy.md § Stage Definitions § 4) Verify",
        way_to_think_anchor="THE_WAY_TO_THINK.md § 1.4 Verify",
    ),
    "handoff": Stage(
        id="handoff",
        ordinal=5,
        name="Handoff",
        purpose="Persist authoritative docs; capture unresolved risks and the exact next action.",
        workflow_policy_anchor="workflow_policy.md § Stage Definitions § 5) Handoff",
        way_to_think_anchor="THE_WAY_TO_THINK.md § 1.5 Handoff",
    ),
}


# ─── Cognitive moves ─────────────────────────────────────────────────────

# Each move's id is stable. The hook validator + practice CLI dereference
# by id. Adding a move requires updating both this registry AND
# docs/THE_WAY_TO_THINK.md to keep the doc-code coupling honest.

COGNITIVE_MOVES: Dict[str, CognitiveMove] = {
    # ── Frame stage ──
    "frame.core_question": CognitiveMove(
        id="frame.core_question",
        stage="frame",
        name="Core Question discipline",
        description="Name the single question this decision is actually trying to answer. Not three loose questions; not a topic; one Core Question.",
        system_1_failure_counter="question substitution (Kahneman) — System 1 silently replaces the hard question with an easier nearby question",
        schema_field="surface.core_question",
        doc_anchor="THE_WAY_TO_THINK.md § 1.1 Frame · Core Question",
    ),
    "frame.knowns": CognitiveMove(
        id="frame.knowns",
        stage="frame",
        name="Knowns ledger",
        description="Enumerate verified facts with source artifacts. Not patterns recognized; verifiable, cited facts.",
        system_1_failure_counter="narrative fallacy (Taleb / Kahneman) — sparse data gets assembled into a coherent causal story",
        schema_field="surface.knowns",
        doc_anchor="THE_WAY_TO_THINK.md § 1.1 Frame · Distinction map",
    ),
    "frame.unknowns": CognitiveMove(
        id="frame.unknowns",
        stage="frame",
        name="Unknowns ledger with cost_of_ignorance",
        description="Name what you don't know, with the concrete cost of proceeding without knowing it. The cost field forces the utility filter — 'so what is the cost of staying ignorant?'",
        system_1_failure_counter="WYSIATI (Kahneman) — What You See Is All There Is; reasoning from what's present in context, blind to what's absent",
        schema_field="surface.unknowns",
        doc_anchor="THE_WAY_TO_THINK.md § 1.1 Frame · Distinction map (Unknowns)",
    ),
    "frame.assumptions": CognitiveMove(
        id="frame.assumptions",
        stage="frame",
        name="Assumptions with if_wrong_then + detectability",
        description="Surface load-bearing beliefs. For each, state what happens if it's wrong, and how detectable the failure is (pre-execution / post-execution-soft / post-execution-irreversible).",
        system_1_failure_counter="overconfidence (Kahneman) + hidden constraints (cognitive_profile.md § Governance Core)",
        schema_field="surface.assumptions",
        doc_anchor="THE_WAY_TO_THINK.md § 1.1 Frame · Distinction map (Assumptions)",
    ),
    "frame.constraint_regime": CognitiveMove(
        id="frame.constraint_regime",
        stage="frame",
        name="Constraint regime declaration",
        description="Name what is allowed, forbidden, costly. Make hidden constraints explicit — operator's own rule: 'Hidden constraints become hidden objectives.'",
        system_1_failure_counter="hidden constraints (cognitive_profile.md § Governance Core)",
        schema_field="surface.risk_classification",
        doc_anchor="THE_WAY_TO_THINK.md § 1.1 Frame · Constraint regime",
    ),
    "frame.reversibility": CognitiveMove(
        id="frame.reversibility",
        stage="frame",
        name="Reversibility classification",
        description="Classify this decision as reversible or irreversible. The classification governs the entire workflow's risk posture.",
        system_1_failure_counter="planning fallacy (Kahneman) — underestimation of consequence severity",
        schema_field="surface.risk_classification.reversibility",
        doc_anchor="THE_WAY_TO_THINK.md § 1.1 Frame · Reversibility",
    ),
    "frame.uncomfortable_friction": CognitiveMove(
        id="frame.uncomfortable_friction",
        stage="frame",
        name="Uncomfortable-friction anchor",
        description="Name the anomaly, inefficiency, or uncomfortable truth driving the decision. Not vague curiosity — a specific friction that demands resolution.",
        system_1_failure_counter="solution-first behavior (cognitive_profile.md § Cognitive Red Flags) — jumping to remedies without naming the problem",
        schema_field=None,  # operator-authored, cited within core_question or audit
        doc_anchor="THE_WAY_TO_THINK.md § 1.1 Frame · Uncomfortable friction",
    ),

    # ── Decompose stage ──
    "decompose.why_to_how": CognitiveMove(
        id="decompose.why_to_how",
        stage="decompose",
        name="Why → How translation",
        description="Convert the philosophical why into operational how. Name what can be measured or mapped now.",
        system_1_failure_counter="vague-curiosity drift (cognitive_profile.md § Decision Engine § Convert why → how quickly)",
        schema_field=None,
        doc_anchor="THE_WAY_TO_THINK.md § 1.2 Decompose · Why→How",
    ),
    "decompose.options_and_tradeoffs": CognitiveMove(
        id="decompose.options_and_tradeoffs",
        stage="decompose",
        name="Options ≥ 2 with tradeoffs (high-impact only)",
        description="For high-impact decisions, articulate at least two viable options with their trade-offs.",
        system_1_failure_counter="anchoring (Kahneman) — first-considered option dominates regardless of merit",
        schema_field=None,
        doc_anchor="THE_WAY_TO_THINK.md § 1.2 Decompose · Options",
    ),
    "decompose.because_chain": CognitiveMove(
        id="decompose.because_chain",
        stage="decompose",
        name="Because-chain (signal → cause → decision)",
        description="Trace the inference chain: observed signal → inferred cause / constraint → decision. Make the causal reasoning auditable.",
        system_1_failure_counter="pattern-match shortcut (cognitive_profile.md § Reasoning Core)",
        schema_field=None,
        doc_anchor="THE_WAY_TO_THINK.md § 1.2 Decompose · Because-chain",
    ),
    "decompose.hypothesis_as_bet": CognitiveMove(
        id="decompose.hypothesis_as_bet",
        stage="decompose",
        name="Hypothesis as a bet",
        description="State the working hypothesis with elicited confidence (0.0 – 1.0). Hypothesis quality = the bet you would take if you had to commit.",
        system_1_failure_counter="overconfidence + planning fallacy (Kahneman) — declared certainty exceeds calibrated accuracy",
        schema_field="surface.decision",
        doc_anchor="THE_WAY_TO_THINK.md § 1.2 Decompose · Hypothesis-as-bet",
    ),

    # ── Execute stage ──
    "execute.reversibility_first": CognitiveMove(
        id="execute.reversibility_first",
        stage="execute",
        name="Reversibility-first execution order",
        description="When multiple paths are open, prefer the reversible one first. Reserve irreversible moves for after confirmation.",
        system_1_failure_counter="planning fallacy (Kahneman) — commitment escalation before validation",
        schema_field="surface.risk_classification.reversibility",
        doc_anchor="THE_WAY_TO_THINK.md § 1.3 Execute · Reversibility-first",
    ),
    "execute.bounded_task": CognitiveMove(
        id="execute.bounded_task",
        stage="execute",
        name="Bounded task per owner",
        description="One task, one owner, one bounded scope. Not 'work on the auth refactor' — 'remove the deprecated session-token field from User.serialize and update the 4 callers.'",
        system_1_failure_counter="scope drift + ambiguity (cognitive_profile.md § Reasoning Core)",
        schema_field=None,
        doc_anchor="THE_WAY_TO_THINK.md § 1.3 Execute · Bounded tasks",
    ),

    # ── Verify stage ──
    "verify.disconfirmation_conditions": CognitiveMove(
        id="verify.disconfirmation_conditions",
        stage="verify",
        name="Disconfirmation conditions (pre-committed)",
        description="State concrete observable conditions that would invalidate the plan, COMMITTED before action. Robust falsifiability enforced at file-system level.",
        system_1_failure_counter="motivated reasoning + post-hoc rationalization (cognitive_profile.md § Decision Engine)",
        schema_field="surface.disconfirmation_conditions",
        doc_anchor="THE_WAY_TO_THINK.md § 1.4 Verify · Disconfirmation",
    ),
    "verify.facts_vs_inferences": CognitiveMove(
        id="verify.facts_vs_inferences",
        stage="verify",
        name="Distinguish proven facts from inferred conclusions",
        description="Separate what is operator-verified or test-passed from what is model-inferred. Inferences cannot promote to facts without explicit evidence (PTSP Invariant I3).",
        system_1_failure_counter="self-conditioning effect (arXiv 2509.09677) — LLM prior output silently treated as fact in later context",
        schema_field=None,  # enforced at PTSP layer, not signed-surface layer
        doc_anchor="THE_WAY_TO_THINK.md § 1.4 Verify · Facts vs Inferences",
    ),
    "verify.residual_unknowns": CognitiveMove(
        id="verify.residual_unknowns",
        stage="verify",
        name="Residual unknowns marked explicitly at handoff",
        description="At handoff time, name the unknowns that remain open. Do not let the handoff pretend the unknowns dissolved.",
        system_1_failure_counter="WYSIATI on the way out (Kahneman) — unknowns drop out of context once a decision is committed",
        schema_field="surface.unknowns",
        doc_anchor="THE_WAY_TO_THINK.md § 1.4 Verify · Residual unknowns",
    ),

    # ── Handoff stage ──
    "handoff.stop_rollback_path": CognitiveMove(
        id="handoff.stop_rollback_path",
        stage="handoff",
        name="Stop / rollback path",
        description="State concrete steps to undo the action if it proves wrong. Not 'revert if needed' — exact commands or escalation path.",
        system_1_failure_counter="planning fallacy on rollback feasibility (Kahneman)",
        schema_field="surface.decision.stop_rollback_path",
        doc_anchor="THE_WAY_TO_THINK.md § 1.5 Handoff · Rollback path",
    ),
    "handoff.persist_to_disk": CognitiveMove(
        id="handoff.persist_to_disk",
        stage="handoff",
        name="Persist reasoning to disk, not chat",
        description="The signed surface is the persistence boundary. Chat scrollback is ephemeral; the surface is the durable artifact.",
        system_1_failure_counter="reliance-on-transcript-memory (operator-noted failure mode; workflow_policy.md § Project Memory Contract)",
        schema_field=None,  # mechanical property of the signed-surface artifact
        doc_anchor="THE_WAY_TO_THINK.md § 1.5 Handoff · Persistence",
    ),
    "handoff.hash_chain": CognitiveMove(
        id="handoff.hash_chain",
        stage="handoff",
        name="Hash-chain across the session",
        description="parent_surface_hash binds each decision to its predecessor. The chain cannot be silently rewritten without breaking the hash.",
        system_1_failure_counter="post-hoc tampering / rationalization (cognitive_profile.md § Adaptation Core)",
        schema_field="surface.envelope.parent_surface_hash",
        doc_anchor="THE_WAY_TO_THINK.md § 1.5 Handoff · Hash chain",
    ),
    "handoff.operator_signature": CognitiveMove(
        id="handoff.operator_signature",
        stage="handoff",
        name="Ed25519 signature with operator key",
        description="The operator's key is the proof that the human (not the model) did the practice. The signing key is structurally out of the agent's reach.",
        system_1_failure_counter="forgery by the agent or anyone else (the MIRROR finding's deep implication: trust in self-reported AI uncertainty is structurally insufficient)",
        schema_field="surface.attestation.signature_b64_or_hex",
        doc_anchor="THE_WAY_TO_THINK.md § 1.5 Handoff · Signature",
    ),
}


# ─── Helpers ─────────────────────────────────────────────────────────────


def get_stage(stage_id: StageName) -> Stage:
    """Lookup a Stage by id. Raises KeyError if unknown."""
    return STAGES[stage_id]


def get_move(move_id: str) -> CognitiveMove:
    """Lookup a CognitiveMove by id. Raises KeyError if unknown."""
    return COGNITIVE_MOVES[move_id]


def moves_by_stage(stage_id: StageName) -> List[CognitiveMove]:
    """All cognitive moves for the named stage, in registration order."""
    return [m for m in COGNITIVE_MOVES.values() if m.stage == stage_id]


def move_for_field(schema_field: str) -> Optional[CognitiveMove]:
    """Find the cognitive move whose residue lives in the named schema field.

    Returns None if the field doesn't map to a move (e.g., metadata fields).
    """
    for move in COGNITIVE_MOVES.values():
        if move.schema_field == schema_field:
            return move
    return None


def ordered_stages() -> List[Stage]:
    """All stages in workflow order."""
    return sorted(STAGES.values(), key=lambda s: s.ordinal)


def all_move_ids() -> List[str]:
    """All cognitive-move ids in registration order."""
    return list(COGNITIVE_MOVES.keys())


# ---------------------------------------------------------------------------
# Gate labels (Event 161)
# ---------------------------------------------------------------------------

# Hook-artifact field (the flat .episteme/reasoning-surface.json shape the
# default PreToolUse gate validates) -> registry move id. The gate's block
# message names the skipped COGNITIVE MOVE, so the practice reaches the
# agent at the exact moment of failure instead of a bare schema-field name.
GATE_FIELD_TO_MOVE: Dict[str, str] = {
    "core_question": "frame.core_question",
    "unknowns": "frame.unknowns",
    "disconfirmation": "verify.disconfirmation_conditions",
}


def gate_move_label(field: str) -> Optional[str]:
    """Render the gate-facing label for a hook-artifact field:
    ``<Stage> · <Move name> — counters <short counter>``. The guard
    duplicates these strings literally (hooks-stay-self-contained
    convention); parity is CI-enforced by
    ``tests/test_practice_cognitive_moves.py``."""
    move_id = GATE_FIELD_TO_MOVE.get(field)
    if move_id is None:
        return None
    move = COGNITIVE_MOVES[move_id]
    stage = STAGES[move.stage]
    counter = move.system_1_failure_counter.split(" — ")[0].strip()
    return f"{stage.name} · {move.name} — counters {counter}"


def gate_move_labels() -> Dict[str, str]:
    """All gate labels keyed by hook-artifact field."""
    return {
        field: label
        for field in GATE_FIELD_TO_MOVE
        if (label := gate_move_label(field)) is not None
    }
