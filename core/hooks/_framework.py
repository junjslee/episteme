"""Pillar 3 framework substrate — v1.0 RC CP7.

Two independent hash-chained streams under ``~/.episteme/framework/``:

- ``protocols.jsonl`` — Pillar 3 protocol synthesis records (Fence
  Reconstruction today; Axiomatic Judgment + Blueprint D at
  v1.0.1 / CP10).
- ``deferred_discoveries.jsonl`` — Blueprint D adjacent-gap log
  (each Blueprint D firing's ``deferred_discoveries[]`` entries
  hash-chained at PreToolUse).

The two files are separate chains because their trust radiuses are
orthogonal (CP7 plan Q1): a protocol is load-bearing cognitive
guidance; a deferred-discovery is an architectural-debt entry. A
chain break in one must not halt reads from the other.

## Retroactive CP5 upgrade

CP5 wrote ``protocols.jsonl`` records with
``format_version: "cp5-pre-chain"`` + null ``prev_hash`` /
``entry_hash``. CP7's ``upgrade_cp5_prechain`` walks the file
deterministically:

1. Pre-upgrade audit — every record must carry
   ``format_version: "cp5-pre-chain"`` + null chain fields. Any
   deviation aborts with ``UpgradeError`` naming the offending line
   (no partial upgrade).
2. Walk in file order, computing hashes against the preserved
   original timestamps (``written_at`` → envelope ``ts``).
3. Wrap each CP5 record as a ``payload`` inside the CP7 envelope.
   The CP5 fields stay verbatim except for the three chain-layer
   fields (``format_version`` / ``prev_hash`` / ``entry_hash``)
   which move to the envelope.
4. Backup the original to ``protocols.jsonl.upgrade-<ts>.bak``.
5. Atomic rename of the new file into place.
6. Idempotent — second call on an already-upgraded file returns
   ``UpgradeResult(status="already_upgraded", ...)`` with no I/O.

The upgrade is the deterministic-walker test: if it can't reconstruct
byte-identical hashes on re-run, the walker has a bug.

## Format version at envelope level

Post-CP7 writes go through ``_chain.append`` directly, so the
envelope's ``schema_version`` is the source of truth.
``format_version`` in the payload is CP5-legacy metadata; new
records don't carry it.

Spec: ``docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md`` § Pillar 3 ·
Framework Synthesis & Active Guidance.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _chain import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    GENESIS_PREV_HASH,
    ChainError,
    ChainVerdict,
    append as _chain_append,
    atomic_replace_file as _atomic_replace,
    compute_entry_hash,
    iter_records as _chain_iter,
    verify_chain as _chain_verify,
)


PROTOCOL_TYPE = "protocol"
DEFERRED_DISCOVERY_TYPE = "deferred_discovery"
CP5_FORMAT_VERSION = "cp5-pre-chain"
UPGRADED_FORMAT_MARKER = "cp7-chained-v1"


class UpgradeError(ChainError):
    """Raised on unrecoverable retroactive-upgrade condition —
    mixed pre-chain/chained, missing required fields, or I/O
    failure mid-upgrade. Caller must not re-try automatically;
    the operator resolves manually via ``episteme chain upgrade``."""


@dataclass(frozen=True)
class UpgradeResult:
    status: Literal["upgraded", "already_upgraded", "empty", "missing"]
    entries_processed: int
    backup_path: Path | None
    message: str


def _episteme_home() -> Path:
    return Path(os.environ.get("EPISTEME_HOME") or (Path.home() / ".episteme"))


def _protocols_path() -> Path:
    return _episteme_home() / "framework" / "protocols.jsonl"


def _deferred_discoveries_path() -> Path:
    return _episteme_home() / "framework" / "deferred_discoveries.jsonl"


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def write_protocol(payload: dict, *, path: Path | None = None) -> dict:
    """Append a protocol record. ``payload`` gets a ``type: "protocol"``
    discriminator if missing; passes straight through to
    ``_chain.append``. Returns the full envelope."""
    target = path if path is not None else _protocols_path()
    if "type" not in payload:
        payload = {**payload, "type": PROTOCOL_TYPE}
    elif payload["type"] != PROTOCOL_TYPE:
        raise ChainError(
            f"write_protocol: payload.type must be {PROTOCOL_TYPE!r} "
            f"(got {payload['type']!r})"
        )
    return _chain_append(target, payload)


DEFAULT_DEDUP_TAIL_N = 200
DEFAULT_DEDUP_DESC_PREFIX = 120


def _dedup_key(payload: dict, desc_prefix: int) -> tuple[str, str]:
    return (
        str(payload.get("flaw_classification", "")),
        str(payload.get("description") or "")[:desc_prefix],
    )


def _tail_deferred_records(target: Path, n: int) -> list[dict]:
    """Read the last N envelopes from `target` via chain iteration.

    Chain verification is skipped for this tail-scan — the dedup check
    is advisory pre-write logic, not a chain-integrity gate. A chain
    break would surface separately via `verify_chains()`. Skipping
    verify keeps dedup O(n) reads without amplifying on corrupted files.
    """
    if not target.is_file() or n <= 0:
        return []
    envelopes: list[dict] = []
    for rec in _chain_iter(target, verify=False):
        envelopes.append(rec)
    return envelopes[-n:] if len(envelopes) > n else envelopes


def write_deferred_discovery(
    payload: dict,
    *,
    path: Path | None = None,
    dedup: bool = True,
    dedup_tail_n: int = DEFAULT_DEDUP_TAIL_N,
    dedup_desc_prefix: int = DEFAULT_DEDUP_DESC_PREFIX,
) -> dict:
    """Append a deferred_discovery record. Type-tagged like
    ``write_protocol``; independent chain stream.

    Event 49 · CP-DEDUP-01 — when ``dedup=True`` (default), a pre-write
    tail-scan of the last ``dedup_tail_n`` entries checks whether an
    entry with the same ``(flaw_classification, description[:dedup_desc_prefix])``
    key exists. On match: no new record is written; the function
    returns ``{"suppressed_duplicate": True, "matched_entry_hash": <hash>}``
    instead of a new envelope. Tolerate callers that discard the return
    (the _blueprint_d.py caller does); callers that inspect the envelope
    should check for the ``suppressed_duplicate`` key.

    Rationale: framework writer historically logged identical findings
    on every cascade:architectural firing, producing a 32× duplication
    ratio across 1,294 records. Pre-write dedup stops growth without
    retroactively modifying existing chain (that stays untouched).
    """
    target = path if path is not None else _deferred_discoveries_path()
    if "type" not in payload:
        payload = {**payload, "type": DEFERRED_DISCOVERY_TYPE}
    elif payload["type"] != DEFERRED_DISCOVERY_TYPE:
        raise ChainError(
            f"write_deferred_discovery: payload.type must be "
            f"{DEFERRED_DISCOVERY_TYPE!r} (got {payload['type']!r})"
        )
    if dedup:
        incoming_key = _dedup_key(payload, dedup_desc_prefix)
        try:
            recent = _tail_deferred_records(target, dedup_tail_n)
        except (OSError, ChainError):
            recent = []
        for existing in recent:
            existing_payload = (
                existing.get("payload") if isinstance(existing, dict) else None
            )
            if not isinstance(existing_payload, dict):
                continue
            if existing_payload.get("type") != DEFERRED_DISCOVERY_TYPE:
                continue
            if _dedup_key(existing_payload, dedup_desc_prefix) == incoming_key:
                return {
                    "suppressed_duplicate": True,
                    "matched_entry_hash": existing.get("entry_hash"),
                    "matched_ts": existing.get("ts"),
                    "reason": "cp-dedup-01 suppression",
                }
    return _chain_append(target, payload)


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def list_protocols(
    *,
    project_name: str | None = None,
    blueprint: str | None = None,
    path: Path | None = None,
) -> list[dict]:
    """Chain-verified read. Stops at first break. Filters on
    ``context_signature.project_name`` and ``blueprint`` when
    provided. Returns a list of envelopes — caller accesses
    business fields via ``rec["payload"]``."""
    target = path if path is not None else _protocols_path()
    out: list[dict] = []
    for rec in _chain_iter(target, verify=True):
        payload = rec.get("payload") if isinstance(rec, dict) else None
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != PROTOCOL_TYPE:
            continue
        if blueprint is not None and payload.get("blueprint") != blueprint:
            continue
        if project_name is not None:
            sig = payload.get("context_signature")
            if isinstance(sig, dict):
                if sig.get("project_name") != project_name:
                    continue
            else:
                # CP5 legacy string signature — skip project filter
                # (can't inspect fields). Caller that wants strict
                # project match should pass a post-CP7 signature.
                continue
        out.append(rec)
    return out


def list_deferred_discoveries(
    *,
    status: str | None = None,
    flaw_classification: str | None = None,
    path: Path | None = None,
) -> list[dict]:
    target = path if path is not None else _deferred_discoveries_path()
    out: list[dict] = []
    for rec in _chain_iter(target, verify=True):
        payload = rec.get("payload") if isinstance(rec, dict) else None
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != DEFERRED_DISCOVERY_TYPE:
            continue
        if status is not None and payload.get("status") != status:
            continue
        if (
            flaw_classification is not None
            and payload.get("flaw_classification") != flaw_classification
        ):
            continue
        out.append(rec)
    return out


# ---------------------------------------------------------------------------
# Chain verification
# ---------------------------------------------------------------------------


def verify_chains(
    *,
    protocols_path: Path | None = None,
    deferred_discoveries_path: Path | None = None,
) -> dict[str, ChainVerdict]:
    """Per-stream chain verification. Returns a dict keyed by stream
    name. Phase 12 reads this at SessionStart."""
    return {
        "protocols": _chain_verify(
            protocols_path if protocols_path is not None else _protocols_path()
        ),
        "deferred_discoveries": _chain_verify(
            deferred_discoveries_path
            if deferred_discoveries_path is not None
            else _deferred_discoveries_path()
        ),
    }


# ---------------------------------------------------------------------------
# Retroactive CP5 upgrade
# ---------------------------------------------------------------------------


def _cp5_payload_from_legacy(legacy: dict) -> dict:
    """Strip the CP5 chain-layer fields (``format_version``,
    ``prev_hash``, ``entry_hash``) from a legacy record and tag it
    with ``type: "protocol"``. Everything else is preserved verbatim.

    The original CP5 record is the payload; the envelope wraps it.
    This preserves ALL business fields (correlation_id,
    synthesized_protocol, context_signature, ...) byte-identically.
    """
    strip_keys = {"format_version", "prev_hash", "entry_hash"}
    payload = {k: v for k, v in legacy.items() if k not in strip_keys}
    payload.setdefault("type", PROTOCOL_TYPE)
    payload.setdefault("legacy_format", CP5_FORMAT_VERSION)
    return payload


def _looks_already_upgraded(first_record: dict) -> bool:
    """A CP7-envelope record has ``schema_version``, ``ts``,
    ``prev_hash``, ``payload``, ``entry_hash`` keys. A CP5 record
    has ``format_version``, ``written_at``, ``prev_hash: null``."""
    return (
        "schema_version" in first_record
        and "payload" in first_record
        and isinstance(first_record.get("entry_hash"), str)
        and first_record["entry_hash"].startswith("sha256:")
    )


def _looks_cp5_prechain(record: dict) -> bool:
    return (
        record.get("format_version") == CP5_FORMAT_VERSION
        and record.get("prev_hash") is None
        and record.get("entry_hash") is None
    )


def upgrade_cp5_prechain(
    *, path: Path | None = None
) -> UpgradeResult:
    """Retroactively chain CP5's ``cp5-pre-chain`` records in place.

    Returns an ``UpgradeResult``. Idempotent — safe to call
    repeatedly. Raises ``UpgradeError`` on mixed pre-chain/chained
    files (the walker can't confidently reconstruct a partial
    upgrade).
    """
    target = path if path is not None else _protocols_path()

    if not target.is_file():
        return UpgradeResult(
            status="missing",
            entries_processed=0,
            backup_path=None,
            message=f"{target} does not exist — nothing to upgrade",
        )

    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        raise UpgradeError(f"upgrade_cp5_prechain read: {exc}") from exc

    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return UpgradeResult(
            status="empty",
            entries_processed=0,
            backup_path=None,
            message=f"{target} is empty — nothing to upgrade",
        )

    parsed: list[dict] = []
    for idx, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise UpgradeError(
                f"{target}:line {idx + 1}: not valid JSON ({exc})"
            ) from exc
        if not isinstance(rec, dict):
            raise UpgradeError(
                f"{target}:line {idx + 1}: not a JSON object"
            )
        parsed.append(rec)

    # Idempotent fast path — already upgraded?
    if all(_looks_already_upgraded(r) for r in parsed):
        verdict = _chain_verify(target)
        if verdict.intact:
            return UpgradeResult(
                status="already_upgraded",
                entries_processed=len(parsed),
                backup_path=None,
                message=(
                    f"{target}: {len(parsed)} records already in "
                    f"cp7-chained-v1 envelope; chain intact"
                ),
            )
        raise UpgradeError(
            f"{target}: appears upgraded but chain verification failed "
            f"({verdict.reason}). Operator must resolve manually."
        )

    # Mixed state — partial upgrade detected.
    if any(_looks_already_upgraded(r) for r in parsed) and any(
        _looks_cp5_prechain(r) for r in parsed
    ):
        raise UpgradeError(
            f"{target}: file contains both cp5-pre-chain AND cp7-chained-v1 "
            f"records. Partial upgrade detected; operator must resolve "
            f"manually (archive then re-play from backup)."
        )

    # Every record must look cp5-pre-chain at this point.
    for idx, rec in enumerate(parsed):
        if not _looks_cp5_prechain(rec):
            raise UpgradeError(
                f"{target}:line {idx + 1}: expected cp5-pre-chain shape "
                f"(format_version={CP5_FORMAT_VERSION!r}, null chain fields); "
                f"got format_version={rec.get('format_version')!r}"
            )
        if not isinstance(rec.get("written_at"), str):
            raise UpgradeError(
                f"{target}:line {idx + 1}: missing required "
                f"`written_at` string field"
            )

    # Backup the original file.
    backup_ts = lines[-1] if False else ""  # placeholder; real ts below
    from datetime import datetime, timezone

    backup_ts = (
        datetime.now(timezone.utc).isoformat().replace(":", "").replace(".", "-")
    )
    backup = target.with_suffix(f".upgrade-{backup_ts}.bak")
    try:
        backup.write_bytes(target.read_bytes())
    except OSError as exc:
        raise UpgradeError(f"upgrade_cp5_prechain backup: {exc}") from exc

    # Walk + rechain. Write to a new file then atomic-replace.
    new_lines: list[str] = []
    expected_prev = GENESIS_PREV_HASH
    for rec in parsed:
        payload = _cp5_payload_from_legacy(rec)
        ts = str(rec["written_at"])
        entry_hash = compute_entry_hash(expected_prev, ts, payload)
        envelope = {
            "schema_version": UPGRADED_FORMAT_MARKER,
            "ts": ts,
            "prev_hash": expected_prev,
            "payload": payload,
            "entry_hash": entry_hash,
        }
        new_lines.append(json.dumps(envelope, ensure_ascii=False))
        expected_prev = entry_hash

    new_contents = ("\n".join(new_lines) + "\n").encode("utf-8")
    try:
        _atomic_replace(target, new_contents)
    except OSError as exc:
        raise UpgradeError(f"upgrade_cp5_prechain atomic replace: {exc}") from exc

    # Post-upgrade verify — the walker's output must re-verify.
    post_verdict = _chain_verify(target)
    if not post_verdict.intact:
        raise UpgradeError(
            f"{target}: upgrade wrote file but post-verify failed "
            f"({post_verdict.reason}). Backup preserved at {backup}."
        )

    return UpgradeResult(
        status="upgraded",
        entries_processed=len(parsed),
        backup_path=backup,
        message=(
            f"{target}: upgraded {len(parsed)} records from "
            f"cp5-pre-chain to cp7-chained-v1; chain intact. "
            f"Backup: {backup}"
        ),
    )
