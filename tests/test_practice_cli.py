"""Tests for `episteme practice` CLI subcommand group."""
from __future__ import annotations

import json
import os

import pytest

from episteme.practice import run_practice_cli


@pytest.fixture(autouse=True)
def _no_rich(monkeypatch):
    """Force NO_RICH for clean test output."""
    monkeypatch.setenv("EPISTEME_NO_RICH", "1")


@pytest.fixture
def isolated_root(tmp_path, monkeypatch):
    root = tmp_path / ".episteme"
    monkeypatch.setenv("EPISTEME_ROOT", str(root))
    return root


def test_walk_runs_and_names_all_five_stages(capsys, isolated_root):
    rc = run_practice_cli(["walk"])
    assert rc == 0
    out = capsys.readouterr().out
    # All five stages must be named
    for stage in ("Frame", "Decompose", "Execute", "Verify", "Handoff"):
        assert stage in out, f"walk output missing stage: {stage}"


def test_walk_includes_foundational_models(capsys, isolated_root):
    run_practice_cli(["walk"])
    out = capsys.readouterr().out
    # Must reference at least one of the foundational mental models
    assert any(name in out for name in ("Kahneman", "Dalio", "Boyd", "Munger"))


def test_walk_cites_source_docs(capsys, isolated_root):
    run_practice_cli(["walk"])
    out = capsys.readouterr().out
    assert "cognitive_profile.md" in out
    assert "workflow_policy.md" in out
    assert "THE_WAY_TO_THINK.md" in out


def test_demo_narrated_mode_includes_cognitive_move_labels(capsys, isolated_root):
    rc = run_practice_cli(["demo", "--format", "narrated"])
    assert rc == 0
    out = capsys.readouterr().out
    # Each section names its cognitive move + counter
    assert "Core Question" in out
    assert "Unknowns" in out
    assert "Disconfirmation" in out
    assert "counter" in out.lower()


def test_demo_json_format_outputs_valid_surface_body(capsys, isolated_root):
    rc = run_practice_cli(["demo", "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    body = json.loads(out)
    # Body should have the required schema fields
    for field in ("core_question", "risk_classification", "knowns", "unknowns",
                  "assumptions", "disconfirmation_conditions", "decision", "audit"):
        assert field in body, f"demo JSON missing field: {field}"


def test_demo_json_is_signable(capsys, isolated_root, tmp_path):
    """A demo body should pass the surface builder's validation."""
    from episteme.surface._builder import validate_surface_body
    rc = run_practice_cli(["demo", "--format", "json"])
    out = capsys.readouterr().out
    body = json.loads(out)
    errors = validate_surface_body(body)
    assert errors == [], f"demo body has validation errors: {errors}"


def test_retro_empty_surface_store(capsys, isolated_root):
    """No surfaces in store — retro should still succeed with 0 examined."""
    rc = run_practice_cli(["retro"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "0" in out  # surfaces_examined: 0


def test_retro_json_format_outputs_retrospective_dict(capsys, isolated_root):
    rc = run_practice_cli(["retro", "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert "surfaces_examined" in data
    assert "observations" in data
    assert "most_frequent_gaps" in data


def test_retro_with_surfaces_reports_gaps(capsys, isolated_root, monkeypatch):
    """Author a minimal surface, then retro should report gaps."""
    from episteme.surface import run_surface_cli
    run_surface_cli([
        "author",
        "--core-question", "This is a smoke test surface with minimum content only",
        "--decision-choice", "proceed",
        "--decision-confidence", "0.8",
        "--stop-rollback-path", "git reset --hard ORIG_HEAD on this branch",
        "--reversibility", "irreversible",
        "--blast-radius", "regulated_artifact",
        "--ai-act-tier", "high",
        "--blueprint", "consequence_chain",
        "--format", "json",
    ])
    capsys.readouterr()  # discard author output
    rc = run_practice_cli(["retro", "--format", "json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["surfaces_examined"] == 1
    # Minimum surface has empty unknowns + assumptions + disconfirmation_conditions →
    # observations should be populated
    assert len(data["observations"]) > 0


def test_practice_via_top_level_cli(capsys, isolated_root):
    """`episteme practice walk` works through the top-level CLI dispatcher."""
    from episteme.cli import main
    rc = main(["practice", "walk"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Frame" in out


def test_practice_no_action_returns_error(capsys, isolated_root):
    """Missing subcommand returns parser-level error (argparse exits)."""
    with pytest.raises(SystemExit):
        run_practice_cli([])
