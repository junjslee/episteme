# Calibration Notes — Phase 2 Runtime Calibration v1

**Status:** v1 calibration run on 2026-05-08 (Event 117). One A/B pair on `axiomatic-judgment/01-orm-cache-pattern`. **Harness orchestration verified; runtime invocation needs revision before productive Phase 2 runs.**

**Provenance:** Phase 2 first-task calibration per `README.md` § 9 + the runtime-calibration deferred discovery from Event 116. Goal of v1: verify the system runs end-to-end and surface any integration-time gaps that the unit tests (which mocked subprocess) couldn't catch.

---

## What worked

- ✅ **Harness orchestration end-to-end.** `episteme bench run` launches the subprocess, captures wall-clock + returncode + transcript.txt + stderr.txt + final_diff.txt + metadata.json into `runs/<run-id>/`. The structure shipped in Event 116 is correct.
- ✅ **Session B's kernel hooks ARE wired correctly.** The runner's `_configure_session_b` correctly copies the operator's `~/.claude/settings.json` (which has the kernel PreToolUse + SessionStart hook chain pointing at `/Users/junlee/episteme/core/hooks/*.py`) into the per-cwd `.claude/settings.json` of the work dir. The settings shape is what the kernel expects.
- ✅ **Reporter aggregator handles N=0** cleanly — empty rollup table renders without crashing; H1/H2/H3 outcomes report "FAIL — insufficient data" correctly.
- ✅ **Task scaffold structure** (README + grader.json + seed.json + repo-state/) is consumed correctly by the runner.

## What didn't work

### Finding C-1 (BLOCKING): `claude --bare` strips OAuth

Session A's default invocation used `claude --bare --print …`. Per `claude --help`, `--bare` documents:

> Minimal mode: skip hooks, LSP, plugin sync, attribution, auto-memory, background prefetches, keychain reads, and CLAUDE.md auto-discovery. **Anthropic auth is strictly ANTHROPIC_API_KEY or apiKeyHelper via --settings (OAuth and keychain are never read).**

The operator's daily-driver authentication is OAuth (via the macOS keychain). Under `--bare`, that auth is unavailable and the agent fails on the first call:

```
Not logged in · Please run /login
```

Wall-clock 0.86s; returncode 1; nothing produced.

**Implication:** `--bare` is not the right kernel-disable mechanism for Session A in this auth setup. It works only for `ANTHROPIC_API_KEY`-based auth, which would require the operator to provision a separate API key.

### Finding C-2 (DEGRADED OUTPUT): `--max-budget-usd 0.50` too tight

Session B with `claude --print --allow-dangerously-skip-permissions --max-budget-usd 0.50 --debug hooks` ran for 40.2s and exhausted the $0.50 budget before producing useful output. Transcript:

```
Error: Exceeded USD budget (0.5)
```

The agent did consume budget (40s of model + tool work) but the work-in-progress was not captured because `--print` mode appears to write only the final response to stdout, and budget exhaustion overwrites that final response with the error message.

**Implication:** $0.50 is below the floor for any productive session on a real coding task. Phase 2 calibration needs at least $2.00–$5.00 per session.

### Finding C-3 (CAPTURE GAP): `--print` mode is single-shot and silent under failure

`--print` outputs the agent's final response only. Mid-session work — tool calls, file edits, partial reasoning — is not surfaced unless the agent's final response references it. When the session terminates abnormally (budget cap, timeout, error), the partial transcript is lost.

**Implication:** Phase 2 productive runs need `--output-format=stream-json` (and likely `--include-hook-events`) to capture the full agent trajectory — including which tools fired, which hooks the kernel triggered, which files the agent inspected. The grader rubric depends on observing "did the agent open `consumer.py` before removing the regex" type details that `--print` text format hides.

### Finding C-4 (UNKNOWN): Did kernel hooks actually fire in Session B?

`--debug hooks` should have written hook-firing events to either stdout or stderr. Stderr is empty in the captured run. Stdout was overwritten by the budget-exceeded error. So we cannot conclude either way whether the kernel's PreToolUse hooks fired during Session B's 40 seconds of work.

**Implication:** The load-bearing question — *do the kernel hooks fire under `claude --print`?* — is not resolved by v1 calibration. v2 needs `--output-format=stream-json --include-hook-events` to surface hook events as discrete records that survive the budget-exhaust failure mode.

---

## Recommended runner v2 changes

Each of these is a small additive change to `src/episteme/_bench_run.py::_default_claude_command_for_session`. v2 calibration validates them.

