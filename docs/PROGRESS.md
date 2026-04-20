# Progress

Running log of completed work. Most recent first.

---

## 0.11.0-entry — 2026-04-20 — Kernel depth pass: attribution surface expansion, operator profile v2, memory architecture contract

Docs-only landing. No code paths touched; hook enforcement and adapter wiring of the new behavior knobs are phases 9–12 of the 0.11.0 plan and remain not-started.

### Attribution surface expansion — `kernel/REFERENCES.md`
- Nine new primary sources added: Ashby (requisite variety → grounds escalate-by-default in hook layer); Gall (working-simple precedes working-complex → grounds evolution posture); Tetlock (calibration culture → grounds telemetry loop target); Laplace/Jaynes (probabilistic inference → grounds evidence-weighted plausibility update); Goodhart / Strathern (measure-as-target drift → grounds scorecard audit discipline); Klein (recognition-primed decision → grounds `tacit_call` + `expertise_map`); Chesterton (the fence → grounds Fence-Check gate); Feynman (self-deception → sharpens Principle I); Festinger (cognitive dissonance → sharpens confidence/accuracy counter).
- Four secondary sources added: Tulving / Squire (memory-tier taxonomy), Snowden (Cynefin domain marker), Wittgenstein (limits of explicit language).
- Primary-source count: 14 → 23. Operational summary at top of REFERENCES.md rewritten.

### Body-doc weaves — no buzzwords, only concepts
- `CONSTITUTION.md` — added variety-match and fence-check lenses to Principle III stack; added "a working complex system evolves from a working simple one" paragraph to Principle IV; added "not a frozen measurement of the operator" caveat to *What it is not*.
- `FAILURE_MODES.md` — new section "Governance-layer failure modes" holding three non-Kahneman modes (constraint removal w/o understanding, measure-as-target drift, controller-variety mismatch) separated from the six primary so the Kahneman taxonomy stays intact. Operational-summary table updated.
- `REASONING_SURFACE.md` — three additions: evidence-weighted update mechanic (Assumption plausibility updates; moves to Known only on decisive evidence), the `domain` marker (Clear/Complicated/Complex/Chaotic — precedes the four fields), the `tacit_call` boolean marker (closes Gap D — relaxes Knowns for judgment-driven calls without relaxing accountability).
- `KERNEL_LIMITS.md` — added limits 7 (rule-based governance against general-capability agents → escalate-by-default) and 8 (scorecard as target → per-axis audit against episodic record; drift is allowed). Operational summary updated.

### Operator profile schema v2 — `kernel/OPERATOR_PROFILE_SCHEMA.md` (rewrite)
- Two scorecard layers now: (a) process axes widened to 0–5 with anchor text per level; (b) new cognitive-style layer — nine typed axes: `dominant_lens`, `noise_signature`, `abstraction_entry`, `decision_cadence`, `explanation_depth`, `feedback_mode`, `uncertainty_tolerance` (0–5), `asymmetry_posture`, `fence_discipline` (0–5).
- Per-axis metadata: `value`, `confidence` (elicited / inferred / default), `last_observed`, `evidence_refs[]`, optional `drift_signal` (0.0–1.0). Replaces the single `Last elicited` file-level line: staleness is now per-axis because axes drift at different rates.
- `expertise_map` field: `{ domain → { level, preferred_mode } }`. Closes the "scaffold an expert" / "go terse on a learner" default failures.
- New section: *Derived behavior knobs* — the declared set of control signals adapters compute from axes (`default_autonomy_class`, `disconfirmation_specificity_min`, `preferred_lens_order`, `noise_watch_set`, `explanation_form`, `checkpoint_frequency`, `scaffold_vs_terse`, `fence_check_strictness`). Bridges "profile is documentation" → "profile is control signal."
- New section: *Audit discipline* — the counter to measure-as-target drift. Scored axes are hypotheses about the operator, not signed contracts; periodically audited against the episodic record; divergence over N cycles flags re-elicitation, never auto-updates.

