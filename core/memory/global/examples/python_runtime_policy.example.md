# Python Runtime Policy

<!-- Personalize: adjust which Python runs `episteme` on this machine. -->

- By default `episteme` uses the Python that invoked it (`sys.executable`). Any reasonable Python (conda, venv, pyenv, system) is accepted.
- To pin a specific Python: `export EPISTEME_PYTHON=/path/to/python` (exact binary) or `export EPISTEME_PYTHON_PREFIX=/path/to/prefix` (install root — the CLI uses `$PREFIX/bin/python`).
- Legacy env vars `EPISTEME_CONDA_ROOT` and `COGNITIVE_OS_CONDA_ROOT` are still honored as fallbacks for machines that previously set them.
- To enforce Conda `base` (and fail `episteme doctor` when it's missing): `export EPISTEME_REQUIRE_CONDA=1`.
- On HPC/remote systems using environment modules, load the desired Python before running `episteme` (e.g. `module load <python-module>`) and add it to your shell rc so it persists.
- Non-Python tooling (Claude Code, Cursor, Git, `jq`) is discovered via `PATH`, not the managed Python.
