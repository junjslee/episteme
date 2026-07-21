"""Wheel asset bundling (Event 177).

Copies the governance asset trees into ``episteme/_assets/`` at build time so
a pip-installed episteme carries what it governs with — measured before this
event, the wheel shipped ``src/episteme`` only, and every asset consumer
resolved into ``lib/python3.X`` (see ``episteme/_assets.py``).

PRIVACY IS STRUCTURAL HERE, not advisory: ``core/memory/global/`` is the
operator's PERSONAL cognitive profile (gitignored live files). The ignore
below ships its ``examples/`` templates only; a naive ``copytree`` would have
published the operator's private memory in every distributed wheel. The same
ignore drops private skills, runtime ``*.jsonl`` state, caches, and any
key-shaped file, so a leak requires editing THIS file, not forgetting a step.
``tests/test_wheel_assets.py`` pins these exclusions.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

REPO = Path(__file__).resolve().parent

#: Trees shipped into episteme/_assets/ (relative to the repo root).
ASSET_TREES = ("core", "kernel", "skills", "templates")

#: Directory names dropped anywhere in the copy.
_DROP_DIR_NAMES = {"__pycache__", ".git", ".DS_Store", "node_modules"}

#: File suffixes dropped anywhere (runtime state, caches, key material).
_DROP_SUFFIXES = (".pyc", ".jsonl", ".pem", ".key", ".p12")


def asset_ignore(directory: str, names: list) -> set:
    """`shutil.copytree` ignore callable enforcing the shipping contract."""
    directory_path = Path(directory)
    rel = directory_path.relative_to(REPO) if directory_path.is_relative_to(REPO) else directory_path
    ignored = set()
    for name in names:
        if name in _DROP_DIR_NAMES or name.endswith(_DROP_SUFFIXES):
            ignored.add(name)
    # The operator's personal memory: ship the fork-install templates ONLY.
    if str(rel) == "core/memory/global":
        ignored.update(n for n in names if n != "examples")
    # Substrate records are runtime data, not distributable assets.
    if str(rel) == "core/memory":
        ignored.add("substrates")
    # Private skills never ship.
    if str(rel) == "skills":
        ignored.add("private")
    return ignored


class build_py_with_assets(build_py):  # noqa: N801 (setuptools naming)
    def run(self) -> None:
        super().run()
        dest_root = Path(self.build_lib) / "episteme" / "_assets"
        for tree in ASSET_TREES:
            src = REPO / tree
            if not src.is_dir():
                continue
            dest = dest_root / tree
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest, ignore=asset_ignore)
        (dest_root / "README.txt").parent.mkdir(parents=True, exist_ok=True)
        (dest_root / "README.txt").write_text(
            "episteme governance assets, bundled at build time by setup.py.\n"
            "Operator personal memory (core/memory/global live files), private\n"
            "skills, and runtime state are excluded by construction.\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    # Import-safe: tests import this module to pin the ignore contract;
    # build frontends execute it as a script, which takes this branch.
    setup(cmdclass={"build_py": build_py_with_assets})
