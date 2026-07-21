<!-- episteme-lifecycle: status=living; reviewed_as_of=E177 -->
# Setup — Profile, Cognition, One-Command

## Install without a checkout (E177 — the distribution path)

A pip-installed wheel is self-contained: it bundles the governance assets
(`core/hooks`, `kernel/`, `skills/`, `templates/` → `episteme/_assets/`,
built by `setup.py`; the maintainer's personal memory is excluded by
construction) and every asset consumer resolves them via
`src/episteme/_assets.py` — repo checkout when present, packaged assets
otherwise. The clean-machine chain is CI-enforced on a fresh macOS runner
(`.github/workflows/ci.yml`, `clean-install` job):

```bash
pip install <episteme wheel>   # from a GitHub release artifact
episteme doctor                # expect 0 warn · 0 fail
episteme sync                  # wires hooks from the installed assets
episteme viewer                # live governance dashboard
```

`episteme sync` from an installed package deploys the governance layer
(hooks, skills, settings) and reports its origin as `installed package`.
Personalized memory for installed users is not wired yet — `episteme init`
refuses in installed context rather than writing into read-only wheel
assets (sync deploys the generic examples layer meanwhile; to personalize
today, clone the repo and run init from the checkout). Developing episteme
itself? A checkout always wins asset resolution — nothing changes for you.

---

Deterministic onboarding for episteme. Two axes:

- **profile** — *how work runs* (planning, testing, docs, automation).
- **cognition** — *how decisions are made* (reasoning depth, challenge style, uncertainty posture).

Treat `survey` / `infer` outputs as a starting point, not doctrine. For long-term quality, author your authoritative philosophy in `core/memory/global/cognitive_profile.md` using a top-down structure (reasoning → agency → adaptation → governance → operating thesis), then sync.

## Modes

- `survey` — explicit questionnaire, 4-level choices mapped to scores 0..3.
- `infer` — deterministic repo-signal scoring (docs / tests / CI / branch patterns / guardrails).
- `hybrid` — weighted merge (`60% survey + 40% infer`, rounded).

`survey` and `hybrid` accept `--answers-file templates/profile_answers.example.json` for non-interactive runs.

## Scored dimensions (all 0..3)

**Workstyle profile:**
`planning_strictness` · `risk_tolerance` · `testing_rigor` · `parallelism_preference` · `documentation_rigor` · `automation_level`.

**Cognitive profile:**
`first_principles_depth` · `exploration_breadth` · `speed_vs_rigor_balance` · `challenge_orientation` · `uncertainty_tolerance` · `autonomy_preference`.

## Commands

```bash
episteme profile survey --answers-file templates/profile_answers.example.json
episteme profile infer .
episteme profile hybrid . --answers-file templates/profile_answers.example.json --write
episteme profile show
```

Generated artifacts land under `core/memory/global/.generated/`:
- `workstyle_profile.json`
- `workstyle_scores.json`
- `workstyle_explanations.md`
- `personalization_blueprint.md` (combined user system profile)

To compile generated scores into global memory files:

```bash
episteme profile hybrid . --write --overwrite
episteme sync
episteme doctor
```

## One-command setup (execution + thinking)

```bash
# Interactive
episteme setup . --interactive

# Non-interactive with explicit post-steps
episteme setup . --write --sync --governance-pack strict --doctor

# Fully scripted (survey/hybrid non-interactive requires answer files)
episteme setup . \
  --profile-mode hybrid \
  --cognition-mode infer \
  --profile-answers-file templates/profile_answers.example.json \
  --cognition-answers-file templates/profile_answers.example.json \
  --write --overwrite --sync --doctor
```

**Defaults.** Non-interactive: `profile-mode=infer`, `cognition-mode=infer`. Interactive: asks whether to use questionnaire onboarding; if yes, both default to `survey`. `write`, `overwrite`, `sync`, `doctor` default to `false` (preview first). `governance-pack=balanced` when `--sync` is enabled.

**Answer-file precedence.**
1. `--profile-answers-file` / `--cognition-answers-file` (most specific)
2. `--answers-file` fallback for both

## Terminal tools (recommended)

Agents running under episteme expect these to be present. `episteme doctor` verifies them.

- `rg` (ripgrep) — codebase search; fast, respects `.gitignore`
- `fd` — file discovery; cleaner than `find`
- `bat` — syntax-highlighted file inspection
- `sd` — safer regex in-place replacements
- `ov` — pager that handles wide output and ANSI cleanly
