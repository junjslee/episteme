"""Step boundary seal protocol — enforces Invariants I1, I3, I4, I5.

Once sealed, a StepBoundary's `self_hash` is computed and the chain is
extended. Any mutation to the boundary after seal would change its
canonical form and break the next step's `parent_hash` reference — that's
the structural tamper evidence the verifier checks.

This module is intentionally side-effect-free for canonicalization and
hashing. Operator signature attachment is a separate concern handled by
`core/signing/`.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from dataclasses import replace
from typing import Optional, Sequence

from core.ptsp.canonical import jcs_canonical, sha256_hex
from core.ptsp.types import (
    Assumption,
    Fact,
    ImmutableLedgerError,
    Inference,
    StepBoundary,
    Unknown,
    _now_iso,
)


def seal_step_boundary(
    *,
    session_id: str,
    step_index: int,
    parent_boundary: Optional[StepBoundary],
    knowns: Sequence[Fact],
    inferences: Sequence[Inference],
    unknowns: Sequence[Unknown],
    assumptions: Sequence[Assumption],
    model_calls: Sequence[dict] = (),
) -> StepBoundary:
    """Construct, validate, and seal a step boundary.

    Raises ImmutableLedgerError if any of I1, I3, I4, I5 are violated.
    Returns a fully-sealed StepBoundary with `self_hash` computed.

    Operator signing happens AFTER seal via `core/signing/sign_step.py`.
    """

    # ── Invariant I1: ledger disjointness ──────────────────────────────────
    all_ids = [f.id for f in knowns]
    all_ids.extend(i.id for i in inferences)
    all_ids.extend(u.id for u in unknowns)
    all_ids.extend(a.id for a in assumptions)
    if len(set(all_ids)) != len(all_ids):
        raise ImmutableLedgerError(
            f"I1 violation: ledger_overlap_detected — duplicate id across "
            f"ledgers in session={session_id} step={step_index}"
        )

    # ── Invariant I3: Fact.depends_on resolves to another Fact ─────────────
    fact_ids = {f.id for f in knowns}
    for fact in knowns:
        for dep_id in fact.depends_on:
            if dep_id not in fact_ids:
                raise ImmutableLedgerError(
                    f"I3 violation: fact_depends_on_non_fact — "
                    f"fact {fact.id} depends on id {dep_id} which is not a "
                    f"Fact in this boundary"
                )

    # ── Invariant I4: monotonic KNOWNS containment ─────────────────────────
    # KNOWNS at step N+1 must contain everything from step N's KNOWNS that
    # was not explicitly rejected. We enforce the simpler superset rule:
    # every id present in parent's knowns AND not in any explicit-reject
    # ledger must appear in this boundary's knowns. The reject ledger is
    # not yet implemented in v1; we enforce strict superset.
    if parent_boundary is not None:
        parent_known_ids = {f.id for f in parent_boundary.knowns}
        current_known_ids = {f.id for f in knowns}
        missing = parent_known_ids - current_known_ids
        if missing:
            raise ImmutableLedgerError(
                f"I4 violation: parent_knowns_dropped — step {step_index} "
                f"knowns is missing {len(missing)} fact(s) from parent step "
                f"{parent_boundary.step_index}; first missing id={next(iter(missing))}"
            )

    # ── Invariant I5: parent hash binding ──────────────────────────────────
    parent_hash = parent_boundary.self_hash if parent_boundary is not None else None

    # Verify parent hash recomputes (defensive — catches in-memory tampering)
    if parent_boundary is not None:
        recomputed = sha256_hex(jcs_canonical(parent_boundary.to_canonical_dict()))
        if recomputed != parent_boundary.self_hash:
            raise ImmutableLedgerError(
                f"I5 violation: parent_self_hash_mismatch — parent boundary's "
                f"declared self_hash {parent_boundary.self_hash[:16]}... does "
                f"not recompute to {recomputed[:16]}..."
            )

    # Build the boundary without self_hash, canonicalize, then attach hash.
    sealed_at = _now_iso()
    provisional = StepBoundary(
        session_id=session_id,
        step_index=step_index,
        parent_hash=parent_hash,
        knowns=tuple(knowns),
        inferences=tuple(inferences),
        unknowns=tuple(unknowns),
        assumptions=tuple(assumptions),
        model_calls=tuple(model_calls),
        sealed_at=sealed_at,
        self_hash="",  # placeholder; recomputed below
        operator_signature=None,
    )
    canonical_bytes = jcs_canonical(provisional.to_canonical_dict())
    self_hash = sha256_hex(canonical_bytes)

    return replace(provisional, self_hash=self_hash)
