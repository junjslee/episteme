# Operator Profile

<!-- Personalize: update machine specs, tool stack, and Conda path for your setup. -->

- Primary machine: macOS, Apple Silicon, arm64, zsh.
- This machine is suited for coding, tests, small automation, and light local inference.
- Heavy LLM runs, large training, or long autonomous compute loops should default to remote infrastructure.
- Tool preference:
  - Claude Code for orchestration
  - Cursor for editing and review
  - Codex supported via repo policy and synced skills where useful

## Execution Profiles

### `local`
- Valid use: orchestration, editing, tests, smoke tests, light inference, query exploration
- Not valid for: production model inference, heavy training runs, large data pipelines
- Default profile for all local work unless a remote profile is explicitly chosen

### `remote_gpu`
- Preferred profile for production model-backed runs requiring GPU
- When used, record: backend, model id, device, runtime, artifact outputs, quota constraints
- On HPC clusters: note the cluster name, work filesystem path, and how Python is loaded (Conda module, environment module, etc.)

### `hosted_inference`
- Fallback when remote GPU is not available
- Before using: record provider, model id, cost assumptions, rate limits, retry policy
- Cost acknowledgment required before any paid run (see workflow_policy.md)

## Python Runtime
- By default `episteme` uses the Python that invoked it (`sys.executable`).
- To pin a specific runtime: `export EPISTEME_PYTHON_PREFIX=/path` (install root) or `export EPISTEME_PYTHON=/path/to/python` (exact binary).
- To require Conda `base`: `export EPISTEME_REQUIRE_CONDA=1`.
