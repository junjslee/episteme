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
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _chain import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    GENESIS_PREV_HASH,
    ChainError,
    ChainVerdict,
    _locked as _chain_locked,
    append as _chain_append,
    atomic_replace_file as _atomic_replace,
    compute_entry_hash,
    iter_records as _chain_iter,
    rewrite_lock as _rewrite_lock,
    verify_chain as _chain_verify,
)


PROTOCOL_TYPE = "protocol"
DEFERRED_DISCOVERY_TYPE = "deferred_discovery"
# Resolution layer (2026-07-03). The ledger accumulated 233 permanently
# 'pending' entries because no resolution mechanism was ever built —
# the only defined open status was `pending` and nothing could
# transition it (recon). Resolution is APPEND-ONLY: a verdict record
# references a discovery's entry_hash; the discovery itself is never
# mutated (mutating a hash-chained record would break the chain, and
# the pending->verdict pair IS the audit trail). Readers derive
# openness: open = status in OPEN_STATUSES AND no verdict references
# the entry_hash.
#
# Four first-class verdicts, each closing an entry identically (openness
# keys on has-any-verdict, not on which verdict):
#   - resolved  : the finding was addressed; the rationale names what was
#                 done (commit/test).
#   - noise     : NOT a real finding — false positive or non-issue; the
#                 rationale names why the pattern cannot occur.
#   - duplicate : a real finding already covered by another entry; the
#                 rationale points at the covering entry.
#   - accepted  : a REAL finding the operator/agent consciously decides
#                 NOT to act on, closed with the COST OF IGNORANCE named
#                 (Event 152). Distinct from `noise` — the finding is
#                 genuine; the ledger records a deliberate wontfix rather
#                 than falsifying it into noise. Required because the
#                 anti-treadmill rule (workflow_policy.md) makes
#                 "accept-and-close with the cost of ignorance named" a
#                 first-class disposition; without it, real-but-wontfix
#                 findings either rot the open-count signal forever or get
#                 mislabeled `noise`, corrupting the record.
DISCOVERY_VERDICT_TYPE = "deferred_discovery_verdict"
RESOLUTION_VERDICTS = frozenset({"resolved", "noise", "duplicate", "accepted"})
_VERDICT_RATIONALE_FLOOR = 15  # same lazy-value bar as surface fields
_REF_PREFIX_FLOOR = 8

# Terminal, machine-written aging-out of an OPEN discovery by the
# at-cap relief valve (Event 158 — sibling of Event 157's
# ``spot_check_expiry``). Deliberately NOT a RESOLUTION_VERDICTS value:
# that enum records operator judgment; an expiry records the absence of
# it, honestly. An expiry closes the entry (open_deferred_discoveries
# treats its ref like a verdict ref) and is not re-openable.
DISCOVERY_EXPIRY_TYPE = "deferred_discovery_expiry"

# Open-set backpressure (Event 158, M1 follow-through). Blueprint D
# auto-enqueues discoveries on the live write path; the only drain is
# the operator verdict CLI. Without a bound the open set grows without
# limit (178 open at audit time; 1,208 records historically). The cap
# mirrors the spot-check queue's DEFAULT_PENDING_CAP — one mental
# model for operator review load — with its own env knob. At cap,
# open entries older than the age floor expire as chained records so
# writes resume; the floor is 30 days (vs the spot-check queue's 7)
# because architectural-debt entries deserve a longer review window
# than op samples. Budgets are code — changing either constant IS the
# decision.
DEFAULT_DEFERRED_OPEN_CAP = 100
DEFERRED_EXPIRY_AGE_SECONDS = 30 * 24 * 60 * 60
_DEFERRED_SKIP_COUNTER_FILENAME = "deferred_skipped.json"
CP5_FORMAT_VERSION = "cp5-pre-chain"
UPGRADED_FORMAT_MARKER = "cp7-chained-v1"

# CP-DEDUP-01 compaction — which deferred_discovery statuses are
# eligible to be collapsed by the one-time compaction. Only `pending`
# entries are de-duplicated: a resolved/superseded/closed record is
# part of the audit trail (it records that a finding was addressed) and
# is preserved verbatim regardless of duplication. A deferred_discovery
# with no `status` field is treated as open (the historical
# Blueprint-D writer emitted no status, so the bloat is all `pending`).
OPEN_STATUSES = frozenset({"pending"})


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


@dataclass(frozen=True)
class CompactResult:
    """Output of ``compact_deferred_discoveries``.

    - ``status`` — ``compacted`` (open duplicates removed + chain
      rebuilt), ``noop`` (no open duplicates found; file untouched),
      ``empty`` (file present but blank), ``missing`` (no file).
    - ``total_before`` / ``total_after`` — record counts before/after.
    - ``removed`` — ``total_before - total_after``.
    - ``backup_path`` — set only when ``status == "compacted"`` (the
      ``noop`` path never writes a backup).
    - ``head_hash`` — chain head after compaction (None on empty /
      missing).
    """

    status: Literal["compacted", "noop", "empty", "missing"]
    total_before: int
    total_after: int
    removed: int
    backup_path: Path | None
    head_hash: str | None
    message: str


def _episteme_home() -> Path:
    return Path(os.environ.get("EPISTEME_HOME") or (Path.home() / ".episteme"))


def _protocols_path() -> Path:
    return _episteme_home() / "framework" / "protocols.jsonl"


def _deferred_discoveries_path() -> Path:
    return _episteme_home() / "framework" / "deferred_discoveries.jsonl"


def _deferred_skip_counter_path() -> Path:
    return _episteme_home() / "state" / _DEFERRED_SKIP_COUNTER_FILENAME


# ---------------------------------------------------------------------------
# Open-set backpressure (Event 158 — mirrors _spot_check's Event 148/157
# machinery; small helpers duplicated per the hooks-stay-self-contained
# convention)
# ---------------------------------------------------------------------------


