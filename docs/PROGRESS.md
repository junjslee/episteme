# Progress

Running log of completed work. Most recent first.

---

## 0.8.0 — 2026-04-19 — Core migration: cognitive-os → episteme

### Python package
- `git mv src/cognitive_os → src/episteme` (history preserved)
- All internal imports updated: `from cognitive_os` → `from episteme`
- `pyproject.toml`: `name`, `description`, `[project.scripts]` entry (`episteme = "episteme.cli:main"`)
- Env vars: `COGNITIVE_OS_CONDA_ROOT` → `EPISTEME_CONDA_ROOT` (+ `_LEGACY` variant)

### Plugin & tooling
- `.claude-plugin/marketplace.json` + `plugin.json` display names updated; `source.url` and `homepage` retained (GitHub repo path unchanged)
- `.github/` issue templates, PR template, CI workflow updated
- `core/adapters/*.json`, `core/harnesses/*.json` string refs updated
- `core/hooks/*.py` log/message strings updated
- `kernel/MANIFEST.sha256` regenerated against new content
- `.git/hooks/pre-commit` updated (imports `episteme.cli`, reads `EPISTEME_CONDA_ROOT` with `COGNITIVE_OS_CONDA_ROOT` fallback)

### Documentation
- README, AGENTS, INSTALL, all `docs/*` and `kernel/*` narrative + CLI examples updated
- Runtime directory convention: `.cognitive-os/` → `.episteme/`
- Schema identifier: `cognitive-os/reasoning-surface@1` → `episteme/reasoning-surface@1`

### Templates & labs
- Only CLI command literals updated; epistemic kernel rules, schemas, and structural logic untouched

### Verification
- `PYTHONPATH=src:. pytest -q` → 60 passed
- `py_compile` across `src/episteme/` and `core/hooks/` → clean
- Pre-commit validate hook → all kernel, agents, skills pass
- `pip install -e .` metadata resolves: `episteme = "episteme.cli:main"`

### Known consequences (user must action)
- `cognitive-os` console script is gone; reinstall via `pip install -e .` to register `episteme`
- Shell env var `COGNITIVE_OS_CONDA_ROOT` should be renamed to `EPISTEME_CONDA_ROOT` in `~/.zshrc`

---

## 0.7.0 — 2026-04-19

### Real enforcement pass
- `core/hooks/reasoning_surface_guard.py` — added `_write_audit()` writing structured entries to `~/.episteme/audit.jsonl` on every check (passed / advisory / blocked)
- `src/episteme/cli.py` — added `_inject()`, `_surface_log()`, parser registration, and dispatch for `inject` and `log` commands
- `.claude-plugin/plugin.json` — version bumped to 0.6.0
- `kernel/CHANGELOG.md` — 0.7.0 entry added
- Verified: `episteme inject /tmp` creates strict-surface + template; hook fires real exit-2 block; `episteme log` shows timestamped audit entries

## 0.6.0 — 2026-04-19

### Gap closure (second pass)
- `kernel/CONSTITUTION.md` — added DbC contract paragraph to Principle I; added feedforward control paragraph to Principle IV; added feedforward + DbC bullets to "What this generates"
- `kernel/FAILURE_MODES.md` — added feedforward framing to intro; renamed review checklist to "pre-execution checklist" to make the feedforward intent explicit
- `.github/ISSUE_TEMPLATE/bug.yml` — added "Kernel alignment" field mapping bugs to failure modes and kernel layers
- `.github/PULL_REQUEST_TEMPLATE.md` — added "Kernel impact" checklist block
- `README.md` — replaced TODO comment with ASCII control-plane architecture diagram
- `docs/PLAN.md`, `docs/PROGRESS.md`, `docs/NEXT_STEPS.md` — created (ops docs were absent; hook advisory fired on every kernel edit)

### Initial pass
- `.claude-plugin/marketplace.json` — fixed `source: "."` → `"https://github.com/junjslee/episteme"` (schema fix; unverified against live validator)
- `src/episteme/viewer/index.html` — removed (deprecated UI artifact)
- `.github/ISSUE_TEMPLATE/feature.yml` — added "Epistemic alignment" field; improved acceptance criteria template
- `README.md` — added governance/control-plane opening paragraph; feedforward + DbC + OPA framing in "Why this architecture"; "Zero-trust execution" section with OWASP counter-mapping table; "Human prompt debugging" section; interoperability statement; ASCII control-plane diagram
- `kernel/KERNEL_LIMITS.md` — added Cynefin problem-domain classification table
- `kernel/CHANGELOG.md` — added [0.6.0] entry
