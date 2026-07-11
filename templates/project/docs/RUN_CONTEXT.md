<!-- episteme-lifecycle: status=living; reviewed_as_of={{DATE}} -->
# 🛠️ Operational Vessel (Run Context)

## 📡 Machine Metadata
- OS: `{{OS_VERSION}}` (`{{OS_BUILD}}`)
- CPU: `{{CPU}}`
- Memory: `{{MEM_GB}} GB`
- Architecture: `{{ARCH}}`
- Shell: `{{SHELL}}`

## 🗡️ Tooling
- Claude Code: `{{CLAUDE_VERSION}}`
- opencode: `{{OPENCODE_VERSION}}`
- Git: `{{GIT_VERSION}}`

## ⛓️ Execution Constraints (Python Runtime)
- `episteme` local Python work must run in Conda `base`.
- Expected Conda root: `{{CONDA_ROOT}}`
- Homebrew Python is not a supported runtime.

## Practical Local Limits
- This machine is suited for editing, tests, small automation, and light inference.
- Avoid heavy local model inference, long training runs, or large data pipelines unless the machine is provisioned for it.
- Prefer remote GPUs or hosted APIs for heavy workloads.

## External Services and APIs
- Fill in services used by this project.

## Rate Limits and Policies
- Fill in API limits, quotas, budgets, and retry rules.

## Local vs Remote Execution
- Run local editing, tests, documentation, and light automation here.
- Push heavy experiments, training, and GPU-heavy loops to remote infrastructure.

## Project-Specific Notes
- Add repo-specific environment constraints here.
