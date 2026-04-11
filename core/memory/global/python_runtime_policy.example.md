# Python Runtime Policy

<!-- Personalize: set AGENT_OS_CONDA_ROOT if your Conda is not at ~/miniconda3. -->

- All local Python-backed `agent-os` commands run in Conda `base`.
- Default Conda root: `~/miniconda3`. Override: `export AGENT_OS_CONDA_ROOT=/your/path`.
- Homebrew Python is not the supported runtime for `agent-os`.
- Non-Python tooling (Claude Code, Cursor, Git, `jq`) stays outside Conda.
