"""End-to-end tests for `episteme verify` CLI.

Covers the deterministic exit code contract by:
  1. signing a synthetic surface
  2. writing it to disk + corresponding pubkey
  3. running the CLI in single / batch / chain mode
  4. mutating various byte offsets and confirming the right exit code fires
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from core.ptsp.canonical import sha256_hex
from core.signing import (
    generate_keypair,
    sign_surface,
)
from episteme.verify._cli import (
    EXIT_OK,
    EXIT_SIGNATURE,
    EXIT_MALFORMED,
    EXIT_KEY_RESOLUTION,
    EXIT_CHAIN_BREAK,
    EXIT_BATCH_MIXED,
    EXIT_USAGE,
    run_verify_cli,
)


# ─── Helpers ──────────────────────────────────────────────────────────────


def _surface_body() -> dict:
    return {
        "core_question": "should I run the migration?",
        "risk_classification": {
            "reversibility": "irreversible",
            "blast_radius": "regulated_artifact",
            "ai_act_tier": "high",
            "article_79_1_triggers": [],
        },
        "knowns": [],
        "unknowns": [],
        "assumptions": [],
        "disconfirmation_conditions": [],
        "decision": {"choice": "proceed", "confidence": 0.8, "confidence_elicitation_method": "slider", "stop_rollback_path": "rollback X"},
        "audit": {"blueprint_invoked": "consequence_chain", "validation_layers_passed": ["presence"]},
    }


def _sign_to_disk(tmp_path: Path, surface_id: str = "surface-001", parent: str | None = None):
    privkey, pubkey = generate_keypair()
    signed = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id=surface_id,
        session_id="session-001",
        parent_surface_hash=parent,
    )
    fp = sha256_hex(bytes.fromhex(pubkey))
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir(exist_ok=True)
    (keys_dir / f"{fp}.pub").write_text(pubkey)
    surface_path = tmp_path / f"{surface_id}.json"
    surface_path.write_text(json.dumps(signed.to_dict(), indent=2))
    return surface_path, keys_dir, signed, privkey, pubkey


# ─── Single-file mode ─────────────────────────────────────────────────────


def test_single_surface_verify_passes(tmp_path):
    surface_path, keys_dir, _, _, _ = _sign_to_disk(tmp_path)
    rc = run_verify_cli([
        str(surface_path),
        "--keys-dir", str(keys_dir),
        "--allow-test-signatures",
        "--format", "json",
    ])
    assert rc == EXIT_OK


def test_single_surface_test_signature_rejected_without_flag(tmp_path):
    surface_path, keys_dir, _, _, _ = _sign_to_disk(tmp_path)
    rc = run_verify_cli([
        str(surface_path),
        "--keys-dir", str(keys_dir),
        "--format", "json",
    ])
    assert rc == EXIT_SIGNATURE


def test_single_surface_malformed_detected(tmp_path):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{")  # invalid JSON
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    rc = run_verify_cli([
        str(bad_path),
        "--keys-dir", str(keys_dir),
        "--allow-test-signatures",
        "--format", "json",
    ])
    assert rc == EXIT_MALFORMED


def test_single_surface_missing_key_detected(tmp_path):
    surface_path, _, _, _, _ = _sign_to_disk(tmp_path)
    empty_keys = tmp_path / "empty_keys"
    empty_keys.mkdir()
    rc = run_verify_cli([
        str(surface_path),
        "--keys-dir", str(empty_keys),
        "--allow-test-signatures",
        "--format", "json",
    ])
    assert rc == EXIT_KEY_RESOLUTION


def test_single_surface_tampered_bytes_detected(tmp_path):
    surface_path, keys_dir, _, _, _ = _sign_to_disk(tmp_path)
    # Tamper: mutate the decision field
    data = json.loads(surface_path.read_text())
    data["surface"]["decision"]["choice"] = "stop"
    surface_path.write_text(json.dumps(data, indent=2))

    rc = run_verify_cli([
        str(surface_path),
        "--keys-dir", str(keys_dir),
        "--allow-test-signatures",
        "--format", "json",
    ])
    # Tamper trips either signature_invalid (10) or self_hash_mismatch (14)
    assert rc in (10, 14)


# ─── Batch mode ───────────────────────────────────────────────────────────


def test_batch_mode_all_pass(tmp_path):
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()

    # Generate 3 surfaces, each with its own key in the same keys_dir
    for i in range(3):
        privkey, pubkey = generate_keypair()
        signed = sign_surface(
            surface=_surface_body(),
            private_key_hex=privkey,
            public_key_hex=pubkey,
            surface_id=f"surface-{i}",
            session_id="session-batch",
        )
        fp = sha256_hex(bytes.fromhex(pubkey))
        (keys_dir / f"{fp}.pub").write_text(pubkey)
        (batch_dir / f"surface-{i}.json").write_text(json.dumps(signed.to_dict()))

    rc = run_verify_cli([
        "--batch", str(batch_dir),
        "--keys-dir", str(keys_dir),
        "--allow-test-signatures",
        "--format", "json",
    ])
    assert rc == EXIT_OK


def test_batch_mode_mixed_pass_fail_returns_30(tmp_path):
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()

    # 1 valid surface
    privkey, pubkey = generate_keypair()
    signed = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="surface-good",
        session_id="session-batch",
    )
    fp = sha256_hex(bytes.fromhex(pubkey))
    (keys_dir / f"{fp}.pub").write_text(pubkey)
    (batch_dir / "surface-good.json").write_text(json.dumps(signed.to_dict()))

    # 1 invalid surface (tampered)
    privkey2, pubkey2 = generate_keypair()
    signed2 = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey2,
        public_key_hex=pubkey2,
        surface_id="surface-bad",
        session_id="session-batch",
    )
    fp2 = sha256_hex(bytes.fromhex(pubkey2))
    (keys_dir / f"{fp2}.pub").write_text(pubkey2)
    bad_dict = signed2.to_dict()
    bad_dict["surface"]["decision"]["choice"] = "stop"  # tamper
    (batch_dir / "surface-bad.json").write_text(json.dumps(bad_dict))

    rc = run_verify_cli([
        "--batch", str(batch_dir),
        "--keys-dir", str(keys_dir),
        "--allow-test-signatures",
        "--format", "json",
    ])
    assert rc == EXIT_BATCH_MIXED


# ─── Chain mode ───────────────────────────────────────────────────────────


def test_chain_mode_valid_chain_passes(tmp_path):
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    chain_dir = tmp_path / "chain"
    chain_dir.mkdir()

    privkey, pubkey = generate_keypair()
    fp = sha256_hex(bytes.fromhex(pubkey))
    (keys_dir / f"{fp}.pub").write_text(pubkey)

    signed_a = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="A",
        session_id="session-chain",
        parent_surface_hash=None,
    )
    (chain_dir / "A.json").write_text(json.dumps(signed_a.to_dict()))

    signed_b = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="B",
        session_id="session-chain",
        parent_surface_hash=signed_a.self_hash,
    )
    (chain_dir / "B.json").write_text(json.dumps(signed_b.to_dict()))

    manifest = chain_dir / "manifest.json"
    manifest.write_text(json.dumps({"surfaces": ["A.json", "B.json"]}))

    rc = run_verify_cli([
        "--chain", str(manifest),
        "--keys-dir", str(keys_dir),
        "--allow-test-signatures",
        "--format", "json",
    ])
    assert rc == EXIT_OK


def test_chain_mode_broken_chain_returns_13(tmp_path):
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    chain_dir = tmp_path / "chain"
    chain_dir.mkdir()

    privkey, pubkey = generate_keypair()
    fp = sha256_hex(bytes.fromhex(pubkey))
    (keys_dir / f"{fp}.pub").write_text(pubkey)

    signed_a = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="A",
        session_id="session-chain",
        parent_surface_hash=None,
    )
    (chain_dir / "A.json").write_text(json.dumps(signed_a.to_dict()))

    signed_b = sign_surface(
        surface=_surface_body(),
        private_key_hex=privkey,
        public_key_hex=pubkey,
        surface_id="B",
        session_id="session-chain",
        parent_surface_hash="0" * 64,  # WRONG parent — chain break
    )
    (chain_dir / "B.json").write_text(json.dumps(signed_b.to_dict()))

    manifest = chain_dir / "manifest.json"
    manifest.write_text(json.dumps({"surfaces": ["A.json", "B.json"]}))

    rc = run_verify_cli([
        "--chain", str(manifest),
        "--keys-dir", str(keys_dir),
        "--allow-test-signatures",
        "--format", "json",
    ])
    assert rc == EXIT_CHAIN_BREAK


# ─── Usage error ──────────────────────────────────────────────────────────


def test_no_mode_returns_usage_error(tmp_path):
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    rc = run_verify_cli([
        "--keys-dir", str(keys_dir),
        "--allow-test-signatures",
    ])
    assert rc == EXIT_USAGE
