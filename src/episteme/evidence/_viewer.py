"""Terminal-first rendering for evidence viewer subcommands.

Pure ANSI / plain text. No external dependency on Rich, Textual, or any
TUI library — episteme kernel install must remain zero-dep. If the
operator wants color, they can pipe through `ccze` or a Rich-based
wrapper of their own; this module sticks to ASCII.

Functions emit strings; the CLI module prints them. This separation keeps
the rendering pure (no side effects) and unit-testable.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from typing import Any, Dict, Iterable, List

from episteme.evidence._index import IndexEntry, PostureSummary


def render_posture_panel(summary: PostureSummary, *, ansi: bool = False) -> str:
    """Tier 1 KPI panel — single screen, fixed width."""
    lines = []
    title = "POSTURE PANEL"
    lines.append("=" * 64)
    lines.append(f"{title:^64}")
    lines.append("=" * 64)
    period_str = f"{summary.period_from} → {summary.period_to}" if summary.period_from else "(no surfaces)"
    lines.append(f"Period: {period_str}")
    lines.append("")
    lines.append(f"  decisions logged             {summary.total_decisions:>8}")
    lines.append(f"  signed surfaces %            {summary.signed_pct:>8.1f}")
    lines.append(f"  chain breaks                 {summary.chain_breaks:>8}")
    lines.append(f"  test-mode signatures         {summary.test_signature_count:>8}")
    lines.append(f"  high-tier decisions          {summary.high_risk_decisions:>8}")
    lines.append(f"  confident failures (period)  {summary.confident_failures:>8}")
    cfr_str = f"{summary.cfr_current:.3f}" if summary.cfr_current is not None else "(no oracle data yet)"
    lines.append(f"  CFR current                  {cfr_str:>8}")
    baseline = f"{summary.cfr_baseline_pre_episteme:.3f}" if summary.cfr_baseline_pre_episteme else "(none)"
    lines.append(f"  CFR baseline (pre-episteme)  {baseline:>8}")
    lines.append("")
    if summary.tier_breakdown:
        lines.append("  by tier:")
        for k in sorted(summary.tier_breakdown):
            lines.append(f"    {k:<14} {summary.tier_breakdown[k]:>5}")
    if summary.blast_breakdown:
        lines.append("  by blast radius:")
        for k in sorted(summary.blast_breakdown):
            lines.append(f"    {k:<24} {summary.blast_breakdown[k]:>5}")
    if summary.by_operator:
        lines.append("  by operator (fingerprint prefix):")
        for k in sorted(summary.by_operator, key=lambda x: -summary.by_operator[x])[:8]:
            lines.append(f"    {k:<24} {summary.by_operator[k]:>5}")
    lines.append("=" * 64)
    return "\n".join(lines)


def render_register(entries: Iterable[IndexEntry]) -> str:
    """Tier 2 decision register — tabular list."""
    rows = list(entries)
    if not rows:
        return "(no surfaces matching filters)"
    header = f"{'surface_id':<32} {'issued_at':<26} {'tier':<10} {'reversibility':<14} {'choice':<8} {'sig':<10}"
    sep = "-" * len(header)
    body_lines = []
    for e in rows:
        body_lines.append(
            f"{e.surface_id:<32} {e.issued_at[:26]:<26} {e.ai_act_tier:<10} "
            f"{e.reversibility:<14} {e.decision_choice:<8} {e.signature_mode:<10}"
        )
    return "\n".join([header, sep] + body_lines)


def render_detail(entry: IndexEntry) -> str:
    """Tier 3 detail drill-down."""
    raw = entry.raw
    env = raw.get("envelope", {})
    surf = raw.get("surface", {})
    att = raw.get("attestation", {})
    lines = []
    lines.append("=" * 72)
    lines.append(f"DECISION DETAIL — {entry.surface_id}")
    lines.append("=" * 72)
    lines.append(f"Session:         {env.get('session_id')}")
    lines.append(f"Issued at:       {env.get('issued_at')}")
    lines.append(f"Operator (fp):   {env.get('operator_pubkey_fingerprint')}")
    lines.append(f"Parent:          {env.get('parent_surface_hash') or '(genesis)'}")
    lines.append(f"Signed at:       {att.get('signed_at')}")
    lines.append(f"Signature mode:  {entry.signature_mode}")
    lines.append(f"Self hash:       {entry.self_hash}")
    tsa = att.get("tsa") or {}
    rekor = att.get("transparency_log") or {}
    lines.append(f"TSA:             {tsa.get('tsa_url', '(none)')}  mode={tsa.get('mode', '-')}")
    lines.append(f"Rekor:           {rekor.get('log_id', '(none)')}  log_index={rekor.get('log_index', '-')}")
    lines.append("")
    lines.append(f"CORE QUESTION:")
    lines.append(f"  {surf.get('core_question', '')}")
    rc = surf.get("risk_classification", {})
    lines.append("")
    lines.append(f"RISK CLASSIFICATION:")
    lines.append(f"  reversibility:  {rc.get('reversibility')}")
    lines.append(f"  blast_radius:   {rc.get('blast_radius')}")
    lines.append(f"  ai_act_tier:    {rc.get('ai_act_tier')}")
    lines.append(f"  79(1) triggers: {', '.join(rc.get('article_79_1_triggers', [])) or '(none)'}")

    for label, items, fields in [
        ("KNOWNS", surf.get("knowns", []), ("fact", "source_artifact", "verification_method")),
        ("UNKNOWNS", surf.get("unknowns", []), ("unknown", "cost_of_ignorance")),
        ("ASSUMPTIONS", surf.get("assumptions", []), ("assumption", "if_wrong_then", "detectability")),
        ("DISCONFIRMATION", surf.get("disconfirmation_conditions", []), ("observable", "measurement_method")),
    ]:
        lines.append("")
        lines.append(f"{label} ({len(items)}):")
        if not items:
            lines.append("  (none)")
        for i, item in enumerate(items, 1):
            lines.append(f"  [{i}]")
            for f in fields:
                v = item.get(f) if isinstance(item, dict) else None
                if v is not None:
                    lines.append(f"      {f}: {v}")

    dec = surf.get("decision", {})
    lines.append("")
    lines.append(f"DECISION:")
    lines.append(f"  choice:                       {dec.get('choice')}")
    lines.append(f"  confidence:                   {dec.get('confidence')}")
    lines.append(f"  confidence_elicitation_method:{dec.get('confidence_elicitation_method')}")
    lines.append(f"  stop_rollback_path:           {dec.get('stop_rollback_path')}")
    lines.append("")
    lines.append(f"FILE: {entry.path}")
    lines.append("=" * 72)
    return "\n".join(lines)


def render_alerts(alerts: List[Dict[str, Any]]) -> str:
    if not alerts:
        return "(no alerts)"
    severity_order = {"critical": 0, "warn": 1, "advisory": 2, "info": 3}
    alerts_sorted = sorted(alerts, key=lambda a: severity_order.get(a.get("severity", ""), 4))
    lines = []
    lines.append(f"{'severity':<10} {'code':<40} count")
    lines.append("-" * 64)
    # Group by code for counts
    by_code: Dict[tuple, List[Dict[str, Any]]] = {}
    for a in alerts_sorted:
        key = (a.get("severity"), a.get("code"))
        by_code.setdefault(key, []).append(a)
    for (sev, code), items in by_code.items():
        lines.append(f"{sev:<10} {code:<40} {len(items):>5}")
    lines.append("")
    lines.append("Details (first 20):")
    for a in alerts_sorted[:20]:
        lines.append(f"  [{a.get('severity')}] {a.get('code')}: {a.get('detail')}")
    return "\n".join(lines)
