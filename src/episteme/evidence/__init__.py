"""Auditor-facing terminal viewer + Regulator Evidence Packet exporter.

`episteme evidence ...` is the CCO / Internal Audit / External Auditor entry
point. It is intentionally read-only — viewing surfaces, browsing the
register, drilling down into a single decision, exporting a ZIP packet for
regulator submission. There is no edit / delete / mutate path; amendments
create new signed surfaces with `parent_surface_hash` references.

Subcommands:
  posture                Tier 1 panel: signed%, chain breaks, CFR
  register               Tier 2 register: filterable list of decisions
  show <surface_id>      Tier 3 detail: drill-down into one decision
  alerts                 Tier 4: signature failures, chain breaks, lazy flags
  packet build           Regulator Evidence Packet ZIP exporter

This module subsumes what PRODUCTIZATION_PLAN.md § 4.2 originally split
between an "audit viewer" and a "packet exporter" — same surface index
substrate, two presentations.
"""
from __future__ import annotations

# pyright: reportMissingImports=false
from episteme.evidence._cli import build_parser, run_evidence_cli, main

__all__ = ["build_parser", "run_evidence_cli", "main"]
