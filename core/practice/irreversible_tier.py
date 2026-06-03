"""DEPRECATED location — the tiered irreversible-op classifier moved to
``core/hooks/_irreversible_tier.py`` in Event 136 (Stage 4b), aligning it
with the underscore-prefixed hook-private convention
(``_scenario_detector``, ``_cascade_detector``, ``_blueprint_d``).

This module is a backward-compatibility shim. It aliases the real module
object into ``sys.modules`` so that any legacy import —
``from core.practice.irreversible_tier import classify`` or
``from core.practice import irreversible_tier as it; it.<attr>`` — resolves
to the SAME module object as ``core.hooks._irreversible_tier``. That single
shared object is load-bearing: it keeps one ``Tier`` enum identity across
import paths (so ``verdict.tier is Tier.ONE`` comparisons hold) and makes
test monkeypatching of module-private globals transparent regardless of
which path a caller used.

Deletable once all in-repo importers reference the new path; retained for
external / BYOS consumers during the transition.
"""
import sys

from core.hooks import _irreversible_tier as _impl

# Replace this shim module with the real module object so the two import
# paths are indistinguishable at runtime (same namespace, same Tier enum).
sys.modules[__name__] = _impl