### Memory architecture — new doc `kernel/MEMORY_ARCHITECTURE.md`
- Five tiers declared with purpose / lifetime / writer / reader:
  1. **Working** — session scratchpad, compresses under context pressure; nothing persists past session end.
  2. **Episodic** — per-decision records (Reasoning Surface + action + observed outcome + Disconfirmation state); 90-day raw + compacted summary afterward. Write triggers declared: high-impact action, hook-blocked or escalated action, Disconfirmation fired (full or partial), operator-elected record.
  3. **Semantic** — cross-session patterns derived from episodic; persistent; pruned on contradicting evidence. Proposes priors to the Frame stage; never autofills the Surface.
  4. **Procedural** — operator-specific reusable action templates, distinct from universal workflow policy and project-local templates.
  5. **Reflective** — memory about memory (staleness, drift signals, elicitation queue). Derivable; materialized view, not source of truth.
- Retrieval contract: query-by-situation (Reasoning Surface shape-match), not query-by-key. Ranking: `similarity × recency_decay × outcome_weight`. No-match is a valid output; spurious priors are more costly than no priors.
- Promotion contract: episodic → semantic requires pattern recurrence + outcome stability; semantic → profile-drift proposal requires long-window conviction + divergence from claimed axis value. Both gated. Profile-drift proposals go into reflective tier for operator review at next SessionStart; the kernel never auto-merges a profile update.
- Forgetting contract: per-tier TTL + compaction rule declared. Two categories never written: secrets (detected at write, rejected) and operator-identifying paths (normalized before write).
- Write/read discipline: each workflow stage has a declared write responsibility and read set. Frame reads profile + semantic priors + recent episodic; Handoff writes the episodic record + updates authoritative docs.
- Integrity guarantees: episodic is append-only (compaction produces new records via `supersedes`/`superseded_by`); promotion is idempotent; forgetting is itself logged in reflective.

### Summary / README updates
- `kernel/SUMMARY.md` — six-modes table expanded to nine (six reasoner + three governance-layer); new Operator-profile-v2 paragraph; new Memory-architecture paragraph; scope boundary updated with limits 7 and 8; *next load* list adds `MEMORY_ARCHITECTURE.md`.
- `kernel/README.md` — file list adds `MEMORY_ARCHITECTURE.md` with a one-line description; `OPERATOR_PROFILE_SCHEMA.md` description updated to reflect v2 structure.

### What did *not* land in this pass (explicit)
- No code changes. Hook layer does not yet read the derived behavior knobs; episodic records are not yet written by the Handoff stage; semantic promotion job does not exist. These are phases 9–12 of the 0.11.0 plan.
- `kernel/MANIFEST.sha256` is stale as of this commit — will be regenerated after all 0.11.0 kernel doc edits settle (phase 14). `episteme doctor` will emit drift warnings until then.
- `kernel/CHANGELOG.md` entry deferred until the implementation phases land (so the changelog reflects both the docs and the wiring). Current `CHANGELOG.md` still reads 0.10.0.
- Version strings in `pyproject.toml` / `plugin.json` / `marketplace.json` unchanged at 0.10.0 — bump pinned to 0.11.0 tag readiness (after phases 9–14).

### Residual architectural gaps — still honest
1. **Intra-call indirection** — unchanged from 0.10.0. Still needs a cross-runtime proxy daemon.
2. **Dynamic shell assembly** (`A=git; B=push; $A $B`) — unchanged.
3. **Heredocs with variable terminators** — unchanged.
4. **Scripts > scan cap** — unchanged.
5. **Governance-layer failure mode 9 (controller-variety mismatch)** is now named and documented; the *enforcement* (escalate-by-default for out-of-coverage action classes) is not built. Presently no-op — the kernel admits the gap and does not silently paper over it.

---

## 0.10.0 — 2026-04-20 — The Sovereign Kernel: stateful interception + heuristic friction analyzer + profile freshness gate

Four atomic commits, 35 new tests, full suite 121 passing, zero regressions. High-level framing: 0.9.0-entry proved telemetry could be paired locally; 0.10.0 carries that same file-on-disk discipline across the execution boundary between Write and Bash — the kernel now remembers what the agent just wrote.