def _resolve_deferred_open_cap(explicit: int | None = None) -> int:
    """Resolve the open-set cap. Precedence: explicit arg (test seam) >
    ``EPISTEME_DEFERRED_OPEN_CAP`` env var > ``DEFAULT_DEFERRED_OPEN_CAP``.
    Non-parseable / NON-POSITIVE values fall back to the default — a
    bad knob must never break the write path, and unlike the spot-check
    sampler (where cap=0 merely quiets sampling) a zero cap here would
    silently drop architectural-debt records with the banner notice
    suppressed (Event 158 review finding). Never raises."""
    if explicit is not None:
        try:
            val = int(explicit)
        except (TypeError, ValueError):
            return DEFAULT_DEFERRED_OPEN_CAP
        return val if val > 0 else DEFAULT_DEFERRED_OPEN_CAP
    raw = os.environ.get("EPISTEME_DEFERRED_OPEN_CAP", "").strip()
    if raw:
        try:
            val = int(raw)
            if val > 0:
                return val
        except ValueError:
            pass
    return DEFAULT_DEFERRED_OPEN_CAP


def read_deferred_skip_counter(path: Path | None = None) -> dict:
    """Read the backpressure skip sidecar — ``{"skipped_count": 0}``
    when absent or unreadable. Never raises."""
    target = path if path is not None else _deferred_skip_counter_path()
    try:
        if target.is_file():
            data = json.loads(target.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(
                data.get("skipped_count"), int
            ):
                return data
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    return {"skipped_count": 0}


def _write_deferred_skip_counter(payload: dict, target: Path) -> bool:
    """Atomic temp+rename sidecar write. Returns False when degraded —
    callers must not block the write path on it."""
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(
            prefix=target.name + ".tmp-", dir=str(target.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, target)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return False
    except OSError:
        return False
    return True


def _bump_deferred_skip_counter(
    reason: str, now: datetime, *, path: Path | None = None
) -> int | None:
    target = path if path is not None else _deferred_skip_counter_path()
    current = read_deferred_skip_counter(target).get("skipped_count", 0)
    if not isinstance(current, int) or current < 0:
        current = 0
    payload = {
        "skipped_count": current + 1,
        "last_skipped_at": now.isoformat(),
        "last_reason": reason,
    }
    if not _write_deferred_skip_counter(payload, target):
        return None
    return current + 1


def _reset_deferred_skip_counter(
    now: datetime, *, path: Path | None = None
) -> None:
    """Zero the counter — an operator verdict is drain activity and
    starts a new 'since last drain' window. Best-effort: never raises."""
    target = path if path is not None else _deferred_skip_counter_path()
    _write_deferred_skip_counter(
        {"skipped_count": 0, "last_reset_at": now.isoformat()}, target
    )


def _parse_iso_ts(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _expire_stale_open(
    target: Path,
    now_dt: datetime,
    *,
    age_seconds: int = DEFERRED_EXPIRY_AGE_SECONDS,
) -> int:
    """At-cap relief valve (Event 158): append a terminal
    ``deferred_discovery_expiry`` record for every OPEN discovery older
    than the age floor. Age comes from payload ``logged_at``, falling
    back to the envelope's append ``ts`` (machine-written, always
    present); an entry with neither parseable is expiry-eligible — an
    unstampable entry must not jam a cap slot forever (Event 157
    immortal-entry lesson, baked in from the start here). Drains ALL
    stale entries in one pass — the cohort is bounded by the cap and a
    full drain lets the SessionStart banner clear honestly. Returns the
    count expired; errors propagate to the caller's guard."""
    cutoff = now_dt - timedelta(seconds=age_seconds)
    expired = 0
    for env in open_deferred_discoveries(path=target):
        payload = env.get("payload") if isinstance(env, dict) else None
        payload = payload if isinstance(payload, dict) else {}
        stamp = _parse_iso_ts(str(payload.get("logged_at") or ""))
        if stamp is None:
            stamp = _parse_iso_ts(str(env.get("ts") or ""))
        if stamp is not None and stamp > cutoff:
            continue
        _chain_append(target, {
            "type": DISCOVERY_EXPIRY_TYPE,
            "ref": str(env.get("entry_hash") or ""),
            "expired_at": now_dt.isoformat(),
            "logged_at": payload.get("logged_at"),
            "reason": "cap_relief",
        })
        expired += 1
    return expired


def _deferred_cap_admit(
    target: Path, cap_value: int, now_dt: datetime
) -> bool:
    """Cap consult for the discovery write path. At cap, run the relief
    valve then recount; True when there is room. A count error fails
    toward admit — backpressure must never break Blueprint D's
    bookkeeping (its writer already degrades gracefully)."""
    try:
        open_n = len(open_deferred_discoveries(path=target))
    except Exception:
        return True
    if open_n < cap_value:
        return True
    try:
        if _expire_stale_open(target, now_dt):
            open_n = len(open_deferred_discoveries(path=target))
    except Exception:
        pass
    return open_n < cap_value


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def _canonical_context_signature(sig: dict) -> str:
    """Canonical JSON serialization of a context_signature dict for
    equality comparison. Sort-keys + minimal separators ensures
    byte-identical output for semantically equal signatures regardless
    of insertion order."""
    return json.dumps(sig, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _find_predecessor(target: Path, context_signature: dict) -> str | None:
    """Return the entry_hash of the LATEST protocol whose
    context_signature matches the given one, or None.

    Used by ``write_protocol`` to auto-set the ``supersedes`` field on
    a new protocol whose context_signature matches an existing one.
    Match semantics: canonical-JSON equality of the full
    context_signature dict.

    Walks the chain in file order; latest match wins (last-write-wins
    is the natural semantic for supersede chains).
    """
    if not target.is_file():
        return None
    target_canonical = _canonical_context_signature(context_signature)
    last_match: str | None = None
    for rec in _chain_iter(target, verify=True):
        if not isinstance(rec, dict):
            continue
        payload = rec.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != PROTOCOL_TYPE:
            continue
        sig = payload.get("context_signature")
        if not isinstance(sig, dict):
            continue
        if _canonical_context_signature(sig) == target_canonical:
            entry_hash = rec.get("entry_hash")
            if isinstance(entry_hash, str):
                last_match = entry_hash
    return last_match


def _superseded_hashes(target: Path) -> set[str]:
    """Return the set of entry_hashes that have been superseded — i.e.,
    hashes that appear as some later protocol's ``supersedes`` field
    value.

    Used by ``list_protocols`` (default) to filter out superseded
    entries from active-guidance queries. The kernel's anti-Doxa
    discipline at the protocol-routing layer: only the LATEST entry
    in a supersede chain is active.
    """
    if not target.is_file():
        return set()
    superseded: set[str] = set()
    for rec in _chain_iter(target, verify=True):
        if not isinstance(rec, dict):
            continue
        payload = rec.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != PROTOCOL_TYPE:
            continue
        sup = payload.get("supersedes")
        if isinstance(sup, str) and sup.startswith("sha256:"):
            superseded.add(sup)
    return superseded


def walk_supersede_chains(
    *,
    project_name: str | None = None,
    path: Path | None = None,
) -> list[list[dict]]:
    """Group protocols by canonical context_signature and return chains
    (lists of envelopes) where len(chain) > 1 — i.e., genuine supersede
    chains where multiple protocols share the same context_signature.

    Chains are returned in file order; within each chain, envelopes
    are also in file order (oldest-first → latest).

    Used by ``episteme history protocol`` CLI sub-action to show the
    operator which context_signatures have evolved over time.
    """
    target = path if path is not None else _protocols_path()
    if not target.is_file():
        return []
    grouped: dict[str, list[dict]] = {}
    for rec in _chain_iter(target, verify=True):
        if not isinstance(rec, dict):
            continue
        payload = rec.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != PROTOCOL_TYPE:
            continue
        sig = payload.get("context_signature")
        if not isinstance(sig, dict):
            continue
        if project_name is not None and sig.get("project_name") != project_name:
            continue
        key = _canonical_context_signature(sig)
        grouped.setdefault(key, []).append(rec)
    return [chain for chain in grouped.values() if len(chain) > 1]


def write_protocol(payload: dict, *, path: Path | None = None) -> dict:
    """Append a protocol record. ``payload`` gets a ``type: "protocol"``
    discriminator if missing.

    Event 84 / CP-TEMPORAL-INTEGRITY-EXPANSION-01 Item 4 — supersede
    detection. If the payload doesn't carry an explicit ``supersedes``
    field AND a prior protocol with matching ``context_signature``
    exists, the new protocol's ``supersedes`` field is set to the
    latest-matching predecessor's entry_hash. This makes
    supersede-with-history automatic on emit (operator + synthesis
    logic don't need to manually compute predecessor hashes).

    Backward compatible: protocols without context_signature get no
    ``supersedes`` field; existing pre-Event-84 protocols remain
    valid; the field is additive.

    Returns the full envelope.
    """
    target = path if path is not None else _protocols_path()
    if "type" not in payload:
        payload = {**payload, "type": PROTOCOL_TYPE}
    elif payload["type"] != PROTOCOL_TYPE:
        raise ChainError(
            f"write_protocol: payload.type must be {PROTOCOL_TYPE!r} "
            f"(got {payload['type']!r})"
        )

    # Auto-detect supersede unless the caller already set the field.
    if "supersedes" not in payload:
        sig = payload.get("context_signature")
        if isinstance(sig, dict):
            predecessor = _find_predecessor(target, sig)
            if predecessor:
                payload = {**payload, "supersedes": predecessor}

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
    cap: int | None = None,
    now: datetime | None = None,
    skip_counter_path: Path | None = None,
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
    # Open-set backpressure + relief (Event 158). Consulted AFTER dedup
    # so a suppressed duplicate never bumps the decline counter. At cap
    # the relief valve first ages out open entries past the floor; if
    # the set stays saturated the write declines with a marker dict
    # (same tolerate-discarding contract as suppressed_duplicate).
    now_dt = now or datetime.now(timezone.utc)
    cap_value = _resolve_deferred_open_cap(cap)
    if not _deferred_cap_admit(target, cap_value, now_dt):
        _bump_deferred_skip_counter(
            "cap_exceeded", now_dt, path=skip_counter_path
        )
        return {
            "declined_at_cap": True,
            "open_cap": cap_value,
            "reason": "cap_exceeded",
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
    include_superseded: bool = False,
) -> list[dict]:
    """Chain-verified read. Stops at first break. Filters on
    ``context_signature.project_name`` and ``blueprint`` when
    provided. Returns a list of envelopes — caller accesses
    business fields via ``rec["payload"]``.

    Event 84 / CP-TEMPORAL-INTEGRITY-EXPANSION-01 Item 4 — by default,
    ``include_superseded=False`` filters out protocols whose
    ``entry_hash`` appears as some later protocol's ``supersedes``
    field (i.e., they've been superseded). Active-guidance queries
    (``_guidance.py:query``) inherit this filter via
    ``_load_protocols_cached``.

    Pass ``include_superseded=True`` for forensic / archaeology reads
    that want the full chain including superseded entries.
    """
    target = path if path is not None else _protocols_path()
    superseded: set[str] = set() if include_superseded else _superseded_hashes(target)
    out: list[dict] = []
    for rec in _chain_iter(target, verify=True):
        payload = rec.get("payload") if isinstance(rec, dict) else None
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != PROTOCOL_TYPE:
            continue
        if not include_superseded:
            entry_hash = rec.get("entry_hash") if isinstance(rec, dict) else None
            if isinstance(entry_hash, str) and entry_hash in superseded:
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


def open_deferred_discoveries(*, path: Path | None = None) -> list[dict]:
    """Discoveries still awaiting an operator verdict.

    OPEN iff payload status is in ``OPEN_STATUSES`` (legacy records
    without a status count as open — the historical Blueprint-D writer
    emitted none) AND no ``deferred_discovery_verdict`` OR
    ``deferred_discovery_expiry`` record references the discovery's
    ``entry_hash`` (Event 158: an expiry closes like a verdict does).
    Single chain pass; the SessionStart banner and ``episteme guide
    --deferred`` read this so a verdicted finding stops re-firing every
    session.
    """
    target = path if path is not None else _deferred_discoveries_path()
    discoveries: list[dict] = []
    verdicted: set[str] = set()
    for rec in _chain_iter(target, verify=True):
        payload = rec.get("payload") if isinstance(rec, dict) else None
        if not isinstance(payload, dict):
            continue
        ptype = payload.get("type")
        if ptype in (DISCOVERY_VERDICT_TYPE, DISCOVERY_EXPIRY_TYPE):
            ref = payload.get("ref")
            if isinstance(ref, str) and ref:
                verdicted.add(ref)
        elif ptype == DEFERRED_DISCOVERY_TYPE:
            status = payload.get("status")
            if status is None or status in OPEN_STATUSES:
                discoveries.append(rec)
    return [
        d for d in discoveries
        if str(d.get("entry_hash") or "") not in verdicted
    ]


def _discovery_ref_sets(target: Path) -> tuple[list[dict], set[str], set[str]]:
    """Single chain pass → (open-shaped discovery envelopes,
    verdict refs, expiry refs). Open-shaped = status pending/None;
    callers apply the closing semantics they need."""
    discoveries: list[dict] = []
    verdict_refs: set[str] = set()
    expiry_refs: set[str] = set()
    for rec in _chain_iter(target, verify=True):
        payload = rec.get("payload") if isinstance(rec, dict) else None
        if not isinstance(payload, dict):
            continue
        ptype = payload.get("type")
        if ptype == DISCOVERY_VERDICT_TYPE:
            ref = payload.get("ref")
            if isinstance(ref, str) and ref:
                verdict_refs.add(ref)
        elif ptype == DISCOVERY_EXPIRY_TYPE:
            ref = payload.get("ref")
            if isinstance(ref, str) and ref:
                expiry_refs.add(ref)
        elif ptype == DEFERRED_DISCOVERY_TYPE:
            status = payload.get("status")
            if status is None or status in OPEN_STATUSES:
                discoveries.append(rec)
    return discoveries, verdict_refs, expiry_refs


def _verdictable_discoveries(*, path: Path | None = None) -> list[dict]:
    """Discoveries an operator verdict may target: OPEN ones plus
    expiry-closed ones with no verdict yet. An operator verdict
    SUPERSEDES a machine expiry (Event 158 review — mirrors the Event
    157 spot-check semantics): cap relief must not permanently block a
    real disposition, especially the Event 152 ``accepted`` verdict
    whose whole point is naming the cost of ignorance."""
    target = path if path is not None else _deferred_discoveries_path()
    discoveries, verdict_refs, _ = _discovery_ref_sets(target)
    return [
        d for d in discoveries
        if str(d.get("entry_hash") or "") not in verdict_refs
    ]


def expired_unverdicted_count(*, path: Path | None = None) -> int:
    """Count of discoveries machine-expired by cap relief with no
    operator verdict recorded. Surfaced by the SessionStart banner and
    ``episteme deferred list`` so mass expiry is never invisible
    (Event 158 review)."""
    target = path if path is not None else _deferred_discoveries_path()
    discoveries, verdict_refs, expiry_refs = _discovery_ref_sets(target)
    return sum(
        1 for d in discoveries
        if str(d.get("entry_hash") or "") in expiry_refs
        and str(d.get("entry_hash") or "") not in verdict_refs
    )


def expired_unverdicted_discoveries(*, path: Path | None = None) -> list[dict]:
    """The machine-expired, still-unverdicted discovery envelopes —
    ``episteme deferred list --expired`` renders these with full refs so
    the supersede path is actually reachable."""
    target = path if path is not None else _deferred_discoveries_path()
    discoveries, verdict_refs, expiry_refs = _discovery_ref_sets(target)
    return [
        d for d in discoveries
        if str(d.get("entry_hash") or "") in expiry_refs
        and str(d.get("entry_hash") or "") not in verdict_refs
    ]


def append_discovery_verdict(
    ref: str,
    verdict: str,
    rationale: str,
    *,
    path: Path | None = None,
) -> dict:
    """Record an operator verdict for an OPEN deferred discovery.

    ``ref`` is the discovery's entry_hash or a unique prefix of at
    least 8 chars. Append-only by design (module § Resolution layer);
    re-verdicting an already-closed discovery is rejected so the
    ledger cannot accumulate contradictory verdicts. Raises
    ``ChainError`` with an operator-actionable message on any invalid
    input — callers surface it verbatim.
    """
    target = path if path is not None else _deferred_discoveries_path()
    verdict = (verdict or "").strip().lower()
    if verdict not in RESOLUTION_VERDICTS:
        raise ChainError(
            f"verdict must be one of {sorted(RESOLUTION_VERDICTS)} "
            f"(got {verdict!r})"
        )
    rationale = (rationale or "").strip()
    if len(rationale) < _VERDICT_RATIONALE_FLOOR:
        raise ChainError(
            f"rationale must be >= {_VERDICT_RATIONALE_FLOOR} chars — "
            "name what was done, why the finding is noise/duplicate, or "
            "(accepted) the cost of ignorance"
        )
    ref = (ref or "").strip()
    if len(ref) < _REF_PREFIX_FLOOR:
        raise ChainError(
            f"ref must be an entry_hash or a >= {_REF_PREFIX_FLOOR}-char "
            f"prefix (got {ref!r})"
        )
    # Match the full `sha256:<hex>` entry_hash OR a bare hex prefix: entries
    # are stored scheme-prefixed but `episteme deferred list` also shows the
    # bare hex, so a copy-paste of either must resolve (Event 152 — the
    # scheme-only startswith rejected bare hex, forcing operators to prepend
    # `sha256:` by hand).
    def _ref_matches(entry_hash: str) -> bool:
        if entry_hash.startswith(ref):
            return True
        _, _, bare = entry_hash.partition(":")
        return bool(bare) and bare.startswith(ref)

    # Event 158 review: match against verdictable (open OR expiry-closed
    # -but-unverdicted) discoveries — an operator verdict supersedes a
    # machine expiry; only a prior operator verdict blocks.
    matches = [
        d for d in _verdictable_discoveries(path=target)
        if _ref_matches(str(d.get("entry_hash") or ""))
    ]
    if not matches:
        raise ChainError(
            f"no verdictable deferred discovery matches {ref!r} — it "
            "may already carry an operator verdict, or the ref is wrong "
            "(open: `episteme deferred list` · machine-expired: "
            "`episteme deferred list --expired`)"
        )
    if len(matches) > 1:
        raise ChainError(
            f"ref {ref!r} is ambiguous ({len(matches)} open matches) — "
            "use a longer prefix"
        )
    full_hash = str(matches[0]["entry_hash"])
    envelope = _chain_append(target, {
        "type": DISCOVERY_VERDICT_TYPE,
        "ref": full_hash,
        "verdict": verdict,
        "rationale": rationale,
    })
    # Drain activity — reset the backpressure window (Event 158) so the
    # banner's 'skipped since last drain' stays truthful.
    _reset_deferred_skip_counter(datetime.now(timezone.utc))
    return envelope


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

    # §4.1 — a chain-rewrite op: shared rewrite mutex FIRST, then the
    # per-file lock (lock-order law). The rewrite uses atomic_replace_file
    # directly, so no second same-process flock is taken.
    with _rewrite_lock(target.parent), _chain_locked(target):
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


# ---------------------------------------------------------------------------
# One-time CP-DEDUP-01 compaction (deferred_discoveries)
# ---------------------------------------------------------------------------


def compact_deferred_discoveries(
    *,
    path: Path | None = None,
    dedup_desc_prefix: int = DEFAULT_DEDUP_DESC_PREFIX,
    dry_run: bool = False,
) -> CompactResult:
    """One-time in-place compaction of the deferred_discoveries chain.

    Event 49's CP-DEDUP-01 stopped *new* duplicates at write time via a
    pre-write tail-scan (see ``write_deferred_discovery``). This function
    is the complementary one-shot cleanup of the chain that bloated
    *before* that gate shipped — the framework writer historically
    logged identical findings on every ``cascade:architectural`` firing
    (a 32x duplication ratio across 1,294 records).

    Algorithm (modelled on ``upgrade_cp5_prechain`` — the sanctioned
    in-place atomic-rewrite + recompute-from-GENESIS pattern):

    1. Read + parse every JSONL line. Any non-JSON / non-dict line aborts
       with ``ChainError`` BEFORE any write — no partial rewrite.
    2. Walk in file order keeping a seen-set of
       ``_dedup_key(payload, dedup_desc_prefix)``. Among payloads whose
       ``type == "deferred_discovery"`` AND ``status`` in
       ``OPEN_STATUSES``, KEEP the FIRST envelope per key and drop later
       open duplicates. ALWAYS keep non-deferred_discovery payloads and
       non-open (resolved / superseded / closed) records verbatim — the
       audit trail is never dropped.
    3. If nothing was removed (``total_after == total_before``),
       short-circuit ``status="noop"`` WITHOUT writing a backup.
    4. Otherwise back the original bytes up to
       ``<name>.compact-<ts>.bak``, rebuild by re-walking the KEPT
       records recomputing ``prev_hash`` from ``GENESIS_PREV_HASH`` +
       ``entry_hash`` via ``compute_entry_hash(prev, original_ts,
       payload)`` while preserving each kept record's ORIGINAL envelope
       ``ts`` (byte-stable re-run), ``atomic_replace_file``, then
       ``verify_chain`` and raise ``ChainError`` if not intact (backup
       preserved).

    ``dry_run=True`` computes the would-be result (status, counts,
    removed) without backing up or rewriting; ``backup_path`` /
    ``head_hash`` stay None on the dry-run compaction path.

    Idempotent: a second run finds no open duplicates and returns
    ``noop`` (no new backup).
    """
    target = path if path is not None else _deferred_discoveries_path()

    if not target.is_file():
        return CompactResult(
            status="missing",
            total_before=0,
            total_after=0,
            removed=0,
            backup_path=None,
            head_hash=None,
            message=f"{target} does not exist — nothing to compact",
        )

    # §4.1 retrofit — the whole-window lock this op previously lacked.
    # Lock-order law: shared rewrite mutex FIRST, then the per-file
    # lock (matching the sibling compact_protocols). The rebuild uses
    # compute_entry_hash + atomic_replace_file directly (never
    # _chain.append), so no second same-process flock is taken.
    with _rewrite_lock(target.parent), _chain_locked(target):
        try:
            text = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise ChainError(f"compact_deferred_discoveries read: {exc}") from exc

        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            return CompactResult(
                status="empty",
                total_before=0,
                total_after=0,
                removed=0,
                backup_path=None,
                head_hash=None,
                message=f"{target} is empty — nothing to compact",
            )

        # Parse every line first. A single bad line aborts the whole run so
        # we never produce a partial rewrite (matches upgrade_cp5_prechain).
        parsed: list[dict] = []
        for idx, line in enumerate(lines):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ChainError(
                    f"{target}:line {idx + 1}: not valid JSON ({exc})"
                ) from exc
            if not isinstance(rec, dict):
                raise ChainError(f"{target}:line {idx + 1}: not a JSON object")
            parsed.append(rec)

        total_before = len(parsed)

        # INPUT chain pre-verify (Event 136 review must-fix). The rebuild below
        # recomputes prev_hash/entry_hash from GENESIS, so a pre-existing break
        # or tamper in the input would be SILENTLY "healed" into a self-consistent
        # chain — laundering a quarantined/tampered record into a verified state,
        # and the post-rebuild verify passes by construction so it can never catch
        # this. Refuse to compact a non-intact input (mirrors the sibling
        # upgrade_cp5_prechain guard). The operator must resolve the break
        # manually (archive + re-play from backup) before compaction. This fires
        # for the dry-run path too — you cannot safely preview a compaction whose
        # rebuild would erase tamper evidence.
        input_verdict = _chain_verify(target)
        if not input_verdict.intact:
            raise ChainError(
                f"{target}: input chain not intact ({input_verdict.reason}) — "
                f"refusing to compact. A GENESIS rebuild would launder the break "
                f"into a verified chain and promote quarantined records. Operator "
                f"must resolve the break manually (archive + re-play from backup) "
                f"before compaction."
            )

        # Verdicts AND cap-relief expiries couple to discoveries by
        # entry_hash (see § Resolution layer; Event 158 review finding —
        # an unremapped expiry ref would dangle after the rebuild and a
        # machine-expired discovery would silently RE-OPEN). A GENESIS
        # rebuild recomputes every entry_hash, so any closing ref would
        # dangle — unless we (1) never drop a closed discovery as a
        # duplicate, and (2) remap closing refs old->new during the
        # rebuild. Collect the referenced hashes first.
        verdict_refs: set[str] = set()
        for rec in parsed:
            payload = rec.get("payload")
            if isinstance(payload, dict) and payload.get("type") in (
                DISCOVERY_VERDICT_TYPE, DISCOVERY_EXPIRY_TYPE
            ):
                ref = payload.get("ref")
                if isinstance(ref, str) and ref:
                    verdict_refs.add(ref)

        # Walk in file order; keep the first open deferred_discovery per
        # dedup key, drop later open UNVERDICTED duplicates, keep everything
        # else. A verdicted discovery is never dropped (its verdict refs it)
        # but its key is still recorded as seen — otherwise a later
        # unverdicted duplicate of a resolved finding would survive as
        # "first" and keep re-firing the banner (adversarial finding
        # 2026-07-03: verdicting the first member must not defeat dedup of
        # the rest).
        seen_keys: set[tuple[str, str]] = set()
        kept: list[dict] = []
        for rec in parsed:
            payload = rec.get("payload")
            if (
                isinstance(payload, dict)
                and payload.get("type") == DEFERRED_DISCOVERY_TYPE
                and str(payload.get("status", "pending")) in OPEN_STATUSES
            ):
                key = _dedup_key(payload, dedup_desc_prefix)
                verdicted = str(rec.get("entry_hash") or "") in verdict_refs
                if key in seen_keys and not verdicted:
                    continue  # later open, unverdicted duplicate — drop
                seen_keys.add(key)
            kept.append(rec)

        total_after = len(kept)
        removed = total_before - total_after

        if removed == 0:
            return CompactResult(
                status="noop",
                total_before=total_before,
                total_after=total_after,
                removed=0,
                backup_path=None,
                head_hash=_chain_verify(target).head_hash,
                message=(
                    f"{target}: no open duplicates among {total_before} records "
                    f"— nothing to compact"
                ),
            )

        # Rebuild the chain from GENESIS, preserving each kept record's
        # ORIGINAL envelope ts (byte-stable: re-running on already-compacted
        # input is a noop because the hashes reproduce exactly).
        new_lines: list[str] = []
        expected_prev = GENESIS_PREV_HASH
        head_hash = expected_prev
        # old entry_hash -> new entry_hash, so a verdict's `ref` (which
        # points at a discovery's OLD hash) can be rewritten to the new one.
        # A discovery always precedes its verdict in append order, so the
        # map entry exists by the time the verdict is rebuilt.
        hash_remap: dict[str, str] = {}
        for rec in kept:
            payload = rec.get("payload")
            ts = rec.get("ts")
            if not isinstance(payload, dict) or not isinstance(ts, str):
                raise ChainError(
                    f"{target}: kept record missing payload / ts during rebuild "
                    f"(payload={type(payload).__name__}, ts={type(ts).__name__})"
                )
            if payload.get("type") in (
                DISCOVERY_VERDICT_TYPE, DISCOVERY_EXPIRY_TYPE
            ):
                old_ref = payload.get("ref")
                if isinstance(old_ref, str) and old_ref in hash_remap:
                    payload = {**payload, "ref": hash_remap[old_ref]}
            old_entry_hash = str(rec.get("entry_hash") or "")
            entry_hash = compute_entry_hash(expected_prev, ts, payload)
            if old_entry_hash:
                hash_remap[old_entry_hash] = entry_hash
            envelope = {
                "schema_version": UPGRADED_FORMAT_MARKER,
                "ts": ts,
                "prev_hash": expected_prev,
                "payload": payload,
                "entry_hash": entry_hash,
            }
            new_lines.append(json.dumps(envelope, ensure_ascii=False))
            expected_prev = entry_hash
            head_hash = entry_hash

        if dry_run:
            return CompactResult(
                status="compacted",
                total_before=total_before,
                total_after=total_after,
                removed=removed,
                backup_path=None,
                head_hash=None,
                message=(
                    f"{target}: DRY RUN — would remove {removed} open duplicate(s), "
                    f"leaving {total_after} of {total_before} records"
                ),
            )

        # Backup the original bytes before any rewrite.
        from datetime import datetime, timezone

        backup_ts = (
            datetime.now(timezone.utc).isoformat().replace(":", "").replace(".", "-")
        )
        backup = target.with_suffix(f".compact-{backup_ts}.bak")
        try:
            backup.write_bytes(target.read_bytes())
        except OSError as exc:
            raise ChainError(f"compact_deferred_discoveries backup: {exc}") from exc

        new_contents = ("\n".join(new_lines) + "\n").encode("utf-8")
        try:
            _atomic_replace(target, new_contents)
        except OSError as exc:
            raise ChainError(
                f"compact_deferred_discoveries atomic replace: {exc}"
            ) from exc

        post_verdict = _chain_verify(target)
        if not post_verdict.intact:
            raise ChainError(
                f"{target}: compaction wrote file but post-verify failed "
                f"({post_verdict.reason}). Backup preserved at {backup}."
            )

        return CompactResult(
            status="compacted",
            total_before=total_before,
            total_after=total_after,
            removed=removed,
            backup_path=backup,
            head_hash=post_verdict.head_hash,
            message=(
                f"{target}: compacted {total_before} → {total_after} records "
                f"({removed} open duplicate(s) removed); chain intact. "
                f"Backup: {backup}"
            ),
        )


# ---------------------------------------------------------------------------
# One-time cascade-synthesis compaction (protocols)
# ---------------------------------------------------------------------------

CASCADE_BLUEPRINT = "architectural_cascade"


def _cascade_content_key(payload: dict) -> str | None:
    """Content-identity key for a cascade-synthesis protocol — the dedup
    axis for ``compact_protocols``. Returns None for every record it
    cannot positively identify as a cascade duplicate (always kept).

    Scope: ONLY ``type == "protocol"`` AND
    ``blueprint == "architectural_cascade"``. A non-cascade protocol or
    a foreign type is out of scope → None.

    Key: the STORED ``cascade_hash`` when present as a str (modern
    records, emitted since commit 1c01f9d). The ~457-record Event-143
    spam predates that field, so for a legacy cascade record the key is
    RECOMPUTED from the payload's own ``source_fields`` / ``op_outcome``
    via the kernel's own ``_cascade_synthesis.cascade_hash`` — the same
    function the emit path uses, so a recomputed legacy key collides
    exactly with the stored key of a modern record describing the same
    resolution (proven in the ×22 cluster: 21 legacy recomputations
    collide with 1 stored key).

    FAIL-OPEN ON KEEPING: any exception during recomputation returns
    None (record kept). Dropping a legitimate protocol is the
    irreversible cost; keeping a duplicate is cheap and self-corrects on
    the next modern re-emission. The caller distinguishes an in-scope
    None (derivation failure — counted + surfaced) from an out-of-scope
    None (ordinary keep).
    """
    if not isinstance(payload, dict):
        return None
    if payload.get("type") != PROTOCOL_TYPE:
        return None
    if payload.get("blueprint") != CASCADE_BLUEPRINT:
        return None
    stored = payload.get("cascade_hash")
    if isinstance(stored, str):
        return stored
    try:
        # Lazy import: the compaction path is the only _framework caller
        # that needs the synthesis arm, and importing it eagerly at module
        # load would couple the whole framework substrate to the T13 arm.
        import _cascade_synthesis  # type: ignore  # pyright: ignore[reportMissingImports]

        sf = payload.get("source_fields") or {}
        oo = payload.get("op_outcome") or {}
        flaw = str(sf["flaw_classification"])
        posture = str(sf["posture_selected"])
        needs_update = [str(x) for x in (sf.get("blast_radius_surfaces") or [])]
        observable = str(sf.get("observable", ""))
        project = Path(str(oo.get("cwd") or ".")).resolve().name or "unknown_project"
        subsystem = _cascade_synthesis._subsystem(needs_update)
        return _cascade_synthesis.cascade_hash(
            project, subsystem, flaw, posture, needs_update, observable
        )
    except Exception:
        return None


def compact_protocols(
    *,
    path: Path | None = None,
    dry_run: bool = False,
) -> CompactResult:
    """One-time in-place compaction of the framework protocols chain.

    Event 143's cascade-synthesis arm chained hundreds of identical
    resolution protocols before content-hash dedup shipped (commit
    1c01f9d): a session surface carrying ``flaw_classification`` made the
    self-escalation trigger classify every tool call as a cascade, and
    per-command ``op_class`` variation defeated the signature-based
    supersede. This is the complementary one-shot cleanup of the ledger
    that bloated *before* the ``cascade_hash`` gate landed.

    Algorithm (modelled on ``compact_deferred_discoveries`` — the
    sanctioned in-place atomic-rewrite + recompute-from-GENESIS pattern):

    1. Read + parse every JSONL line. Any non-JSON / non-dict line aborts
       with ``ChainError`` BEFORE any write — no partial rewrite.
    2. INPUT chain pre-verify: refuse a non-intact input (a GENESIS
       rebuild would silently launder the break into a self-consistent
       chain and promote quarantined records — the post-rebuild verify
       passes by construction and can never catch it). Fires for the
       dry-run path too.
    3. Walk in file order. For each record derive
       ``_cascade_content_key(payload)``. Records with key None (every
       non-cascade payload, plus in-scope cascade records whose key could
       not be derived) are ALWAYS kept. Among cascade records with a key,
       KEEP the FIRST per key and drop later duplicates. Payloads stay
       VERBATIM (no ``cascade_hash`` backfill — audit purity; see the
       blind-spot note below for the bounded cost).
    4. ``removed == 0`` → ``noop`` without a backup.
    5. Rebuild from GENESIS preserving each kept record's ORIGINAL
       envelope ``ts`` (byte-stable re-run). Two remap maps carry
       ``supersedes`` across the rewrite:
       - ``drop_to_rep``: a DROPPED duplicate's OLD entry_hash → the kept
         representative's OLD entry_hash.
       - ``hash_remap``: a KEPT record's OLD entry_hash → its NEW one.
       For each kept payload whose ``supersedes`` points backward:
       redirect a reference to a dropped duplicate onto its
       representative (``drop_to_rep``), then rewrite to the new hash
       (``hash_remap``); leave verbatim if unresolved by both maps.
       ``supersedes`` always points backward in file order, so both maps
       are populated by the time a referrer is rebuilt.
    6. Backup the original bytes to ``<name>.compact-<ts>.bak``,
       ``atomic_replace_file``, then post-verify (``ChainError`` naming
       the preserved backup on failure).

    Concurrency: the ENTIRE read → pre-verify → keep-walk → backup →
    rebuild → replace → post-verify span runs under ``_locked(target)``.
    The live ledger is append-hot (hooks write during sessions); the
    sibling holds no lock — this is a deliberate improvement. The rebuild
    computes hashes via ``compute_entry_hash`` directly (never
    ``_chain.append``, which would take a second same-process flock on
    the held file and deadlock).

    ``dry_run=True`` returns the would-be counts after the keep-walk with
    ``backup_path`` / ``head_hash`` None; no backup, no rewrite.

    Idempotent: a second run finds no duplicates and returns ``noop``.

    Bounded blind spot: kept payloads are verbatim, so a kept LEGACY
    representative still lacks ``cascade_hash``. The write-time dedup walk
    keys on the stored field, so it will not recognise the kept legacy
    rep until ONE modern re-emission of the same resolution lands (that
    modern record carries the field and collapses onto the rep on the
    NEXT compaction). Cost is ≤1 future re-emission per legacy-kept
    cluster — accepted against audit purity.
    """
    target = path if path is not None else _protocols_path()

    if not target.is_file():
        return CompactResult(
            status="missing",
            total_before=0,
            total_after=0,
            removed=0,
            backup_path=None,
            head_hash=None,
            message=f"{target} does not exist — nothing to compact",
        )

    # Whole-window lock (see docstring § Concurrency). §4.1 lock-order
    # law: the shared rewrite mutex (cross-stream / cross-session) is
    # acquired FIRST, then the per-file lock — never the reverse. The
    # missing check is deliberately BEFORE the locks so _locked's ``a+``
    # open does not materialise an empty file for a truly-absent target.
    with _rewrite_lock(target.parent), _chain_locked(target):
        try:
            text = target.read_text(encoding="utf-8")
        except OSError as exc:
            raise ChainError(f"compact_protocols read: {exc}") from exc

        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            return CompactResult(
                status="empty",
                total_before=0,
                total_after=0,
                removed=0,
                backup_path=None,
                head_hash=None,
                message=f"{target} is empty — nothing to compact",
            )

        # Parse every line first — a single bad line aborts before any
        # write (matches the sibling; no partial rewrite).
        parsed: list[dict] = []
        for idx, line in enumerate(lines):
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ChainError(
                    f"{target}:line {idx + 1}: not valid JSON ({exc})"
                ) from exc
            if not isinstance(rec, dict):
                raise ChainError(f"{target}:line {idx + 1}: not a JSON object")
            parsed.append(rec)

        total_before = len(parsed)

        # INPUT chain pre-verify (laundering guard; fires for dry-run too).
        input_verdict = _chain_verify(target)
        if not input_verdict.intact:
            raise ChainError(
                f"{target}: input chain not intact ({input_verdict.reason}) — "
                f"refusing to compact. A GENESIS rebuild would launder the "
                f"break into a verified chain and promote quarantined records. "
                f"Operator must resolve the break manually (archive + re-play "
                f"from backup) before compaction."
            )

        # Keep-walk: first-wins per content key; record dropped-duplicate
        # -> representative so a later supersedes ref can be re-pointed.
        seen: dict[str, str] = {}  # content key -> kept rep OLD entry_hash
        drop_to_rep: dict[str, str] = {}  # dropped OLD hash -> rep OLD hash
        kept: list[dict] = []
        deriv_failures = 0
        for rec in parsed:
            payload = rec.get("payload")
            key = _cascade_content_key(payload) if isinstance(payload, dict) else None
            in_scope = (
                isinstance(payload, dict)
                and payload.get("type") == PROTOCOL_TYPE
                and payload.get("blueprint") == CASCADE_BLUEPRINT
            )
            if key is None:
                # In-scope + None means the key could not be derived —
                # counted + surfaced (fail-open on keeping). Out-of-scope
                # None is an ordinary keep.
                if in_scope:
                    deriv_failures += 1
                kept.append(rec)
                continue
            old = str(rec.get("entry_hash") or "")
            rep = seen.get(key)
            if rep is not None:
                if old:
                    drop_to_rep[old] = rep
                continue  # later duplicate — drop
            seen[key] = old
            kept.append(rec)

        total_after = len(kept)
        removed = total_before - total_after

        deriv_note = (
            f" ({deriv_failures} in-scope cascade record(s) kept — "
            f"content key underivable)"
            if deriv_failures
            else ""
        )

        if removed == 0:
            return CompactResult(
                status="noop",
                total_before=total_before,
                total_after=total_after,
                removed=0,
                backup_path=None,
                head_hash=input_verdict.head_hash,
                message=(
                    f"{target}: no cascade duplicates among {total_before} "
                    f"records — nothing to compact{deriv_note}"
                ),
            )

        # Rebuild from GENESIS, preserving each kept record's ORIGINAL ts
        # (byte-stable) and remapping supersedes old->new (incl. re-pointing
        # a reference to a dropped duplicate onto its representative).
        new_lines: list[str] = []
        expected_prev = GENESIS_PREV_HASH
        head_hash = expected_prev
        hash_remap: dict[str, str] = {}  # kept OLD entry_hash -> NEW
        for rec in kept:
            payload = rec.get("payload")
            ts = rec.get("ts")
            if not isinstance(payload, dict) or not isinstance(ts, str):
                raise ChainError(
                    f"{target}: kept record missing payload / ts during rebuild "
                    f"(payload={type(payload).__name__}, ts={type(ts).__name__})"
                )
            sup = payload.get("supersedes")
            if isinstance(sup, str) and sup.startswith("sha256:"):
                tgt = sup
                if tgt in drop_to_rep:
                    tgt = drop_to_rep[tgt]
                if tgt in hash_remap:
                    payload = {**payload, "supersedes": hash_remap[tgt]}
                # else: unresolved by both maps — leave verbatim.
            old_entry_hash = str(rec.get("entry_hash") or "")
            entry_hash = compute_entry_hash(expected_prev, ts, payload)
            if old_entry_hash:
                hash_remap[old_entry_hash] = entry_hash
            envelope = {
                "schema_version": UPGRADED_FORMAT_MARKER,
                "ts": ts,
                "prev_hash": expected_prev,
                "payload": payload,
                "entry_hash": entry_hash,
            }
            new_lines.append(json.dumps(envelope, ensure_ascii=False))
            expected_prev = entry_hash
            head_hash = entry_hash

        if dry_run:
            return CompactResult(
                status="compacted",
                total_before=total_before,
                total_after=total_after,
                removed=removed,
                backup_path=None,
                head_hash=None,
                message=(
                    f"{target}: DRY RUN — would remove {removed} cascade "
                    f"duplicate(s), leaving {total_after} of {total_before} "
                    f"records{deriv_note}"
                ),
            )

        # Backup the original bytes before any rewrite.
        from datetime import datetime, timezone

        backup_ts = (
            datetime.now(timezone.utc).isoformat().replace(":", "").replace(".", "-")
        )
        backup = target.with_suffix(f".compact-{backup_ts}.bak")
        try:
            backup.write_bytes(target.read_bytes())
        except OSError as exc:
            raise ChainError(f"compact_protocols backup: {exc}") from exc

        new_contents = ("\n".join(new_lines) + "\n").encode("utf-8")
        try:
            _atomic_replace(target, new_contents)
        except OSError as exc:
            raise ChainError(f"compact_protocols atomic replace: {exc}") from exc

        post_verdict = _chain_verify(target)
        if not post_verdict.intact:
            raise ChainError(
                f"{target}: compaction wrote file but post-verify failed "
                f"({post_verdict.reason}). Backup preserved at {backup}."
            )

        return CompactResult(
            status="compacted",
            total_before=total_before,
            total_after=total_after,
            removed=removed,
            backup_path=backup,
            head_hash=post_verdict.head_hash,
            message=(
                f"{target}: compacted {total_before} → {total_after} records "
                f"({removed} cascade duplicate(s) removed); chain intact. "
                f"Backup: {backup}{deriv_note}"
            ),
        )
