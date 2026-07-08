"""Blueprint D synthesis arm — T13 (Event 143).

Owns the PreToolUse -> PostToolUse handoff that turns a successfully
resolved architectural cascade into a context-scoped cascade protocol
in the Pillar 3 framework — the emit path whose absence E1 named as
the reason the dominant blueprint class could not compound
(kernel/FALSIFIABILITY_CONDITIONS.md § E1).

## Lifecycle

1. **PreToolUse** — `reasoning_surface_guard.py` admits a Blueprint D
   surface (structural validation passed, deferred discoveries
   chained). On admission the guard calls `write_pending_marker(...)`
   under every candidate correlation id
   (`~/.episteme/state/cascade_pending/<id>.json`).

2. **PostToolUse** — `fence_synthesis.py` (the shared PostToolUse
   finalizer hook) calls `finalize_on_success_with_fallback(...)`.
   If `exit_code == 0`, the resolution emits the spec'd protocol
   (docs/DESIGN_V1_0_SEMANTIC_GOVERNANCE.md:204):

       In context `<project + subsystem + flaw_class>`, posture
       `<patch|refactor>` with blast-radius class `<surfaces>`
       resolved without divergence because `<observable>`.

   through CP7's chained `_framework.write_protocol`. Either way all
   candidate markers are deleted.

Honest T13 limit (same shape as CP5's): the emit gate is
`exit_code == 0`. True retrospective sync-plan verification (orphan-
reference detection over the resulting diff) is spec-deferred to
v1.0.1 (spec line 53) — the observable quoted in the protocol is the
surface's own pre-committed one, not an independently re-measured one.

The context signature is the CANONICAL `_context_signature.build`
dict (not CP5's inline string hash): repeated resolutions in the same
`<project, blueprint, op_class>` context auto-supersede via
`_framework.write_protocol`, and CP9's guidance query can rank on
field overlap.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _fence_synthesis import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    MARKER_TTL_SECONDS,
    _redact,
)


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _episteme_home() -> Path:
    return Path(os.environ.get("EPISTEME_HOME") or (Path.home() / ".episteme"))


def _pending_dir() -> Path:
    return _episteme_home() / "state" / "cascade_pending"


# ---------------------------------------------------------------------------
# Pending marker (PreToolUse write) — per-correlation-id files, same
# concurrency posture as the fence arm (no flock needed).
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _needs_update_surfaces(surface: dict) -> list[str]:
    out: list[str] = []
    brm = surface.get("blast_radius_map")
    if isinstance(brm, list):
        for entry in brm:
            if isinstance(entry, dict) and entry.get("status") == "needs_update":
                s = str(entry.get("surface", "")).strip()
                if s:
                    out.append(s)
    return out


def _observable(surface: dict) -> str:
    """The observable the protocol quotes: prefer the verification
    trace's threshold (the thing that held), fall back to the
    pre-committed disconfirmation (the thing that did not fire)."""
    trace = surface.get("verification_trace")
    if isinstance(trace, dict):
        t = str(trace.get("threshold_observable", "")).strip()
        if t:
            return t
    disc = surface.get("disconfirmation")
    if isinstance(disc, list):
        return "; ".join(str(d) for d in disc)
    return str(disc or "")


def write_pending_marker(
    surface: dict,
    correlation: str,
    cwd: Path,
    cmd: str,
) -> Path | None:
    """Persist the admitted Blueprint D surface for the PostToolUse
    finalizer. Returns the marker path, or None on graceful-degrade
    failure — bookkeeping never blocks an admitted op."""
    try:
        marker = {
            "version": 1,
            "correlation_id": correlation,
            "written_at": datetime.now(timezone.utc).isoformat(),
            "cwd": str(cwd),
            "command_redacted": _redact(cmd),
            # Free-text surface fields are redacted at persistence time:
            # the observable quotes measured command/test output — exactly
            # where a leaked secret is most likely to appear (Event 143
            # adversarial review, confirmed by probe).
            "surface": {
                "flaw_classification": str(surface.get("flaw_classification", "")),
                "posture_selected": str(surface.get("posture_selected", "")),
                "core_question": _redact(str(surface.get("core_question", ""))),
                "needs_update_surfaces": _needs_update_surfaces(surface),
                "observable": _redact(_observable(surface)),
            },
        }
        path = _pending_dir() / f"{correlation}.json"
        _atomic_write_json(path, marker)
        return path
    except OSError:
        return None


def read_pending_marker(correlation: str) -> dict | None:
    path = _pending_dir() / f"{correlation}.json"
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    written = data.get("written_at")
    if isinstance(written, str):
        try:
            age = (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(written.replace("Z", "+00:00"))
            ).total_seconds()
            if age > MARKER_TTL_SECONDS:
                return None
        except ValueError:
            pass
    return data


def delete_pending_marker(correlation: str) -> None:
    try:
        (_pending_dir() / f"{correlation}.json").unlink()
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Protocol build + finalize (PostToolUse write)
# ---------------------------------------------------------------------------

def _short(text: str, limit: int = 160) -> str:
    if not text:
        return ""
    flat = " ".join(text.split())
    if len(flat) > limit:
        return flat[: limit - 1] + "…"
    return flat


def _subsystem(needs_update: list[str]) -> str:
    """The cascade's primary subsystem: the directory of the first
    needs_update surface (that is where the flaw lived)."""
    if not needs_update:
        return "repo"
    first = needs_update[0]
    parent = str(Path(first).parent)
    return first if parent in (".", "") else parent


def _op_class(cmd: str) -> str:
    tokens = cmd.split()
    if len(tokens) >= 2:
        return " ".join(tokens[:2])
    if tokens:
        return tokens[0]
    return "cascade:resolution"


def cascade_hash(
    project: str,
    subsystem: str,
    flaw: str,
    posture: str,
    needs_update: list[str],
    observable: str,
) -> str:
    """Content hash of a cascade resolution — the dedup key.

    Live-dogfood lesson (Event 143): a session surface carrying
    flaw_classification makes the self-escalation trigger classify every
    tool call as cascade, and per-command op_class variation defeats the
    signature-based supersede — 438 identical-content protocols chained
    in one session. The know-how lives in the resolution content, so
    emission is bounded by content identity (mirrors
    _interrogation.lesson_hash), not by which ops ran under it.
    """
    import hashlib

    seed = "\x1f".join(
        [project, subsystem, flaw, posture, "\x1e".join(needs_update), observable]
    ).encode("utf-8", errors="replace")
    return "ch_" + hashlib.sha256(seed).hexdigest()[:16]


def _build_protocol(marker: dict, exit_code: int | None) -> dict:
    surface = marker.get("surface", {}) if isinstance(marker.get("surface"), dict) else {}
    flaw = str(surface.get("flaw_classification", "")) or "other"
    posture = str(surface.get("posture_selected", "")) or "patch"
    needs_update = [
        str(s) for s in (surface.get("needs_update_surfaces") or []) if str(s)
    ]
    observable = str(surface.get("observable", ""))
    cwd = Path(marker.get("cwd") or ".")
    project = cwd.resolve().name or "unknown_project"
    subsystem = _subsystem(needs_update)
    surfaces_text = _short(", ".join(needs_update) or "no-surface-declared")
    cmd = str(marker.get("command_redacted", ""))

    import _context_signature  # type: ignore  # pyright: ignore[reportMissingImports]

    sig = _context_signature.build(
        cwd,
        blueprint_name="architectural_cascade",
        op_class=_op_class(cmd),
        constraint_head=None,
    )

    protocol_text = (
        f"In context `{project}::{subsystem}::{flaw}`, posture "
        f"`{posture}` with blast-radius class `{surfaces_text}` resolved "
        f"without divergence because `{_short(observable)}`."
    )
    return {
        "type": "protocol",
        "version": 1,
        "blueprint": "architectural_cascade",
        "source": "cascade_resolution",
        "synthesized_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": marker.get("correlation_id", ""),
        "context_signature": sig.as_dict(),
        "cascade_hash": cascade_hash(
            project, subsystem, flaw, posture, needs_update, observable
        ),
        "synthesized_protocol": protocol_text,
        "source_fields": {
            "flaw_classification": flaw,
            "posture_selected": posture,
            # Capped: a pathological surface must not bloat the durable
            # record; the count preserves the true blast-radius size.
            "blast_radius_surfaces": needs_update[:32],
            "blast_radius_count": len(needs_update),
            "core_question": str(surface.get("core_question", "")),
            "observable": observable,
        },
        "op_outcome": {
            "exit_code": exit_code,
            "cwd": str(marker.get("cwd", "")),
            "command_redacted": cmd,
        },
    }


def finalize_on_success_with_fallback(
    candidates: list[str],
    exit_code: int | None,
) -> dict | None:
    """Walk candidate correlation ids (Event 50 · CP-FENCE-02 pairing),
    synthesize on the first marker found iff exit_code == 0, and delete
    ALL candidate markers regardless of outcome. Returns the chain
    envelope on write, else None. Never raises past its boundary."""
    found: dict | None = None
    for cid in candidates:
        m = read_pending_marker(cid)
        if m is not None:
            found = m
            break
    try:
        if found is None or exit_code != 0:
            return None
        payload = _build_protocol(found, exit_code)
        try:
            from _framework import (  # type: ignore  # pyright: ignore[reportMissingImports]
                ChainError as _ChainError,
                _cascade_content_key,
                _chain_iter,
                _protocols_path,
                write_protocol as _write_protocol,
            )
        except ImportError:
            return None
        # Content dedup: identical resolution content emits exactly once,
        # ever — superseded records included, so a superseded protocol
        # cannot resurrect as a fresh duplicate. The walk is UNVERIFIED:
        # a verified iteration stops silently at the first chain break,
        # blinding dedup to everything past it and reopening the 438-spam
        # (Event 143 review, confirmed by probe). Integrity checking is
        # verify_chains' job; dedup's job is seeing every record. And the
        # gate FAILS CLOSED — if uniqueness cannot be proven, skipping
        # one legitimate protocol costs less than re-spamming the ledger.
        #
        # §5.1 read-side healing: key on `_cascade_content_key` (the
        # shared stored-else-recomputed helper) rather than the raw
        # `cascade_hash` field. A legacy record with NO stored field then
        # RECOMPUTES the same content key and participates in dedup with
        # zero payload mutation (audit purity — Event 144's verbatim
        # rule). The ≤1-re-emission-per-cluster blind spot closes for
        # every legacy record, forever, not just ones a compaction visited.
        key = _cascade_content_key(payload)
        try:
            target = _protocols_path()
            if key is not None and target.is_file():
                for env in _chain_iter(target, verify=False):
                    p = env.get("payload") if isinstance(env, dict) else None
                    if isinstance(p, dict) and _cascade_content_key(p) == key:
                        return None
        except (OSError, _ChainError):
            return None
        try:
            return _write_protocol(payload)
        except OSError:
            return None
    except Exception:
        # The docstring's never-raise contract is load-bearing: callers
        # in the PostToolUse path must stay exit-0 no matter what the
        # build/dedup path does.
        return None
    finally:
        for cid in candidates:
            delete_pending_marker(cid)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def pending_dir_for_tests() -> Path:
    return _pending_dir()


def build_protocol_for_tests(marker: dict, exit_code: int | None) -> dict:
    return _build_protocol(marker, exit_code)
