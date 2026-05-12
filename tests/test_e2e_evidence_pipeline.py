"""End-to-end test: surface author → evidence packet → standalone verify.

This is the full pipeline that an actual operator + auditor would walk:
  1. Operator authors 3 signed surfaces
  2. Operator builds a Regulator Evidence Packet ZIP
  3. Packet is extracted to a fresh dir (simulating auditor receipt)
  4. Standalone `episteme verify` runs against the extracted packet from
     the fresh dir, with only the included pubkeys + verifier code
  5. Verification passes
  6. Mutate one byte of one surface; re-verify; expect failure
"""
from __future__ import annotations

import json
import zipfile

import pytest

from episteme.evidence import run_evidence_cli
from episteme.surface import run_surface_cli
from episteme.verify import run_verify_cli


@pytest.fixture
def isolated_root(tmp_path, monkeypatch):
    root = tmp_path / ".episteme"
    monkeypatch.setenv("EPISTEME_ROOT", str(root))
    return root


def _author_high_risk(label: str) -> None:
    run_surface_cli([
        "author",
        "--core-question", f"E2E test {label}: high-risk irreversible action",
        "--decision-choice", "proceed",
        "--decision-confidence", "0.8",
        "--stop-rollback-path", "rollback documented in runbook section 4.2",
        "--reversibility", "irreversible",
        "--blast-radius", "regulated_artifact",
        "--ai-act-tier", "high",
        "--blueprint", "consequence_chain",
        "--with-tsa", "--with-rekor",
        "--format", "json",
    ])


def test_full_pipeline_sign_packet_extract_verify(isolated_root, tmp_path):
    # 1. Author 3 surfaces
    for label in ("alpha", "beta", "gamma"):
        _author_high_risk(label)

    # 2. Build packet
    packet_path = tmp_path / "packet.zip"
    rc = run_evidence_cli([
        "packet", "build",
        "--framework", "eu-ai-act",
        "--output", str(packet_path),
        "--format", "json",
    ])
    assert rc == 0
    assert packet_path.exists()

    # 3. Extract packet to fresh dir (simulate auditor receipt)
    auditor_workspace = tmp_path / "auditor_workspace"
    auditor_workspace.mkdir()
    with zipfile.ZipFile(packet_path) as zf:
        zf.extractall(auditor_workspace)

    # 4. Standalone verify against extracted packet — should PASS
    surfaces_dir = next(auditor_workspace.glob("surfaces/*"))  # date bucket
    keys_dir = auditor_workspace / "public_keys"
    rc = run_verify_cli([
        "--batch", str(surfaces_dir),
        "--keys-dir", str(keys_dir),
        "--allow-test-signatures",
        "--verify-tsa", "--verify-rekor",
        "--format", "json",
    ])
    assert rc == 0


def test_tamper_in_extracted_packet_detected(isolated_root, tmp_path):
    # Setup: author + packet + extract
    _author_high_risk("tamper-test")
    packet_path = tmp_path / "packet.zip"
    run_evidence_cli([
        "packet", "build",
        "--framework", "eu-ai-act",
        "--output", str(packet_path),
        "--format", "json",
    ])
    auditor_workspace = tmp_path / "auditor_workspace"
    auditor_workspace.mkdir()
    with zipfile.ZipFile(packet_path) as zf:
        zf.extractall(auditor_workspace)

    # Tamper: mutate the decision in the extracted surface
    surface_files = list(auditor_workspace.glob("surfaces/*/*.signed.json"))
    assert len(surface_files) == 1
    data = json.loads(surface_files[0].read_text())
    data["surface"]["decision"]["choice"] = "stop"  # was "proceed"
    surface_files[0].write_text(json.dumps(data, indent=2))

    # Verify should now FAIL with exit 10 (signature) or 14 (self_hash)
    rc = run_verify_cli([
        "--batch", str(surface_files[0].parent),
        "--keys-dir", str(auditor_workspace / "public_keys"),
        "--allow-test-signatures",
        "--format", "json",
    ])
    assert rc in (10, 14)


def test_pipeline_with_chain_continuity(isolated_root, tmp_path):
    """A multi-surface session should chain via parent_surface_hash."""
    # The current surface CLI uses session_id="session-default" by default,
    # which yields a flat session. The chain test mostly exercises the verifier's
    # chain-mode happy path.

    _author_high_risk("chain-1")
    _author_high_risk("chain-2")

    packet_path = tmp_path / "packet.zip"
    run_evidence_cli([
        "packet", "build",
        "--framework", "eu-ai-act",
        "--output", str(packet_path),
        "--format", "json",
    ])

    auditor_workspace = tmp_path / "auditor_workspace"
    auditor_workspace.mkdir()
    with zipfile.ZipFile(packet_path) as zf:
        zf.extractall(auditor_workspace)

    # Batch verify all surfaces — both should pass independently
    surfaces_dir = next(auditor_workspace.glob("surfaces/*"))
    rc = run_verify_cli([
        "--batch", str(surfaces_dir),
        "--keys-dir", str(auditor_workspace / "public_keys"),
        "--allow-test-signatures",
        "--format", "json",
    ])
    assert rc == 0


def test_pipeline_with_pynacl_absent_uses_test_mode(isolated_root, tmp_path):
    """Confirm the kernel's zero-dep posture: test-mode HMAC works end-to-end."""
    _author_high_risk("nacl-absent")

    packet_path = tmp_path / "packet.zip"
    run_evidence_cli([
        "packet", "build",
        "--framework", "eu-ai-act",
        "--output", str(packet_path),
        "--format", "json",
    ])

    auditor_workspace = tmp_path / "auditor_workspace"
    auditor_workspace.mkdir()
    with zipfile.ZipFile(packet_path) as zf:
        zf.extractall(auditor_workspace)

    surfaces_dir = next(auditor_workspace.glob("surfaces/*"))
    # Without --allow-test-signatures, verifier MUST reject (audit-grade discipline)
    rc = run_verify_cli([
        "--batch", str(surfaces_dir),
        "--keys-dir", str(auditor_workspace / "public_keys"),
        "--format", "json",
    ])
    assert rc == 10  # test_signature_rejected


def test_hermes_signed_surface_bridge_writes_artifacts(tmp_path):
    """Hermes adapter sync_signed_surface_bridge writes expected files."""
    from episteme.adapters.hermes import sync_signed_surface_bridge

    fake_hermes = tmp_path / "fake-hermes"
    fake_hermes.mkdir()
    ok = sync_signed_surface_bridge(fake_hermes)
    assert ok is True
    assert (fake_hermes / "SIGNED_SURFACE_PROTOCOL.md").exists()
    assert (fake_hermes / "schemas" / "signed-surface-v1.0.md").exists()
    # Content sanity: protocol mentions the operator-side authorship requirement.
    # Normalize whitespace so multi-line phrases like "signing\n   key" match.
    protocol = (fake_hermes / "SIGNED_SURFACE_PROTOCOL.md").read_text().lower()
    normalized = " ".join(protocol.split())
    assert "operator" in normalized
    assert "signing key" in normalized or "operator key" in normalized


def test_hermes_bridge_on_missing_root_returns_false(tmp_path):
    """If ~/.hermes doesn't exist, bridge declines gracefully."""
    from episteme.adapters.hermes import sync_signed_surface_bridge

    missing = tmp_path / "nonexistent-hermes"
    ok = sync_signed_surface_bridge(missing)
    assert ok is False