### Session A (control) — replace `--bare` with auth-preserving alternative

**Proposal:** drop `--bare`; use `--setting-sources project` instead so claude reads ONLY the per-cwd `.claude/settings.json` (which the runner writes with empty hooks). User-global hooks + plugins are not loaded.

```python
return [
    "claude",
    "--print",
    "--output-format", "stream-json",
    "--include-hook-events",
    "--allow-dangerously-skip-permissions",
    "--max-budget-usd", "2.00",
    "--setting-sources", "project",
]
```

**Calibration question:** does `--setting-sources project` actually disable plugin loading, or do plugins load regardless of settings sources? v2 calibration must verify by checking whether the kernel's known hook signatures (e.g., a SessionStart banner from `session_context.py`) appear in Session A's stream-json output. If they DO appear, plugins are loading despite `--setting-sources project` → need a different mechanism (e.g., temporary HOME override pointing at a stripped-down `~/.claude/`).

### Session B (treatment) — switch to stream-json + bump budget

```python
return [
    "claude",
    "--print",
    "--output-format", "stream-json",
    "--include-hook-events",
    "--allow-dangerously-skip-permissions",
    "--max-budget-usd", "2.00",
]
```

`--include-hook-events` produces explicit hook-fire records in the stream — directly answers Finding C-4. `--max-budget-usd 2.00` is 4× the v1 cap; should be sufficient for most tasks.

### Both sessions — reduce per-task timeout

`--max-budget-usd` is the hard cost ceiling; `timeout` is the time ceiling. Setting both keeps cost AND wall-clock bounded. Default `timeout=1800` (30 min) is generous; `600s` (10 min) is sufficient for most tasks within the $2.00 budget.

### Grader prompt — adapt to stream-json transcripts

The grader prompt template in `_bench_grade.py::GRADER_PROMPT_TEMPLATE` assumes the transcript is human-readable text. Stream-json transcripts are JSON-line records; the grader either needs to (a) be told the format and how to parse it, or (b) the runner pre-processes the stream-json into a human-readable transcript before grading.

Recommendation: option (b) — runner extracts the human-readable agent messages from stream-json and writes them as `transcript.txt`; the raw stream is preserved as `transcript.jsonl` for hook-event inspection.

---

## What this calibration tells the operator

1. **The harness shape is correct.** Modular code architecture, run-directory structure, metadata capture, reporter aggregation — all working. Event 116's Phase 2 implementation is structurally sound.

2. **Two integration-boundary gaps blocked productive v1 runs:** auth (Session A) and budget+capture (both sessions). Both are runner-config issues, not architecture issues. Each fix is single-file additive.

3. **The load-bearing kernel-hook-firing question is still open** but has a clear path to resolution in v2 (stream-json + hook-events).

4. **Phase 2 is not blocked.** The path forward is bounded: ship runner v2, re-run calibration on 1 task, then if v2 succeeds run all 4 tasks (8 sessions × $2 = $16 max budget) for the first methodology-refinement Phase 2 result.

---

## Recommended next move

Pick one:

**A. Ship runner v2 in this conversation** (~30 LOC change to `_bench_run.py` + tests update + re-run calibration). Authorize ~$5 of additional claude budget for v2 calibration on 1 task.

**B. Stop here, document v1 findings, defer runner v2 to a separate Event.** Operator reviews these notes, makes any adjustments to budget / methodology, then authorizes v2 in next session.

**C. Run with anthropic SDK directly** (bypasses the auth-OAuth-vs-API-key issue by going through API key entirely; gives more control over invocation). Bigger change — adds `anthropic` as a dep, rewrites `_bench_run.py` substantially.

**Default proposal: A** — the v2 changes are small, calibration cost is bounded, and we have momentum.

---

## Provenance

- v1 run A: `runs/axiomatic-judgment-01-orm-cache-pattern-A-3488e9fc/` (returncode 1, 0.86s, "Not logged in")
- v1 run B: `runs/axiomatic-judgment-01-orm-cache-pattern-B-b97c5e87/` (returncode 1, 40.24s, "Exceeded USD budget (0.5)")
- Phase 1 spec: `README.md`
- Runner module: `src/episteme/_bench_run.py`
- Grader module: `src/episteme/_bench_grade.py`
- Reporter module: `src/episteme/_bench_report.py`
- Operator decisions locked Event 116: `README.md` § 11

*End of v1 calibration notes. v2 plan + actual v2 calibration run is its own Event after operator authorization.*