### Stateful interception (Phase 1)
- New `core/hooks/state_tracker.py` — PostToolUse hook on Write/Edit/MultiEdit + Bash. Persists `{path → {sha256, ts, tool, source}}` to `~/.episteme/state/session_context.json`. 24 h rolling TTL, atomic `temp+os.replace`, `fcntl.flock` on a sibling lockfile.
- Tracked inputs: `.sh`, `.bash`, `.zsh`, `.ksh`, `.py`, `.pyw`, `.js`, `.mjs`, `.cjs`, `.ts`, `.rb`, `.pl`, `.php`, plus extension-less files (frequently shell scripts). Bash redirect/tee targets (`>`, `>>`, `| tee [-a]`) also captured.
- `core/hooks/reasoning_surface_guard.py` extended with `_match_agent_written_files`: two match modes — (1) literal file name or abs path in command → scan that file; (2) variable-indirection shape against any recent tracked write → scan every recent entry.
- `hooks/hooks.json` — state_tracker wired to both PostToolUse matchers (Write/Edit/MultiEdit and Bash), async.
- Tests (`tests/test_stateful_interception.py`, 12 cases): tracker records `.sh`/`.py`/`.js`/extension-less writes; skips `.md`; records Bash redirects and `tee`; purges stale entries; deep-scans `run.py` on `python run.py`; catches `bash $F` against recent write; innocuous agent-written files pass; empty state store is a no-op.

### SVG architecture overhaul (Phase 2)
- `docs/assets/architecture_v2.svg` — 1200×780 schematic, three layers (Agent Runtime / Episteme Control Plane / Hardware · OS). Dedicated nodes for Reasoning-Surface Guard, Stateful Interceptor (with the cross-call memory loop), and Calibration Telemetry (with the feedback arrow to the guard). Cybernetic aesthetic — near-black background, cyan/amber/emerald accents, mono typography.
- `README.md` — ASCII box-drawing diagram under "System overview" removed; SVG embedded with a short narrative on PASS / BLOCK, stateful loop, and calibration feed.

### Heuristic friction analyzer (Phase 3)
- New CLI subcommand `episteme evolve friction [--telemetry-dir PATH] [--output PATH] [--top N]`. Scans `~/.episteme/telemetry/*-audit.jsonl`, pairs prediction↔outcome by `correlation_id`, flags `exit_code ≠ 0` against *positive* predictions (predictions with empty envelopes are skipped — not a calibration signal), and emits a Markdown Friction Report ranking most-violated unknowns, friction-prone ops, and recent events.
- Empty telemetry → graceful "No friction detected yet" message. Malformed lines are skipped silently.
- Tests (`tests/test_evolve_friction.py`, 7 cases): empty dir, unknowns ranked by frequency, empty envelope skipped, missing outcome ignored, malformed line survived, `--output` writes file, `--top N` truncates.

### Gap B — `last_elicited` + stale warning (Phase 4a)
- `core/memory/global/operator_profile.md` — added `Last elicited: 2026-04-13` metadata line.
- `_compile_operator_profile` in `src/episteme/cli.py` — emits the line on every profile regenerate.
- `_write_workstyle_artifacts` — mirrors `last_elicited` into both generated JSON artifacts.
- New helpers `_read_last_elicited`, `_profile_staleness`, `_render_stale_profile_warning` (kernel const `PROFILE_STALE_DAYS = 30`).
- `src/episteme/adapters/claude.py` — `render_user_claude_md()` now checks staleness and injects a visible "Stale Context Warning" block above the memory imports when absent or older than 30 days.
- `kernel/OPERATOR_PROFILE_SCHEMA.md` — field documented as required.
- Tests (`tests/test_last_elicited.py`, 16 cases): parser accepts `_italic_`, `bullet`, plain forms; rejects malformed dates; staleness classification (missing / unknown / fresh / stale); warning block content and suppression.

