"""Surface body builder + draft-author flow.

The Reasoning Surface body schema for `signed-surface@1.0` covers:

  core_question                        str
  risk_classification.{reversibility, blast_radius, ai_act_tier, article_79_1_triggers[]}
  knowns[]                             list[{fact, source_artifact, verified_at, verification_method}]
  unknowns[]                           list[{unknown, why_not_resolvable_now, cost_of_ignorance}]
  assumptions[]                        list[{assumption, if_wrong_then, detectability}]
  disconfirmation_conditions[]         list[{observable, measurement_method, would_invalidate_plan}]
  decision.{choice, confidence, confidence_elicitation_method, stop_rollback_path}
  audit.{blueprint_invoked, validation_layers_passed[]}

This module provides:
  - validate_surface_body(body)    — strict, returns list[str] of errors
  - lazy_placeholder_scan(body)    — detect TBD/N/A/see-above/lazy strings
  - new_surface_skeleton()         — empty template for `surface author`
"""
from __future__ import annotations

import re
from typing import Any, Dict, List


REVERSIBILITY_VALUES = {"reversible", "irreversible"}
BLAST_RADIUS_VALUES = {"local", "repo", "external_service", "user_visible", "regulated_artifact"}
AI_ACT_TIER_VALUES = {"minimal", "limited", "high", "unacceptable"}
DECISION_CHOICE_VALUES = {"proceed", "stop", "audit"}
CONFIDENCE_ELICITATION_VALUES = {"slider", "written_probability_estimate"}
DETECTABILITY_VALUES = {"pre_execution", "post_execution_soft", "post_execution_irreversible"}
VERIFICATION_METHOD_VALUES = {
    "operator_cosign",
    "test_pass",
    "external_oracle",
    "operator_read",
    "original_axiom",
}
BLUEPRINT_VALUES = {
    "axiomatic_judgment",
    "fence_reconstruction",
    "consequence_chain",
    "architectural_cascade",
    "generic_fallback",
}

LAZY_PLACEHOLDER_PATTERNS = [
    re.compile(r"^\s*(tbd|n/?a|none|see above|various|tba|todo|fixme|\?+)\s*$", re.IGNORECASE),
    re.compile(r"^\s*(해당\s*없음|없음)\s*$"),
]

MIN_LENGTH_FIELDS = {
    "core_question": 20,
    "unknowns[].cost_of_ignorance": 30,
    "decision.stop_rollback_path": 10,
}


def is_lazy_placeholder(text: str) -> bool:
    if not text or not text.strip():
        return True
    for pat in LAZY_PLACEHOLDER_PATTERNS:
        if pat.match(text):
            return True
    return False


def new_surface_skeleton() -> Dict[str, Any]:
    """Empty Reasoning Surface body for `surface author` interactive flows.

    All required fields are present but empty/placeholder-typed so the
    author flow can fill them and the validator can catch missing fields
    deterministically.
    """
    return {
        "core_question": "",
        "risk_classification": {
            "reversibility": "irreversible",
            "blast_radius": "repo",
            "ai_act_tier": "limited",
            "article_79_1_triggers": [],
        },
        "knowns": [],
        "unknowns": [],
        "assumptions": [],
        "disconfirmation_conditions": [],
        "decision": {
            "choice": "proceed",
            "confidence": 0.0,
            "confidence_elicitation_method": "written_probability_estimate",
            "stop_rollback_path": "",
        },
        "audit": {
            "blueprint_invoked": "consequence_chain",
            "validation_layers_passed": [],
        },
    }


def lazy_placeholder_scan(body: Dict[str, Any]) -> List[str]:
    """Return a list of `field-path: detail` strings for lazy values found.

    Walks the body recursively; reports any string-valued leaf matching a
    lazy placeholder pattern.
    """
    findings: List[str] = []

    def _walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                _walk(item, f"{path}[{i}]")
        elif isinstance(node, str):
            if is_lazy_placeholder(node):
                findings.append(f"{path}: '{node}' is a lazy placeholder")

    _walk(body, "")
    return findings


