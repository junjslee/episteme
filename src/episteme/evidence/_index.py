"""Surface index — shared reading layer used by both viewer and packet.

The index is a lazy iterator over signed surfaces under .episteme/surfaces/,
yielding `IndexEntry` dataclasses with the fields the viewer and packet
exporter both need. Verification is intentionally NOT done at index time —
each consumer decides whether to verify (auditor view: yes; quick-list:
optional). This keeps the index cheap for large stores.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from episteme.surface._storage import iter_surfaces, surfaces_dir


@dataclass(frozen=True, slots=True)
class IndexEntry:
    surface_id: str
    session_id: str
    issued_at: str
    operator_pubkey_fingerprint: str
    parent_surface_hash: Optional[str]
    reversibility: str
    blast_radius: str
    ai_act_tier: str
    article_79_1_triggers: Tuple[str, ...]
    decision_choice: str
    decision_confidence: float
    signature_mode: str
    self_hash: str
    path: Path
    raw: Dict[str, Any]  # full signed-surface dict, for drill-down and verifier

    def to_dict(self, *, include_raw: bool = False) -> Dict[str, Any]:
        d = {
            "surface_id": self.surface_id,
            "session_id": self.session_id,
            "issued_at": self.issued_at,
            "operator_pubkey_fingerprint": self.operator_pubkey_fingerprint,
            "parent_surface_hash": self.parent_surface_hash,
            "reversibility": self.reversibility,
            "blast_radius": self.blast_radius,
            "ai_act_tier": self.ai_act_tier,
            "article_79_1_triggers": list(self.article_79_1_triggers),
            "decision_choice": self.decision_choice,
            "decision_confidence": self.decision_confidence,
            "signature_mode": self.signature_mode,
            "self_hash": self.self_hash,
            "path": str(self.path),
        }
        if include_raw:
            d["raw"] = self.raw
        return d


def _signature_mode_of(att_dict: Dict[str, Any]) -> str:
    sig = att_dict.get("signature_b64_or_hex", "")
    if sig.startswith("ed25519:"):
        return "production"
    if sig.startswith("test-hmac:"):
        return "test"
    return "unknown"


def load_entry(path: Path) -> Optional[IndexEntry]:
    """Load a single surface JSON into an IndexEntry. Returns None on parse
    failure so the index iterator can skip malformed files without raising."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    env = data.get("envelope", {})
    surf = data.get("surface", {})
    att = data.get("attestation", {})
    rc = surf.get("risk_classification", {})
    dec = surf.get("decision", {})
    try:
        return IndexEntry(
            surface_id=env.get("surface_id", ""),
            session_id=env.get("session_id", ""),
            issued_at=env.get("issued_at", ""),
            operator_pubkey_fingerprint=env.get("operator_pubkey_fingerprint", ""),
            parent_surface_hash=env.get("parent_surface_hash"),
            reversibility=rc.get("reversibility", ""),
            blast_radius=rc.get("blast_radius", ""),
            ai_act_tier=rc.get("ai_act_tier", ""),
            article_79_1_triggers=tuple(rc.get("article_79_1_triggers", [])),
            decision_choice=dec.get("choice", ""),
            decision_confidence=float(dec.get("confidence", 0.0)),
            signature_mode=_signature_mode_of(att),
            self_hash=data.get("self_hash", ""),
            path=path,
            raw=data,
        )
    except (TypeError, ValueError):
        return None


def iter_index(*, root: Optional[Path] = None) -> Iterator[IndexEntry]:
    """Yield IndexEntry items newest-first across all surfaces in the store."""
    for path in iter_surfaces(root=root):
        entry = load_entry(path)
        if entry is not None:
            yield entry


@dataclass
class PostureSummary:
    period_from: str
    period_to: str
    total_decisions: int
    signed_pct: float
    chain_breaks: int
    test_signature_count: int
    high_risk_decisions: int
    confident_failures: int
    cfr_current: Optional[float]
    cfr_baseline_pre_episteme: Optional[float]
    tier_breakdown: Dict[str, int] = field(default_factory=dict)
    blast_breakdown: Dict[str, int] = field(default_factory=dict)
    by_operator: Dict[str, int] = field(default_factory=dict)