### Final neutrality sweep (Phase 4b)
- `docs/PLAN.md:18`, `docs/PROGRESS.md:10-11` — literal absolute-user-home strings in *descriptions of the prior scrub* replaced with generic `~/...` language. Public `junjslee` GitHub identity retained intentionally (open-source attribution).
- `grep -r /Users/junlee episteme/` now returns zero matches.

### Version bumps + changelog
- `pyproject.toml` 0.8.0 → 0.10.0.
- `.claude-plugin/plugin.json` 0.8.0 → 0.10.0.
- `.claude-plugin/marketplace.json` plugin 0.8.0 → 0.10.0.
- `kernel/CHANGELOG.md` — new 0.10.0 entry + retroactive 0.9.0-entry entry to bring the audit trail in line (the 0.9.0 work had landed without a kernel-changelog bump).

### Residual architectural gaps — honest
1. **Intra-call indirection.** A single Bash call that both writes and executes (`echo "git push" > s.sh && bash s.sh` as *one* tool-use) is caught today only by the existing in-command text scanner. State tracking adds no new coverage because the PostToolUse recorder fires *after* the call. The true fix needs a cross-runtime proxy daemon that can pause between the write and the exec — the 0.11+ Sovereign Kernel. Naming v0.10 "The Sovereign Kernel" is directional, not complete.
2. **Dynamic shell assembly.** `A=git; B=push; $A $B` — unchanged from 0.8.1.
3. **Heredocs with variable terminators.** Redirect parser is regex-based; `cat <<"$EOF" > f` is missed.
4. **Scripts > 256 KB (hash) / > 64 KB (scan).** Unchanged caps.

### Test count
- 86 → **121** passing, 8 subtests. 0 regressions.

---

## 0.9.0-entry — 2026-04-20 — Privacy scrub + calibration telemetry + visual demo + bypass hardening

### Repository neutrality (Phase 1)
- Replaced absolute user-home paths with `~/...` or placeholder equivalents in `docs/PROGRESS.md`, `docs/NEXT_STEPS.md`, `docs/assets/setup-demo.svg`.
- Neutralized operator identifier to `"operator": "default"` in `demos/01_attribution-audit/reasoning-surface.json`.
- `junjslee` GitHub references retained — public identity for the open-source repo.
- `.gitignore` confirmed clean: `.episteme/`, `core/memory/global/*.md` (personal), secrets, and generated profile artifacts all covered. New telemetry writes to `~/.episteme/telemetry/` (outside repo), no gitignore change needed.

### Calibration telemetry (Phase 2 — Gap A closure)
- `core/hooks/reasoning_surface_guard.py` — on allowed Bash (`status == "ok"`), writes a `prediction` record to `~/.episteme/telemetry/YYYY-MM-DD-audit.jsonl` with `correlation_id`, `timestamp`, `command_executed`, `epistemic_prediction` (core_question + disconfirmation + unknowns + hypothesis), `exit_code: null`.
- `core/hooks/calibration_telemetry.py` — new PostToolUse hook; writes the matching `outcome` record with observed `exit_code` and `status`. Correlates via `tool_use_id` first, SHA-1 `(ts-second, cwd, cmd)` fallback when absent.
- `hooks/hooks.json` — new PostToolUse Bash matcher wires `calibration_telemetry.py` (async).
- Telemetry is operator-local, append-only JSONL, never transmitted.

### Visual demo (Phase 3)
- `scripts/demo_strict_mode.sh` — hermetic three-act script: (1) lazy agent writes `disconfirmation: "None"`, (2) `git push` attempt blocked with exit 2 + stderr shown, (3) valid surface rewritten, retry passes. Narrated via `sleep` for asciinema cadence (overridable with `DEMO_PAUSE`).
- `docs/CONTRIBUTING.md` — recording workflow documented (`brew install asciinema agg`, `asciinema rec -c ./scripts/demo_strict_mode.sh`, `agg` to render GIF, size/cadence targets).
- `README.md` — placeholder `![Episteme Strict Mode Block](docs/assets/strict_mode_demo.gif)` embedded above the "I want to…" table. GIF asset itself produced in a separate maintainer pass.

