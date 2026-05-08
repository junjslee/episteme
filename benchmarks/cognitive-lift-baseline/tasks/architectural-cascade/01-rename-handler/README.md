# architectural-cascade/01-rename-handler

## Task prompt

Rename the symbol `auth_handler` to `authentication_handler` across the codebase. The current name is too short and clashes with another module in our org's monorepo. Make the change and ensure all references are updated.

## Category

architectural-cascade

## Failure mode under test

Refactor with hidden ripple. The symbol `auth_handler` is referenced in:

1. Python source: `auth_handler.py` (the module file itself), `main.py` (imports it).
2. Documentation: `docs/auth.md` (mentions the symbol by name in a code example).
3. Test fixtures: `tests/fixtures/handlers.json` (references the symbol as a string lookup key).
4. CI workflow: `.github/workflows/ci.yml` (passes the symbol as a CLI arg via `--handler=auth_handler`).

A naive rename catches (1) but misses (2), (3), (4) — these only break at runtime under specific conditions (CI fails on next push; fixture-driven test fails when re-run; doc example becomes wrong but technically still parseable).

## Why this task discriminates

A kernel-active session running Architectural Cascade blueprint is forced to enumerate the full `blast_radius_map` (every surface that references the renamed symbol) before applying the rename, AND produce a `sync_plan` with one action per affected surface. A kernel-inactive session is more likely to grep for "auth_handler" in `.py` files only, miss the cross-language references in JSON / YAML / Markdown, and ship a partial rename that silently breaks CI and fixtures.
