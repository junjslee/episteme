# Examples — User-Authored Checks

Small, copy-and-paste-able Python checks you can drop into `~/.claude/settings.json` to extend Claude Code's `PreToolUse` enforcement layer. They are NOT part of the live episteme gate — they are **reference material** that demonstrates the same hook-protocol contract `core/hooks/*.py` uses, exposed at a contribution-friendly threshold.

If you can write 30 lines of Python, you can write a check.

---

## What a check is

A check is a Python script that:

1. **Reads JSON from stdin.** Claude Code's PreToolUse hook posts a JSON payload describing the tool call about to fire (tool name + tool input).
2. **Inspects whatever it cares about.** The proposed command, the proposed file path, the current Reasoning Surface on disk, the operator profile — anything available on the filesystem or inferable from the payload.
3. **Returns a verdict via exit code + stderr.**
   - `exit 0` — allow the tool call (silently or with an advisory message on stderr).
   - `exit 2` — block the tool call (stderr message is shown back to the agent).

That is the entire contract. There is no registration step, no schema file, no plugin manifest.

---

## The PreToolUse JSON shape

```json
{
  "tool_name": "Bash" | "Edit" | "Write" | "MultiEdit" | ...,
  "tool_input": {
    /* shape varies by tool */
    "command": "git push --force",            // Bash
    "file_path": "/abs/path/to/file.py",      // Edit / Write / MultiEdit
    "old_string": "...", "new_string": "...", // Edit
    "content": "..."                          // Write
  },
  "session_id": "<opaque>",
  "transcript_path": "<opaque>"
}
```

Always use defensive `.get()` — fields are optional and the shape evolves.

---

## Verdict semantics

| Goal | Exit code | Where to write the message |
| --- | --- | --- |
| Allow silently | `0` | no output |
| Allow with advisory note | `0` | stderr — the agent sees it; the call still proceeds |
| Block with reason | `2` | stderr — the agent sees the reason; the call is refused |

`exit 1` means *"the check itself errored"* — Claude Code treats that as soft-fail (call proceeds; warning logged). Don't return 1 deliberately.

---

## How to wire one in

Add to `~/.claude/settings.json` (or a project-local `.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "python3 /abs/path/to/examples/checks/block_rmrf.py" }
        ]
      }
    ]
  }
}
```

`matcher` is a regex over tool names. Common patterns: `"Bash"`, `"Edit|Write|MultiEdit"`, `"Bash|Edit|Write|MultiEdit"`.

Multiple checks can ride the same matcher; they fire in order, and the first non-zero exit wins.

---

## The three example checks

| File | What it does | Verdict shape |
| --- | --- | --- |
| [`block_rmrf.py`](./block_rmrf.py) | Refuses `rm -rf` and a small set of related destructive shell shapes at PreToolUse on Bash. The minimum-viable check — about 30 lines including header. Mirrors the Pi video's [rmrf-blocker example](https://www.youtube.com/watch?v=PzqRRYHHpbw) at the same conceptual size. | block |
| [`require_disconfirmation_for_irreversible.py`](./require_disconfirmation_for_irreversible.py) | Reads `.episteme/reasoning-surface.json` from the current working directory and refuses irreversible Bash ops (`terraform apply`, `npm publish`, `gh release create`, force-push, etc.) if the surface lacks a non-empty `disconfirmation` field. Connects user checks to episteme's actual gate semantics. | block |
| [`flag_kernel_edits.py`](./flag_kernel_edits.py) | Advisory only — emits a warning on Edit/Write into `kernel/`, `core/blueprints/`, `core/hooks/`, `templates/`, `labs/` paths reminding the operator that those surfaces are soak-protected and should usually fire a Fence Reconstruction blueprint first. Demonstrates the advisory-not-block pattern. | advise |

---

## Rules of taste

These are not enforced by the check contract — they are the customs that keep checks useful rather than friction:

1. **Single responsibility.** One check, one named failure mode it counters. If you find yourself OR-ing two unrelated patterns, write two checks.
2. **Explicit names in messages.** When blocking, name the rule that fired and the constraint it protects ("Blocked: kernel/ edit without Fence Reconstruction surface"). The agent and the operator are both reading the message; both should be able to act on it.
3. **Conservative on ambiguity.** If your pattern can't decide, prefer `exit 0` over `exit 2`. False-allows are recoverable; false-blocks frustrate the operator and erode the gate's authority.
4. **No I/O beyond stdin / stderr / a small filesystem read.** Don't make network calls, don't fork subprocesses, don't write to disk. Hook latency budget is tight (< 100ms p95 across the whole chain).
5. **Don't import episteme internals.** Examples here are stand-alone `python3` scripts using only the standard library. That keeps the contribution threshold low and prevents accidental coupling to soak-protected internal modules.

---

## What this is NOT

- These checks are **not** part of the live episteme gate. The kernel's authoritative checks live in `core/hooks/*.py` and are wired via `hooks/hooks.json`. Those follow stricter rules (kernel tone discipline, operator-profile awareness, blueprint compliance) and are soak-protected.
- These checks do **not** replace the Reasoning Surface. They are a low-threshold complement — a way to script local, project-specific rules without touching the kernel.
- These checks do **not** auto-load. You opt in by editing your `.claude/settings.json`. That is intentional: the gate's authority comes from the operator choosing what enforces what.

---

## Authoring a new check

Use the scaffolder:

```
episteme check new <name>                    # block-pattern check (default)
episteme check new <name> --type=advisory    # advisory-not-block
episteme check new <name> --type=surface     # reads .episteme/reasoning-surface.json
episteme check new <name> --output=<path>    # custom destination
episteme check new <name> --force            # overwrite existing
episteme check new --list-templates          # show all template shapes
```

The scaffolder writes to `examples/checks/<name>.py` by default. Each generated file is a complete, syntactically-valid Python script you can wire into `~/.claude/settings.json` immediately. The TODO comments in the generated file mark the one-line edits you'll need to make (regex / path prefix / blueprint field) to specialize the check.

If you'd rather start from a working example: copy any of the three examples in this directory, rename it, edit the pattern.

---

## Provenance

Introduced in Event 109 / Tier 2.1 of the post-pi.dev-comparison work. The check contract here is the same one `core/hooks/block_dangerous.py` already implements — the examples vendor it at a contribution-friendly size so external authors can extend the enforcement layer without reading the full kernel corpus first.
