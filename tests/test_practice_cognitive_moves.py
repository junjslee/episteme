"""Tests for core/practice/cognitive_moves registry.

Verifies (a) registry is internally consistent (every move references a
known stage, every schema-field-mapped move points at a real schema
field shape), (b) helper functions work, (c) doc anchors point at
THE_WAY_TO_THINK.md sections that look right (smoke-string check).
"""
from __future__ import annotations

import pytest

from core.practice.cognitive_moves import (
    COGNITIVE_MOVES,
    STAGES,
    CognitiveMove,
    all_move_ids,
    get_move,
    get_stage,
    move_for_field,
    moves_by_stage,
    ordered_stages,
)


def test_all_stages_present():
    expected = {"frame", "decompose", "execute", "verify", "handoff"}
    assert set(STAGES.keys()) == expected


def test_ordered_stages_have_unique_ordinals():
    stages = ordered_stages()
    ordinals = [s.ordinal for s in stages]
    assert ordinals == sorted(ordinals)
    assert len(set(ordinals)) == len(ordinals)
    assert ordinals == [1, 2, 3, 4, 5]


def test_every_move_references_known_stage():
    stage_ids = set(STAGES.keys())
    for move in COGNITIVE_MOVES.values():
        assert move.stage in stage_ids, f"move {move.id} references unknown stage {move.stage}"


def test_every_move_has_doc_anchor():
    for move in COGNITIVE_MOVES.values():
        assert move.doc_anchor.startswith("THE_WAY_TO_THINK.md"), (
            f"move {move.id} doc_anchor does not start with THE_WAY_TO_THINK.md: {move.doc_anchor}"
        )


def test_every_move_has_named_system_1_counter():
    for move in COGNITIVE_MOVES.values():
        assert move.system_1_failure_counter, f"move {move.id} has empty system_1_failure_counter"
        assert len(move.system_1_failure_counter) > 20, (
            f"move {move.id} system_1_failure_counter is suspiciously short"
        )


def test_get_move_returns_correct_instance():
    move = get_move("frame.core_question")
    assert isinstance(move, CognitiveMove)
    assert move.stage == "frame"
    assert move.schema_field == "surface.core_question"


def test_get_move_raises_on_unknown():
    with pytest.raises(KeyError):
        get_move("nonexistent.move")


def test_get_stage_returns_correct_instance():
    stage = get_stage("frame")
    assert stage.id == "frame"
    assert stage.ordinal == 1
    assert stage.name == "Frame"


def test_moves_by_stage_filters_correctly():
    frame_moves = moves_by_stage("frame")
    assert len(frame_moves) > 0
    for m in frame_moves:
        assert m.stage == "frame"

    handoff_moves = moves_by_stage("handoff")
    assert len(handoff_moves) > 0
    for m in handoff_moves:
        assert m.stage == "handoff"


def test_move_for_field_resolves():
    move = move_for_field("surface.core_question")
    assert move is not None
    assert move.id == "frame.core_question"


def test_move_for_field_returns_none_for_unknown_field():
    assert move_for_field("surface.nonexistent_field") is None


def test_all_move_ids_returns_registration_order():
    ids = all_move_ids()
    assert len(ids) == len(COGNITIVE_MOVES)
    assert ids[0] == "frame.core_question"  # First registered


def test_handoff_stage_includes_signature_move():
    """Critical move — the operator's signature is the proof-of-practice."""
    handoff = moves_by_stage("handoff")
    sig_moves = [m for m in handoff if "signature" in m.id]
    assert len(sig_moves) >= 1


def test_verify_stage_includes_disconfirmation_move():
    verify = moves_by_stage("verify")
    discon_moves = [m for m in verify if "disconfirmation" in m.id]
    assert len(discon_moves) >= 1
