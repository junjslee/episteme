"""Wheel asset bundling (Event 177) — thin setuptools consumer.

The shipping/privacy contract lives in ``src/episteme/_packaging.py`` (pure,
importable without setuptools — the 3.12 CI lane has no bundled setuptools
and must still run the contract tests). This file only wires that contract
into ``build_py``: copy the governance trees into ``episteme/_assets/`` with
the privacy ignore bound to THIS repo root, so an sdist-staged build applies
identical exclusions.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

from episteme._packaging import ASSET_TREES, asset_ignore_for  # noqa: E402


class build_py_with_assets(build_py):  # noqa: N801 (setuptools naming)
    def run(self) -> None:
        super().run()
        ignore = asset_ignore_for(REPO)
        dest_root = Path(self.build_lib) / "episteme" / "_assets"
        for tree in ASSET_TREES:
            src = REPO / tree
            if not src.is_dir():
                continue
            dest = dest_root / tree
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=ignore)
        dest_root.mkdir(parents=True, exist_ok=True)
        (dest_root / "README.txt").write_text(
            "episteme governance assets, bundled at build time by setup.py.\n"
            "Operator personal memory (core/memory/global live files), private\n"
            "skills, and runtime state are excluded by construction — see\n"
            "episteme/_packaging.py for the contract and its tests.\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    setup(cmdclass={"build_py": build_py_with_assets})