def compute_posture(
    entries: Iterable[IndexEntry],
    *,
    cfr_baseline: Optional[float] = None,
) -> PostureSummary:
    """Aggregate posture KPIs from a stream of entries.

    `confident_failures` is currently 0 because there is no post-hoc oracle
    in v1. When the Phase 2 trial runs and oracle resolution is wired in,
    this will be populated from `<surface_id>.oracle.json` companion files
    or an external resolution database. See PRODUCTIZATION_PLAN.md § 1.2.
    """
    entries_list = list(entries)
    if not entries_list:
        return PostureSummary(
            period_from="", period_to="",
            total_decisions=0, signed_pct=0.0, chain_breaks=0,
            test_signature_count=0, high_risk_decisions=0,
            confident_failures=0, cfr_current=None,
            cfr_baseline_pre_episteme=cfr_baseline,
        )

    period_from = min(e.issued_at for e in entries_list if e.issued_at)
    period_to = max(e.issued_at for e in entries_list if e.issued_at)

    total = len(entries_list)
    signed = sum(1 for e in entries_list if e.self_hash)
    signed_pct = (signed / total * 100.0) if total else 0.0
    test_count = sum(1 for e in entries_list if e.signature_mode == "test")
    high_risk = sum(1 for e in entries_list if e.ai_act_tier == "high")

    # Chain breaks — group by session, sort by issued_at within session,
    # check parent_surface_hash continuity.
    by_session: Dict[str, List[IndexEntry]] = {}
    for e in entries_list:
        by_session.setdefault(e.session_id, []).append(e)
    chain_breaks = 0
    for session_entries in by_session.values():
        ordered = sorted(session_entries, key=lambda x: x.issued_at)
        prior_hash: Optional[str] = None
        for e in ordered:
            if prior_hash is not None and e.parent_surface_hash and e.parent_surface_hash != prior_hash:
                chain_breaks += 1
            prior_hash = e.self_hash

    tier_breakdown: Dict[str, int] = {}
    blast_breakdown: Dict[str, int] = {}
    by_operator: Dict[str, int] = {}
    for e in entries_list:
        tier_breakdown[e.ai_act_tier] = tier_breakdown.get(e.ai_act_tier, 0) + 1
        blast_breakdown[e.blast_radius] = blast_breakdown.get(e.blast_radius, 0) + 1
        by_operator[e.operator_pubkey_fingerprint[:16]] = by_operator.get(e.operator_pubkey_fingerprint[:16], 0) + 1

    return PostureSummary(
        period_from=period_from,
        period_to=period_to,
        total_decisions=total,
        signed_pct=signed_pct,
        chain_breaks=chain_breaks,
        test_signature_count=test_count,
        high_risk_decisions=high_risk,
        confident_failures=0,  # placeholder until oracle resolution is wired
        cfr_current=None,
        cfr_baseline_pre_episteme=cfr_baseline,
        tier_breakdown=tier_breakdown,
        blast_breakdown=blast_breakdown,
        by_operator=by_operator,
    )


def filter_entries(
    entries: Iterable[IndexEntry],
    *,
    since: Optional[str] = None,
    until: Optional[str] = None,
    operator: Optional[str] = None,
    ai_act_tier: Optional[str] = None,
    reversibility: Optional[str] = None,
    decision_choice: Optional[str] = None,
) -> Iterator[IndexEntry]:
    """Stream filter — each filter is None-as-wildcard, conjunctive."""
    for e in entries:
        if since and e.issued_at < since:
            continue
        if until and e.issued_at > until:
            continue
        if operator and not e.operator_pubkey_fingerprint.startswith(operator):
            continue
        if ai_act_tier and e.ai_act_tier != ai_act_tier:
            continue
        if reversibility and e.reversibility != reversibility:
            continue
        if decision_choice and e.decision_choice != decision_choice:
            continue
        yield e


def detect_alerts(entries: Iterable[IndexEntry]) -> List[Dict[str, Any]]:
    """Run light-weight checks across the index for Tier 4 alert surfacing.

    Each alert is a dict with:
      severity   info | advisory | warn | critical
      code       short tag
      detail     human-readable
      surface_id which surface(s) it ties to
    """
    alerts: List[Dict[str, Any]] = []
    entries_list = list(entries)

    # Test-mode signatures
    test_entries = [e for e in entries_list if e.signature_mode == "test"]
    if test_entries:
        alerts.append({
            "severity": "warn",
            "code": "test_mode_signatures_present",
            "detail": (
                f"{len(test_entries)} surface(s) signed in test-mode HMAC fallback. "
                f"Production audits will reject these. Install PyNaCl for Ed25519."
            ),
            "surface_ids": [e.surface_id for e in test_entries[:10]],
        })

    # Chain breaks — re-detect to surface specific ids
    by_session: Dict[str, List[IndexEntry]] = {}
    for e in entries_list:
        by_session.setdefault(e.session_id, []).append(e)
    for session_id, session_entries in by_session.items():
        ordered = sorted(session_entries, key=lambda x: x.issued_at)
        prior: Optional[IndexEntry] = None
        for e in ordered:
            if prior is not None and e.parent_surface_hash and e.parent_surface_hash != prior.self_hash:
                alerts.append({
                    "severity": "critical",
                    "code": "chain_break",
                    "detail": (
                        f"surface {e.surface_id} parent_surface_hash="
                        f"{e.parent_surface_hash[:16]}... does not match prior surface "
                        f"{prior.surface_id} self_hash={prior.self_hash[:16]}..."
                    ),
                    "surface_ids": [e.surface_id],
                })
            prior = e

    # Low-confidence high-risk proceeds
    for e in entries_list:
        if e.ai_act_tier == "high" and e.decision_choice == "proceed" and e.decision_confidence < 0.5:
            alerts.append({
                "severity": "advisory",
                "code": "low_confidence_high_risk_proceed",
                "detail": (
                    f"surface {e.surface_id} proceeded on a high-tier action with "
                    f"confidence {e.decision_confidence:.2f} (<0.50)"
                ),
                "surface_ids": [e.surface_id],
            })

    # Article 79(1) triggers without article_79_1_triggers list populated
    for e in entries_list:
        if e.ai_act_tier == "high" and not e.article_79_1_triggers:
            alerts.append({
                "severity": "info",
                "code": "missing_article_79_1_triggers",
                "detail": (
                    f"surface {e.surface_id} is tier=high but does not enumerate "
                    f"Article 79(1) triggers; Article 12(2)(a) compliance gap"
                ),
                "surface_ids": [e.surface_id],
            })

    return alerts
