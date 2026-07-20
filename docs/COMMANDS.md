<!-- episteme-lifecycle: status=living; reviewed_as_of=E174 -->
# episteme — command reference

A one-page map of every `episteme` subcommand, grouped by lifecycle phase.
Run `episteme <command> --help` for flags and arguments.

Source of truth: the argparse tree in `src/episteme/cli.py` — the
completeness of this page against it is CI-enforced both directions
(`tests/test_commands_doc_drift.py`), and naming the source here puts this
page on the reverse index so CLI edits surface it (`episteme docs map`).

Scope key:
- **global** — targets `~/episteme` or `~/.claude` / `~/.hermes`, ignores CWD
- **project** — takes a path arg (default `.`), acts on the current project
- **framework** — operates on internal episteme state (hash chain, protocols, evolution)

---

## Daily

| Command | Scope | What it does |
|---|---|---|
| `episteme bootstrap [path]` / `new-project [path]` | project | Scaffold `AGENTS.md`, `CLAUDE.md`, `docs/*`, `.claude/settings.json`, `.gitignore` into the given directory. |
| `episteme sync` | global | Propagate kernel memory + governance policies into `~/.claude/` and `~/.hermes/`. Run after editing anything under `~/episteme/core/memory/global/`. |
| `episteme start [claude\|...]` | project | Launch the preferred agent surface in the current project. |
| `episteme doctor` | global | Verify runtime wiring — Conda presence, core CLI tools, optional integrations. |
| `episteme audit` | project | Check whether the current project session addressed its cognitive unknowns. |
| `episteme memory {record,list,search,promote}` | global | Create, list, search memory records; promote stable episodic patterns to semantic-tier proposals. |

## Setup & admin

| Command | Scope | What it does |
|---|---|---|
| `episteme init` | global | One-shot: seed kernel global memory from `core/memory/global/examples/*.example.md`. Only meaningful on a fresh kernel clone. |
| `episteme setup` | global | Interactive wizard that runs profile + cognition surveys end-to-end. |
| `episteme profile {survey,infer,hybrid,gap,show,override,audit}` | global | Manage operator-profile axes (planning strictness, risk tolerance, testing rigor, etc.); `override` sets a per-project axis override (Event 85) and `audit ack <audit-id>` acknowledges a drift verdict (Event 78). |
| `episteme cognition {survey,infer,hybrid,show}` | global | Manage cognitive-style axes (dominant lens, noise signature, abstraction entry, etc.). |
| `episteme update` | global | Pull the latest episteme from git. |
| `episteme list` | global | Show installed agents, skills, plugins, and active hooks. |
| `episteme validate` | global | Check manifest integrity — every declared skill must have a SKILL.md. |

## Project tools

| Command | Scope | What it does |
|---|---|---|
| `episteme detect [path]` | project | Score which harness type fits the project. |
| `episteme harness {list,apply}` | project | List available harnesses; apply one to a project. A harness defines execution profile + workflow constraints for a project type. |
| `episteme worktree` | project | Create a git worktree for a bounded task in the current repo. |
| `episteme viewer` | project | Live local governance dashboard (E174): global operator-home state + current-project surface/doc-map/staleness + the DOC ADVISORY feed, polling every 3s at `localhost:37776`; auto-opens the browser (`--no-open` to suppress). Menu-bar companion: `tools/xbar/episteme.30s.sh`. |
| `episteme capture` | project | Draft a `reasoning-surface.json` skeleton from unstructured text (Slack thread, PR desc, ticket, email). Reads stdin. |

## Framework internals

| Command | Scope | What it does |
|---|---|---|
| `episteme kernel {verify,update}` | framework | Kernel integrity manifest — verify working tree against `kernel/MANIFEST.sha256`, or regenerate it. |
| `episteme chain {verify,reset,upgrade,recover}` | framework | Pillar 2 hash-chain operations over framework + reflective streams. `recover` covers reset / selective / migrate modes (CP-CHAIN-RECOVERY-PROTOCOL-01). |
| `episteme guide [--deferred]` | framework | List synthesized framework protocols and (with `--deferred`) open deferred discoveries. |
| `episteme history {axis,policy,protocol}` | framework | Walk Cognitive Arm A supersede-with-history streams: profile axis trajectories (Event 82), policy section changes (Event 83), synthesized-protocol supersede chains (Event 84). |
| `episteme cognitive-budget {--summary,--check,--record,--list,--tail}` | framework | Inspect operator approval-time observations + D11 fatigue signal (Event 88, Cognitive Arm A). |
| `episteme inject` | framework | Deploy cognitive enforcement to any directory in one command. |
| `episteme log` | framework | Show audit log of reasoning-surface checks (passed / advisory / blocked). |
| `episteme review` | framework | Review sampled Layer 8 spot-check entries (operator verdicts). |
| `episteme evolve {run,report,promote,rollback,friction}` | framework | Run and manage gated self-evolution episodes. |
| `episteme bridge {am,substrate}` | framework | Bridge external runtime event logs into memory-contract envelopes. |
| `episteme private-skill` | framework | Enable or disable a private experimental skill. |
| `episteme surface {author,list,show,chain}` | practice | Author / sign / manage Signed Reasoning Surfaces (operator UX). |
| `episteme evidence {view,packet}` | practice | Auditor-facing viewer + Regulator Evidence Packet exporter. |
| `episteme verify` | practice | Standalone signed-surface verifier (independent of the episteme runtime). |
| `episteme practice {walk,retro,demo}` | practice | Make the practice tangible — walk / retro / demo without authoring a surface. |
| `episteme report` | practice | Quantified value report — surface authoring, failure modes, Tier-1 soak, calibration trend. |
| `episteme status` | runtime | Runtime-state snapshot: surface freshness, branch, rigor, framework counts, profile drift. |
| `episteme deferred {list,resolve}` | framework | List OPEN deferred discoveries (project-scoped; `--all-projects`, `--expired`) or chain an operator verdict. |
| `episteme docs {lint,index}` | docs | Doc-lifecycle marker lint + generated docs index (`--check` gates CI). |
| `episteme check {list,scaffold}` | governance | Manage user-authored PreToolUse checks. |
| `episteme bench {scaffold,run,grade,report}` | evaluation | Empirical-lift benchmark suite: paired-comparison runner + blind LLM grader. |
| `episteme dev watch` | development | Source-to-plugin-cache file watcher for plugin development. |
| `episteme new-project` | scaffold | Interactive wrapper over `bootstrap` for starting a fresh governed project. |
| `episteme verify-examples` | docs | Structural-parity guard: `core/memory/global/examples/*.example.md` stay at v2. |

---

## Quick maps

**Starting from scratch on a new machine:**
```
git clone <episteme> ~/episteme
episteme init            # seed global memory from examples
episteme setup           # profile + cognition wizard
episteme sync            # propagate to ~/.claude / ~/.hermes
episteme doctor          # verify wiring
```

**Starting a new project:**
```
cd ~/my-new-project
episteme bootstrap .     # scaffold docs + settings
# edit docs/REQUIREMENTS.md
episteme start claude    # launch agent surface
```

**After editing your operator profile:**
```
# edit ~/episteme/core/memory/global/operator_profile.md
episteme sync            # propagate changes
```

**Scope rule of thumb.** If a command takes a `[path]` argument, it's project-scoped. If it doesn't, it's almost certainly global.
