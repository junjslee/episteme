"""argparse glue for `episteme evidence ...`."""
from __future__ import annotations

# pyright: reportMissingImports=false
import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from episteme.evidence._index import (
    compute_posture,
    detect_alerts,
    filter_entries,
    iter_index,
    load_entry,
)
from episteme.evidence._packet import build_packet
from episteme.evidence._viewer import (
    render_alerts,
    render_detail,
    render_posture_panel,
    render_register,
)
from episteme.surface._storage import find_surface


EXIT_OK = 0
EXIT_NOT_FOUND = 4
EXIT_USAGE = 64


def cmd_posture(args: argparse.Namespace) -> int:
    entries = list(filter_entries(
        iter_index(),
        since=args.since,
        until=args.until,
        ai_act_tier=args.tier,
    ))
    summary = compute_posture(entries, cfr_baseline=args.cfr_baseline)
    if args.format == "json":
        print(json.dumps({
            "period_from": summary.period_from,
            "period_to": summary.period_to,
            "total_decisions": summary.total_decisions,
            "signed_pct": summary.signed_pct,
            "chain_breaks": summary.chain_breaks,
            "test_signature_count": summary.test_signature_count,
            "high_risk_decisions": summary.high_risk_decisions,
            "confident_failures": summary.confident_failures,
            "cfr_current": summary.cfr_current,
            "cfr_baseline_pre_episteme": summary.cfr_baseline_pre_episteme,
            "tier_breakdown": summary.tier_breakdown,
            "blast_breakdown": summary.blast_breakdown,
            "by_operator": summary.by_operator,
        }, indent=2))
    else:
        print(render_posture_panel(summary))
    return EXIT_OK


def cmd_register(args: argparse.Namespace) -> int:
    entries = list(filter_entries(
        iter_index(),
        since=args.since,
        until=args.until,
        operator=args.operator,
        ai_act_tier=args.tier,
        reversibility=args.reversibility,
        decision_choice=args.choice,
    ))
    if args.limit:
        entries = entries[:args.limit]
    if args.format == "json":
        print(json.dumps([e.to_dict() for e in entries], indent=2))
    else:
        print(render_register(entries))
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    path = find_surface(args.surface_id)
    if not path:
        print(f"surface not found: {args.surface_id}", file=sys.stderr)
        return EXIT_NOT_FOUND
    entry = load_entry(path)
    if not entry:
        print(f"could not parse surface: {path}", file=sys.stderr)
        return EXIT_NOT_FOUND
    if args.format == "json":
        print(json.dumps(entry.to_dict(include_raw=True), indent=2))
    else:
        print(render_detail(entry))
    return EXIT_OK


def cmd_alerts(args: argparse.Namespace) -> int:
    entries = list(filter_entries(
        iter_index(),
        since=args.since,
        until=args.until,
    ))
    alerts = detect_alerts(entries)
    if args.format == "json":
        print(json.dumps(alerts, indent=2))
    else:
        print(render_alerts(alerts))
    return EXIT_OK


def cmd_packet_build(args: argparse.Namespace) -> int:
    entries = list(filter_entries(
        iter_index(),
        since=args.since,
        until=args.until,
        operator=args.operator,
        ai_act_tier=args.tier,
    ))
    if not entries:
        print("no surfaces match filters; refusing to build empty packet", file=sys.stderr)
        return EXIT_NOT_FOUND
    out = Path(args.output)
    manifest = build_packet(
        entries,
        framework=args.framework,
        output_path=out,
        period_from=args.since,
        period_to=args.until,
        include_rekor=not args.no_rekor,
    )
    if args.format == "json":
        print(json.dumps({
            "packet_path": str(out),
            "surfaces_included": manifest["counts"]["surfaces"],
            "sessions_included": manifest["counts"]["sessions"],
            "operators_included": manifest["counts"]["operators"],
            "framework": args.framework,
        }, indent=2))
    else:
        print(f"packet built: {out}")
        print(f"  framework:           {args.framework}")
        print(f"  surfaces included:   {manifest['counts']['surfaces']}")
        print(f"  sessions included:   {manifest['counts']['sessions']}")
        print(f"  operators included:  {manifest['counts']['operators']}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="episteme evidence",
        description="Auditor-facing viewer + Regulator Evidence Packet exporter.",
    )
    sub = p.add_subparsers(dest="action", required=True)

    # posture
    posture = sub.add_parser("posture", help="Tier 1 KPI panel")
    posture.add_argument("--since")
    posture.add_argument("--until")
    posture.add_argument("--tier", help="Filter by AI Act tier")
    posture.add_argument("--cfr-baseline", type=float, help="Pre-episteme baseline CFR for compare")
    posture.add_argument("--format", choices=("human", "json"), default="human")

    # register
    reg = sub.add_parser("register", help="Tier 2 decision register (filterable list)")
    reg.add_argument("--since")
    reg.add_argument("--until")
    reg.add_argument("--operator", help="Filter by operator pubkey fingerprint prefix")
    reg.add_argument("--tier", help="Filter by AI Act tier")
    reg.add_argument("--reversibility", help="reversible | irreversible")
    reg.add_argument("--choice", help="proceed | stop | audit")
    reg.add_argument("--limit", type=int, default=50)
    reg.add_argument("--format", choices=("human", "json"), default="human")

    # show
    show = sub.add_parser("show", help="Tier 3 decision detail drill-down")
    show.add_argument("surface_id")
    show.add_argument("--format", choices=("human", "json"), default="human")

    # alerts
    alerts = sub.add_parser("alerts", help="Tier 4 alerts + anomalies")
    alerts.add_argument("--since")
    alerts.add_argument("--until")
    alerts.add_argument("--format", choices=("human", "json"), default="human")

    # packet build
    packet = sub.add_parser("packet", help="Regulator Evidence Packet operations")
    packet_sub = packet.add_subparsers(dest="packet_action", required=True)
    build = packet_sub.add_parser("build", help="Build a Regulator Evidence Packet ZIP")
    build.add_argument("--since")
    build.add_argument("--until")
    build.add_argument("--operator")
    build.add_argument("--tier")
    build.add_argument(
        "--framework",
        required=True,
        choices=("eu-ai-act", "nist-genai", "sr-11-7", "eba-ml", "mas-feat", "osfi-e23", "finra"),
    )
    build.add_argument("--output", "-o", required=True)
    build.add_argument("--no-rekor", action="store_true", help="Skip transparency_log/")
    build.add_argument("--format", choices=("human", "json"), default="human")

    return p


def run_evidence_cli(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.action == "posture":
        return cmd_posture(args)
    if args.action == "register":
        return cmd_register(args)
    if args.action == "show":
        return cmd_show(args)
    if args.action == "alerts":
        return cmd_alerts(args)
    if args.action == "packet" and args.packet_action == "build":
        return cmd_packet_build(args)
    parser.print_help(sys.stderr)
    return EXIT_USAGE


def main(argv: Optional[List[str]] = None) -> int:
    return run_evidence_cli(argv)


if __name__ == "__main__":
    sys.exit(main())
