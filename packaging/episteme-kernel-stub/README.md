# episteme-kernel — name-defense stub

This directory is a minimal, ready-to-publish PyPI package whose only job is
to hold the `episteme-kernel` name for the project (PRODUCT_MASTER_PLAN §9.2,
decision (a)+(c), Event 143). Importing it raises `ImportError` with pointers
to the two real install paths — the Claude Code plugin and a source checkout.
`episteme` itself is squatted on PyPI by an unrelated package; this stub keeps
the fallback name available for a future packaged kernel, should real demand
for a pip-native install ever appear (that would be §9.2 option (b), a
separate decision).

It is **not** wired into CI on purpose: publishing claims a public namespace
and cannot be unclaimed, so it is an operator action.

## Publish (operator-run, one time)

```bash
cd packaging/episteme-kernel-stub
python -m build
twine upload dist/*
```

Version stays `0.0.1` until the name ever carries a real package. Do not add
this directory to the wheel/sdist of the main project; it is a sibling
artifact, not a dependency.
