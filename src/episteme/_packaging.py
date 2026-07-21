"""The wheel's asset-shipping contract — pure logic, no setuptools (E177).

Split from setup.py because Python 3.12 venvs no longer bundle setuptools:
importing the contract for TESTING must not require the build backend (the
3.12 CI lane failed collection on exactly that). setup.py consumes these;
tests/test_wheel_assets.py pins them; neither needs the other's runtime.

PRIVACY IS STRUCTURAL HERE: ``core/memory/global`` is the operator's
personal cognitive profile — only its ``examples/`` templates ship. Private
skills, runtime ``*.jsonl`` state, caches, and key-shaped files are dropped
wherever they appear. A leak requires editing THIS file, not forgetting a
step.
"""

from __future__ import annotations

from pathlib import Path

#: Trees shipped into episteme/_assets/ (relative to the repo root).
ASSET_TREES = ("core", "kernel", "skills", "templates")

#: Directory names dropped anywhere in the copy.
DROP_DIR_NAMES = {"__pycache__", ".git", ".DS_Store", "node_modules"}

#: File suffixes dropped anywhere (runtime state, caches, key material).
DROP_SUFFIXES = (".pyc", ".jsonl", ".pem", ".key", ".p12")


def asset_ignore_for(repo_root: Path):
    """`shutil.copytree` ignore callable bound to ``repo_root``.

    Binding the root explicitly (instead of assuming the copy source lives
    under this file's repo) keeps the privacy rules correct no matter where
    the build frontend stages the tree — an sdist temp dir must get the same
    exclusions as an in-repo build.
    """
    repo_root = Path(repo_root).resolve()

    def _ignore(directory: str, names: list) -> set:
        directory_path = Path(directory).resolve()
        try:
            rel = str(directory_path.relative_to(repo_root))
        except ValueError:
            rel = ""
        ignored = set()
        for name in names:
            if name in DROP_DIR_NAMES or name.endswith(DROP_SUFFIXES):
                ignored.add(name)
        # The operator's personal memory: ship the fork-install templates ONLY.
        if rel == "core/memory/global":
            ignored.update(n for n in names if n != "examples")
        # Substrate records are runtime data, not distributable assets.
        if rel == "core/memory":
            ignored.add("substrates")
        # Private skills never ship.
        if rel == "skills":
            ignored.add("private")
        return ignored

    return _ignore