### Bypass-vector hardening (Phase 4 — best-effort)
- `_NORMALIZE_SEPARATORS` now includes backticks — catches `` `git push` `` command substitution.
- `INDIRECTION_BASH` list added; blocks `eval $VAR` / `eval "$VAR"`. Literal-string `eval "echo hi"` still passes (no `$` trigger).
- `_match_script_execution` — resolves scripts referenced by `./x.sh`, `bash x.sh`, `sh x.sh`, `zsh x.sh`, `source x.sh`, `. x.sh`; reads up to 64 KB; scans content with the same pattern set as inline commands. Missing / unreadable scripts pass through (FP-averse).
- Label format: `"<inner label> via <script path>"` — e.g., `"git push via deploy.sh"` — so the block message carries the provenance.

### Test coverage
- `tests/test_reasoning_surface_guard.py` — +10 cases: backtick substitution, eval-of-variable (two shapes), eval-of-literal (pass), script-scan blocks (bash/`.sh`, `./script.sh`, `source`), benign-script pass-through, missing-script pass-through, allowed-Bash telemetry write, blocked-Bash telemetry suppression.
- `tests/test_calibration_telemetry.py` — new file, 7 cases: non-Bash ignored, success outcome recorded, failure outcome recorded, missing exit_code → null, `returncode` fallback honored, empty command skipped, malformed payload never raises.
- Full suite: **86 passed** (was 68), 8 subtests passed, 0 regressions.

### Residual gaps (deferred, logged to NEXT_STEPS.md)
- **Write-then-execute across two tool calls** remains uncatchable by a stateless hook. Candidate for cross-runtime MCP proxy daemon (0.10+).
- **Dynamic shell assembly** (`A=git; B=push; $A $B`) still evades detection. Would require a lightweight shell parser. Deferred pending cost/benefit evidence.
- **Strict Mode demo GIF** — the asset file itself is one `asciinema rec` away; README placeholder is in place.

---

## 0.8.1 — 2026-04-20 — Strict-by-default enforcement + semantic validator + bypass-resistant matching

### Hook behavior changes (`core/hooks/reasoning_surface_guard.py`)
- **Default inverted**: missing / stale / incomplete / lazy Reasoning Surface now exits 2 and blocks the tool call. Previously advisory; hard-block required `.episteme/strict-surface`.
- **Opt-out mechanism**: per-project advisory mode via `.episteme/advisory-surface` marker. Legacy `.episteme/strict-surface` is now a no-op (strict is default).
- **Semantic validator added** to `_surface_missing_fields`:
  - Min lengths: `MIN_DISCONFIRMATION_LEN = 15`, `MIN_UNKNOWN_LEN = 15`
  - Lazy-token blocklist: `none`, `null`, `nil`, `nothing`, `undefined`, `n/a`, `na`, `not applicable`, `tbd`, `todo`, `unknown`, `idk`, `해당 없음`, `해당없음`, `없음`, `모름`, `해당 사항 없음`, `-`, `--`, `---`, `—`, `...`, `?`, `pending`, `later`, `maybe`
  - Case-insensitive + whitespace-collapsed + trailing-punctuation-trimmed matching
- **Bypass resistance** via `_normalize_command`: `[,'"\[\]\(\)\{\}]` → space before regex match. Caught in tests: `subprocess.run(['git','push'])`, `os.system('git push')`, `sh -c 'npm publish'`.
- **Block message upgraded**: stderr leads with `"Execution blocked by Episteme Strict Mode. Missing or invalid Reasoning Surface."` + concrete validator reasons + advisory-mode opt-out pointer.
- **Audit entry** `mode` field replaces the old `strict` bool.

### CLI (`src/episteme/cli.py`)
- `_inject` rewritten: strict (default) creates no marker and removes any pre-existing `advisory-surface`; `--no-strict` writes `.episteme/advisory-surface` explicitly.
- Template unknowns placeholder updated to reflect the ≥ 15 char rule.
- Post-inject hint text lists lazy-token rejection explicitly.

