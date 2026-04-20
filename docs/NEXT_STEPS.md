# Next Steps

Exact next actions, in priority order. Update this file at every handoff.

---

## Immediate (0.10.0 remainder → 0.10.0 GA)

1. **Record the Strict Mode demo GIF** — first maintainer to run it produces `docs/assets/strict_mode_demo.gif` and `.cast`. Instructions in [`docs/CONTRIBUTING.md`](./CONTRIBUTING.md#recording-the-strict-mode-demo). Keep it a quick demo — a few beats of block → fix → pass, readable on GitHub without zoom.
2. **First friction-report pass** — after ~1 week of real v0.10.0 use, run `episteme evolve friction` against accumulated telemetry. Answer: do the ranked unknowns point at real calibration debt? Are the friction-prone ops the same ones humans are already suspicious of? Tune the heuristic (currently: skip empty envelopes; rank by raw frequency) if the top-N doesn't track intuition.
3. **Stateful-interception FP audit** — scan `~/.episteme/audit.jsonl` for blocks carrying the new `via agent-written <path>` label. Any false positive here is a regression-budget hit; surface them fast.
4. **Tag and push `v0.10.0`** after one-week soak if no FP spike and no telemetry anomalies.

## Short-term

- `tacit-call` decision marker in Reasoning Surface schema (Gap D).
- Cynefin domain classification field in `reasoning-surface.json` (companion to `kernel/KERNEL_LIMITS.md` addition).
- **Auto-refinement of `CONSTITUTION.md` from the friction report.** The heuristic already names which unknowns are chronically under-elaborated; wire a `--apply` flag that proposes a CONSTITUTION.md diff, gated by human review — never auto-merged.

## Medium-term (roadmap)

- Multi-operator mode design (Gap C) — deferred past 0.10.0; requires profile schema rework.
- **Cross-runtime MCP proxy daemon — the next real Sovereign Kernel step.** v0.10.0 gives the kernel *memory* across calls. The cross-runtime daemon gives the kernel *mediation* at the syscall boundary: pause execution between the write and the exec, inspect every subprocess fork, and refuse to return control to the agent until the contract is satisfied. This is what closes intra-call indirection (see below). Blocked on telemetry-informed demand evidence from v0.10.0.

## Architectural bypass vectors — remaining open after v0.10.0

v0.10.0 closed write-then-execute *across tool calls* (state tracker + deep-scan) and variable-indirection (`bash $F` against any recent tracked write). These remain:

1. **Intra-call write-then-execute.** `echo "git push" > s.sh && bash s.sh` as a single Bash tool call is caught today only by the in-command text scanner — state tracking fires PostToolUse, after the write has landed. Fix needs a cross-runtime proxy daemon. Targeted at 0.11+.
2. **Dynamic shell assembly.** `A=git; B=push; $A $B` — unchanged from 0.8.1. Would require a lightweight shell parser, or a deny-by-default policy on `$()`/backticks (legitimate automation break). Deferred pending cost/benefit review.
3. **Heredocs with variable terminators.** The v0.10-α redirect parser is regex-based and misses `cat <<"$EOF" > f`. A shell-parser dependency is the fix; weighed against its cost.
4. **Scripts > 64 KB (scan) / > 256 KB (hash).** Unchanged caps. Raising them increases hook latency and creates a DoS surface on pathologically large files. Accepted until a real FN is reported.

---

## Closed in 0.10.0

- **Stateful interception.** Cross-call memory shipped. `core/hooks/state_tracker.py` persists agent-written file paths + sha256 + ts to `~/.episteme/state/session_context.json` (24 h TTL). `reasoning_surface_guard.py` consults the store at execute time, deep-scanning recently-written files referenced by name OR by variable-indirection shape (`bash $F`).
- **Heuristic friction analyzer.** `episteme evolve friction` pairs prediction↔outcome telemetry by `correlation_id`, flags `exit_code ≠ 0` despite positive predictions, ranks most-violated unknowns and friction-prone ops, emits a Markdown Friction Report. Seed for automated CONSTITUTION.md refinement.
- **SVG control-plane diagram.** `docs/assets/architecture_v2.svg` replaces the ASCII diagram in `README.md`. Three-layer schematic; Stateful Interceptor loop and Calibration Telemetry feed visible.
- **Gap B — `last_elicited`.** Required metadata on `operator_profile.md`, mirrored to generated JSON; `episteme sync` injects a stale-context warning block when absent or >30 days old. Schema doc updated.
- **Final neutrality sweep.** No literal absolute-user-home strings remain in any committed doc.
- **Version reconcile** — `pyproject.toml`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` all at 0.10.0.
- Tests 86 → 121. 0 regressions.

## Closed in 0.9.0-entry
- **Repository is neutral.** Personal filesystem paths and operator identifiers removed from docs and demo artifacts. Public GitHub identity (`junjslee`) retained intentionally.
- **Calibration telemetry shipped (Gap A).** Prediction + outcome JSONL records in `~/.episteme/telemetry/YYYY-MM-DD-audit.jsonl`, joined by `correlation_id`. Local-only. Never transmitted.
- **Backtick substitution closed.** `` `git push` `` now normalizes the same way as `"git push"` and trips the pattern set.
- **`eval $VAR` blocked.** `eval "$CMD"`, `eval $CMD` block with label `"eval with variable indirection"`. Literal `eval "echo hi"` still passes.
- **Shell-script execution scanned.** Hook resolves and reads `.sh` files referenced by `./x.sh`, `bash x.sh`, `sh x.sh`, `zsh x.sh`, `source x.sh`, `. x.sh` and scans up to 64 KB for high-impact patterns. Missing scripts pass through (FP-averse).
- **Visual demo harness.** `scripts/demo_strict_mode.sh` is reproducible and recording-ready. `docs/CONTRIBUTING.md` documents the `asciinema rec → agg` flow.
- **Test coverage 17 → 35 guard/telemetry cases** (full suite 86 passed, 0 regressions).

## Closed in 0.8.1
- **Strict mode is default.** Missing / stale / incomplete / lazy Reasoning Surface → exit 2 (block). Opt out per-project via `.episteme/advisory-surface`.
- **Semantic validator shipped.** Lazy-token blocklist + 15-char minimums on `disconfirmation` and each `unknowns` entry. `"disconfirmation": "None"` and `"해당 없음"` no longer pass.
- **Command normalization closes three bypass shapes.** `subprocess.run(['git','push'])`, `os.system('git push')`, `sh -c 'npm publish'` all trip the same regex patterns as bare shell.
- **Block-mode stderr upgraded.** `"Execution blocked by Episteme Strict Mode. Missing or invalid Reasoning Surface."` + concrete validator reasons + advisory-mode opt-out pointer.
- **`episteme inject` reworked.** Default is no-marker (strict is default); `--no-strict` writes `advisory-surface` explicitly.

## Closed in 0.8.0
- Remove compat symlink `~/cognitive-os`
- Verify `/plugin marketplace add junjslee/episteme` resolves (user confirmed in-session)
- Tag + push `v0.8.0`
- Reconcile `pyproject.toml`, `plugin.json`, `marketplace.json` versions
- Add `kernel/CHANGELOG.md` 0.8.0 entry