def validate_surface_body(body: Dict[str, Any]) -> List[str]:
    """Strict structural + value validation. Returns list of error strings.

    Empty list means valid; non-empty means the caller must surface the errors
    to the operator. This is a defensive layer; the signer + verifier provide
    cryptographic correctness, while this layer provides operator-feedback on
    content quality before signing.
    """
    errors: List[str] = []

    # ── Required top-level fields ──
    required_top = (
        "core_question", "risk_classification", "knowns", "unknowns",
        "assumptions", "disconfirmation_conditions", "decision", "audit",
    )
    for f in required_top:
        if f not in body:
            errors.append(f"missing required field: {f}")

    # ── Core question minimum length ──
    cq = body.get("core_question", "")
    if not isinstance(cq, str) or len(cq.strip()) < MIN_LENGTH_FIELDS["core_question"]:
        errors.append(
            f"core_question too short (min {MIN_LENGTH_FIELDS['core_question']} chars): "
            f"got {len(cq.strip()) if isinstance(cq, str) else 'non-string'}"
        )

    # ── Risk classification ──
    rc = body.get("risk_classification", {})
    if not isinstance(rc, dict):
        errors.append("risk_classification must be an object")
    else:
        if rc.get("reversibility") not in REVERSIBILITY_VALUES:
            errors.append(f"risk_classification.reversibility must be in {REVERSIBILITY_VALUES}")
        if rc.get("blast_radius") not in BLAST_RADIUS_VALUES:
            errors.append(f"risk_classification.blast_radius must be in {BLAST_RADIUS_VALUES}")
        if rc.get("ai_act_tier") not in AI_ACT_TIER_VALUES:
            errors.append(f"risk_classification.ai_act_tier must be in {AI_ACT_TIER_VALUES}")
        if not isinstance(rc.get("article_79_1_triggers"), list):
            errors.append("risk_classification.article_79_1_triggers must be a list")

    # ── Decision ──
    d = body.get("decision", {})
    if not isinstance(d, dict):
        errors.append("decision must be an object")
    else:
        if d.get("choice") not in DECISION_CHOICE_VALUES:
            errors.append(f"decision.choice must be in {DECISION_CHOICE_VALUES}")
        confidence = d.get("confidence")
        if not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
            errors.append("decision.confidence must be a number in [0.0, 1.0]")
        if d.get("confidence_elicitation_method") not in CONFIDENCE_ELICITATION_VALUES:
            errors.append(
                f"decision.confidence_elicitation_method must be in "
                f"{CONFIDENCE_ELICITATION_VALUES}"
            )
        rp = d.get("stop_rollback_path", "")
        if not isinstance(rp, str) or len(rp.strip()) < MIN_LENGTH_FIELDS["decision.stop_rollback_path"]:
            errors.append("decision.stop_rollback_path too short or missing")

    # ── Unknowns content quality (sharpness) ──
    unknowns = body.get("unknowns", [])
    if isinstance(unknowns, list):
        for i, u in enumerate(unknowns):
            if not isinstance(u, dict):
                errors.append(f"unknowns[{i}] must be an object")
                continue
            coi = u.get("cost_of_ignorance", "")
            min_coi = MIN_LENGTH_FIELDS["unknowns[].cost_of_ignorance"]
            if not isinstance(coi, str) or len(coi.strip()) < min_coi:
                errors.append(
                    f"unknowns[{i}].cost_of_ignorance too short (min {min_coi} chars)"
                )

    # ── Assumptions detectability ──
    assumptions = body.get("assumptions", [])
    if isinstance(assumptions, list):
        for i, a in enumerate(assumptions):
            if not isinstance(a, dict):
                errors.append(f"assumptions[{i}] must be an object")
                continue
            det = a.get("detectability")
            if det not in DETECTABILITY_VALUES:
                errors.append(
                    f"assumptions[{i}].detectability must be in {DETECTABILITY_VALUES}"
                )

    # ── Knowns verification method ──
    knowns = body.get("knowns", [])
    if isinstance(knowns, list):
        for i, k in enumerate(knowns):
            if not isinstance(k, dict):
                errors.append(f"knowns[{i}] must be an object")
                continue
            vm = k.get("verification_method")
            if vm not in VERIFICATION_METHOD_VALUES:
                errors.append(
                    f"knowns[{i}].verification_method must be in {VERIFICATION_METHOD_VALUES}"
                )

    # ── Audit blueprint ──
    audit = body.get("audit", {})
    if isinstance(audit, dict):
        bp = audit.get("blueprint_invoked")
        if bp not in BLUEPRINT_VALUES:
            errors.append(f"audit.blueprint_invoked must be in {BLUEPRINT_VALUES}")

    # ── Lazy placeholder scan ──
    errors.extend(lazy_placeholder_scan(body))

    return errors
