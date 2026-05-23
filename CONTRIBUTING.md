# Contributing

The full contributing guide lives at **[`docs/CONTRIBUTING.md`](./docs/CONTRIBUTING.md)**.

Short version, so you don't have to click through if you're scanning:

1. Read [`AGENTS.md`](./AGENTS.md) (operational contract) and
   [`kernel/SUMMARY.md`](./kernel/SUMMARY.md) (30-line kernel
   distillation) first. The kernel is a contract — changes to it
   follow [`docs/EVOLUTION_CONTRACT.md`](./docs/EVOLUTION_CONTRACT.md).
2. Work in a branch — `feat/<name>`, `fix/<name>`, `docs/<name>`.
3. `PYTHONPATH=. pytest -q` must pass before you ask for review
   (currently 1170 tests, 54 subtests).
4. Include narrative context in the PR description for substantive
   changes — what changed, why, expected impact. The maintainer
   handles the private operational docs (`docs/PLAN.md` etc.); you
   don't need to update those.
5. By contributing, you agree your contribution is licensed under
   [AGPL-3.0-or-later](./LICENSE) (the project's license).

See [`docs/CONTRIBUTING.md`](./docs/CONTRIBUTING.md) for the recurring
maintainer tasks (hero demo recording, etc.) and the full picture.

For conduct in issues/PRs/discussions, see
[`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md).

For reporting a security issue, see [`SECURITY.md`](./SECURITY.md).