### Tests (`tests/test_reasoning_surface_guard.py`)
- Rewritten from 9 advisory-flavored cases → 17 cases covering:
  - Strict-by-default on every failure mode (missing / stale / incomplete / lockfile)
  - Advisory-marker downgrade path
  - Legacy `strict-surface` marker no-op behavior
  - Lazy-token rejection: 8 subtest values (`none`, `N/A`, `TBD`, `해당 없음`, `없음`, `null`, `-`, `nothing`)
  - Short-string rejection (disconfirmation and unknowns)
  - Bypass vectors: subprocess list form, `os.system`, `sh -c` wrapping

### Docs
- `kernel/CHANGELOG.md` — 0.8.1 entry added
- `kernel/HOOKS_MAP.md` — enforcement row + state-file description rewritten to match new default
- `README.md` — lede paragraph rewritten: no more "advisory by default" hedge; now explicitly states block-by-default, the validator contract, and the advisory opt-out pointer
- `docs/PLAN.md`, `docs/NEXT_STEPS.md` — strict-by-default and validator items moved to Closed

### Verification
- `PYTHONPATH=. pytest tests/ -v` → **68 passed**, 8 subtests passed (17 in the guard suite, 51 pre-existing elsewhere — zero regressions)
- Hook tested end-to-end via the suite: block exit code 2, advisory-mode exit 0, normalized bypass shapes caught, lazy tokens rejected

### Architectural gaps surfaced (not fixed, logged to `NEXT_STEPS.md`)
- **Shell script files calling high-impact ops** are not caught (e.g., `./deploy.sh` that internally runs `git push`). Intercepting requires script-content reading — out of scope for this patch.
- **Write-then-execute patterns** (write a script to disk, then run it) are not caught without a stateful hook. Requires cross-call state, which is out of scope.
- **Bash variable indirection** (`CMD="git push" && $CMD`) is not caught; normalization handles quote/bracket separators but not variable substitution.

---

## 0.8.0 — 2026-04-19 — Core migration: cognitive-os → episteme

### Version alignment (0.8.0 follow-on)
- `pyproject.toml` version: `0.2.0` → `0.8.0` (was stale across 0.6.0/0.7.0/0.8.0 cycles)
- `.claude-plugin/plugin.json` version: `0.6.0` → `0.8.0`
- `.claude-plugin/marketplace.json` plugin version: `0.6.0` → `0.8.0`
- `pip install -e .` re-run so the registered `episteme` console script reports 0.8.0
- `git tag v0.8.0 && git push --tags` — migration tagged and pushed

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

### Environment completion (completed in-session)
- GitHub repo renamed via `gh repo rename` → `github.com/junjslee/episteme` (old URL 301-redirects)
- Local `origin` remote updated; all in-repo URLs now point at the new canonical URL
- Physical repo directory renamed `~/cognitive-os` → `~/episteme`
- Pip: `pip uninstall cognitive-os` → `pip install -e .` (registers `episteme` console script)
- `~/.claude/settings.json` hook command paths rewritten to `~/episteme/core/hooks/*`
- `~/.zshrc` aliases and hint function renamed (`ainit`, `awt`, `cci`, `aci`, `adoctor`, `aos`)
- `episteme sync` regenerated `~/.claude/CLAUDE.md` with new `@~/episteme/...` includes

### Dynamic Python runtime (0.8.0 follow-on)
- `CONDA_ROOT` hardcoded to `~/miniconda3` → `PYTHON_PREFIX` derived from `sys.prefix`
- New env vars: `EPISTEME_PYTHON_PREFIX`, `EPISTEME_PYTHON`, `EPISTEME_REQUIRE_CONDA`
- Legacy `EPISTEME_CONDA_ROOT` / `COGNITIVE_OS_CONDA_ROOT` still honored as fallbacks
- `episteme doctor` skips conda checks on non-conda runtimes unless `EPISTEME_REQUIRE_CONDA=1`

### Temporary compatibility shim
- Symlink `~/cognitive-os → ~/episteme` created to keep the current shell session's cwd valid. Remove with `rm ~/cognitive-os` after restarting any shells/editors that had the old path cached.

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
