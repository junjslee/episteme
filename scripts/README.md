# Scripts

The main `cognitive-os` command lives in the Python package under `src/agent_os/`.

The user entrypoint is:
- `~/.local/bin/cognitive-os`

That wrapper always runs:
- `conda run -n base python -m agent_os.cli ...`

So local Python-backed `cognitive-os` work always executes in Conda `base`.
