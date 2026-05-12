"""Tests for `episteme evidence ...` CLI subcommands.

Exercises the viewer (posture / register / show / alerts) + packet builder
end-to-end against a fixture of N signed surfaces.
"""
from __future__ import annotations

import json
import os
import zipfile

import pytest

from episteme.evidence import run_evidence_cli
from episteme.surface import run_surface_cli


@pytest.fixture
def isolated_root(tmp_path, monkeypatch):
    root = tmp_path / ".episteme"
    monkeypatch.setenv("EPISTEME_ROOT", str(root))
    return root


def _seed_surfaces(n_high: int = 2, n_low: int = 1) -> None:
    """Author n_high high-tier surfaces and n_low low-tier surfaces."""
    for i in range(n_high):
        run_surface_cli([
            "author",
            "--core-question", f"High-tier decision number {i} on prod system",
            "--decision-choice", "proceed",
            "--decision-confidence", "0.85",
            "--stop-rollback-path", "psql pg_cancel_backend on migration",
            "--reversibility", "irreversible",
            "--blast-radius", "regulated_artifact",
            "--ai-act-tier", "high",
            "--blueprint", "consequence_chain",
            "--with-tsa", "--with-rekor",
            "--format", "json",
        ])
    for i in range(n_low):
        run_surface_cli([
            "author",
            "--core-question", f"Low-tier decision number {i} on local files",
            "--decision-choice", "stop",
            "--decision-confidence", "0.5",
            "--stop-rollback-path", "git checkout to revert local files",
            "--reversibility", "reversible",
            "--blast-radius", "local",
            "--ai-act-tier", "minimal",
            "--blueprint", "axiomatic_judgment",
            "--format", "json",
        ])


def test_posture_panel(isolated_root, capsys):
    _seed_surfaces(n_high=2, n_low=1)
    capsys.readouterr()  # discard seed output
    rc = run_evidence_cli(["posture", "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total_decisions"] == 3
    assert data["high_risk_decisions"] == 2
    assert data["signed_pct"] == 100.0
    assert data["test_signature_count"] == 3  # HMAC fallback (no PyNaCl)
    assert data["chain_breaks"] == 0


def test_register_filters_by_tier(isolated_root, capsys):
    _seed_surfaces(n_high=2, n_low=1)
    capsys.readouterr()
    rc = run_evidence_cli(["register", "--tier", "high", "--format", "json"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 2
    for r in rows:
        assert r["ai_act_tier"] == "high"


def test_register_filters_by_choice(isolated_root, capsys):
    _seed_surfaces(n_high=2, n_low=1)
    capsys.readouterr()
    rc = run_evidence_cli(["register", "--choice", "stop", "--format", "json"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["decision_choice"] == "stop"


def test_show_specific_surface(isolated_root, capsys):
    _seed_surfaces(n_high=1, n_low=0)
    capsys.readouterr()
    # First, list to get an id
    run_evidence_cli(["register", "--format", "json"])
    rows = json.loads(capsys.readouterr().out)
    sid = rows[0]["surface_id"]
    rc = run_evidence_cli(["show", sid, "--format", "json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["surface_id"] == sid
    assert "raw" in data  # show includes raw signed-surface


def test_alerts_flag_test_signatures(isolated_root, capsys):
    _seed_surfaces(n_high=1, n_low=0)
    capsys.readouterr()
    rc = run_evidence_cli(["alerts", "--format", "json"])
    assert rc == 0
    alerts = json.loads(capsys.readouterr().out)
    codes = {a["code"] for a in alerts}
    assert "test_mode_signatures_present" in codes


def test_packet_build_eu_ai_act(isolated_root, tmp_path, capsys):
    _seed_surfaces(n_high=2, n_low=1)
    capsys.readouterr()
    out_path = tmp_path / "packet.zip"
    rc = run_evidence_cli([
        "packet", "build",
        "--framework", "eu-ai-act",
        "--output", str(out_path),
        "--format", "json",
    ])
    assert rc == 0
    assert out_path.exists()
    # Verify packet shape
    with zipfile.ZipFile(out_path) as zf:
        names = zf.namelist()
        assert "MANIFEST.json" in names
        assert "MANIFEST.json.sig" in names
        assert "README.md" in names
        assert any(n.startswith("surfaces/") for n in names)
        assert any(n.startswith("chains/") for n in names)
        assert any(n.startswith("public_keys/") for n in names)


def test_packet_build_refuses_empty(isolated_root, tmp_path):
    # No surfaces authored
    out_path = tmp_path / "empty.zip"
    rc = run_evidence_cli([
        "packet", "build",
        "--framework", "eu-ai-act",
        "--output", str(out_path),
        "--since", "1970-01-01",
        "--until", "1970-01-02",
        "--format", "json",
    ])
    assert rc == 4  # EXIT_NOT_FOUND — refuses empty packet
    assert not out_path.exists()
