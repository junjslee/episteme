"""Asset-root resolution — repo checkout vs installed package (Event 177).

Every governance asset (core/hooks, kernel/, skills/, templates/) historically
resolved via ``Path(__file__).parents[2]`` — six independent copies of that
pattern, all of which point into ``lib/python3.X`` when the package is
pip-installed (measured: doctor's own wire probe flagged
``venv/lib/python3.11/core/hooks/... missing (wheel-shaped install?)``).
This module is the ONE definition of where assets live:

1. **Checkout wins.** Walk upward from this file looking for the checkout
   markers; a dev tree (or a venv nested inside one) resolves to the repo
   root exactly as before — zero behavior change for the operator.
2. **Packaged assets** otherwise: the ``episteme/_assets/`` tree that
   ``setup.py`` copies into the wheel (core/kernel/skills/templates, with the
   operator's personal memory excluded by construction — see setup.py's
   privacy ignore).
3. Legacy ``parents[2]`` as the last resort, so a broken install degrades to
   the old (diagnosable) behavior rather than a new one.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

#: A directory is the episteme checkout iff ALL markers exist. Two markers so
#: a stray ``kernel/`` dir in some unrelated ancestor cannot hijack resolution.
_CHECKOUT_MARKERS = ("kernel/CONSTITUTION.md", "core/hooks")


def checkout_root() -> Optional[Path]:
    """The enclosing repo checkout, or ``None`` in an installed context.

    ``EPISTEME_CHECKOUT`` overrides the walk (useful for tests and unusual
    layouts); it must itself carry the markers to be honored — an override
    pointing at a non-checkout is ignored, not trusted.
    """
    override = os.environ.get("EPISTEME_CHECKOUT")
    if override:
        cand = Path(override)
        if all((cand / m).exists() for m in _CHECKOUT_MARKERS):
            return cand.resolve()
    here = Path(__file__).resolve()
    for parent in here.parents:
        if all((parent / m).exists() for m in _CHECKOUT_MARKERS):
            return parent
    return None


def packaged_root() -> Optional[Path]:
    """The wheel-shipped ``_assets`` tree, or ``None`` when absent (dev tree)."""
    cand = Path(__file__).resolve().parent / "_assets"
    if (cand / "core" / "hooks").is_dir():
        return cand
    return None


def asset_root() -> Path:
    """Where ``core/``, ``kernel/``, ``skills/``, ``templates/`` live."""
    root = checkout_root()
    if root is not None:
        return root
    packaged = packaged_root()
    if packaged is not None:
        return packaged
    return Path(__file__).resolve().parents[2]


def is_installed_context() -> bool:
    """True when running from an installed package with no checkout in reach.

    The sync origin guard branches on this: an installed wheel's assets are
    versioned, immutable-by-install content — a legitimate origin class,
    unlike the throwaway-checkout class the guard exists to refuse.
    """
    return checkout_root() is None
