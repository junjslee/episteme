"""Claude Code hook handlers shipped by the episteme distribution.

These are independent of the soak-protected `core/hooks/` directory.
That directory holds the existing kernel hot path (reasoning_surface_guard
and friends). This directory holds Phase 3+ additive hooks — most
importantly the opt-in signed-surface validator that runs in parallel
without mutating the soak-protected path.

The presence of this module does NOT change Claude Code behavior. To
activate, the operator wires the hook into .claude/settings.json
explicitly. The settings snippet ships with the skills/compliance-
evidence-layer/ bundle.
"""
from __future__ import annotations
