# AGENTS.md — episteme

> Operational contract for any AI coding agent working inside this repository.
> Human-facing documentation: [`README.md`](./README.md). Durable
> first-principles: [`kernel/`](./kernel/).

If you have 500 tokens, load [`kernel/SUMMARY.md`](./kernel/SUMMARY.md).
Everything below is the operational contract; it does not replace the kernel.

---

## What this repository is

A portable cognitive kernel for AI agents. The kernel is markdown
(vendor-neutral). Adapters mount the kernel into specific runtimes
(Claude Code, Hermes, future). The kernel defines *how the agent thinks*;
everything else in this repo is delivery plumbing.

**Do not treat this repo as a general-purpose codebase.** It is a
governance + cognition product whose own artifacts are its thesis.

---

## Repository map (what lives where)

```
kernel/          philosophy; markdown; vendor-neutral; the contract
  SUMMARY.md     load first (30-line distillation)
  CONSTITUTION.md    root claim, four principles, six reasoner failure modes
  REASONING_SURFACE.md   Knowns/Unknowns/Assumptions/Disconfirmation
  FAILURE_MODES.md       12 modes ↔ counter artifacts (6 reasoner + 3 governance v0.11 + 2 v1.0 RC + 1 v1.2 RC)
  OPERATOR_PROFILE_SCHEMA.md  how operators encode their worldview
  KERNEL_LIMITS.md       when this kernel is the wrong tool
  ARTIFACT_TAXONOMY.md   four-tier mutation discipline (frozen-purpose · authoritative-living · working-execution · ephemeral)
  PATTERN_GOVERNANCE.md  novel-decision vs mechanical-implementation; pattern-declaration artifact
  MEMORY_ARCHITECTURE.md five memory tiers
  FALSIFIABILITY_CONDITIONS.md  per-claim falsifiability matrix
  CALIBRATION_TELEMETRY.md  Brier score + calibration curve + base-rate-aware measurement surface
  CHAIN_RECOVERY_PROTOCOL.md  legitimate state-loss recovery
  CONTINUITY_PLAN.md     project governance continuity
  DESIGN_BEHAVIOR_INVARIANTS.md  design-behavior verification invariants
  ACTIVE_GUIDANCE_RANKING.md  Pillar 3 active guidance ranking strategy
  MODEL_PROGRESS_RISK_MODEL.md  saturation-vs-positioning threat model
  PHASE_12_LEXICON.md    profile-audit vocabulary
  REFERENCES.md          attribution for every load-bearing borrow
  CHANGELOG.md           versioned kernel history
  HOOKS_MAP.md           kernel invariants ↔ runtime hooks
  README.md              kernel manifest index
  MANIFEST.sha256        kernel integrity digest

demos/           reference deliverables produced by the loop itself
  01_attribution-audit/  canonical four-artifact shape; start here

core/
  memory/global/    operator's personal memory (gitignored; do NOT write)
  hooks/            deterministic safety + workflow hooks
  harnesses/        per-project-type operating environments
  schemas/          memory + evolution contract JSON schemas
  adapters/         adapter target configurations
  agents/           subagent persona definitions

adapters/claude/  Claude Code delivery layer
adapters/hermes/  Hermes (OMO) delivery layer
skills/           reusable operator skills (custom/vendor/private)
templates/        project scaffolds, example answer files
docs/             architecture, contracts, setup guides
src/episteme/    CLI + core library
tests/
```

---

## Build, test, sync

```bash
# Install (idempotent)
pip install -e .

# Verify health
episteme doctor

# Verify kernel integrity
episteme kernel verify   # detects drift in managed files

# Push kernel + profile to all adapters
episteme sync

# Run tests
PYTHONPATH=. pytest -q

# Static check
python3 -m py_compile src/episteme/cli.py
```

Local Python work runs in whichever Python invokes the CLI (`sys.executable`). Pin a specific runtime via `$EPISTEME_PYTHON_PREFIX` (install root) or `$EPISTEME_PYTHON` (exact binary). Set `EPISTEME_REQUIRE_CONDA=1` to enforce Conda `base`.

---

## Kernel invariants (do NOT modify without the Evolution Contract)

1. The four principles in `kernel/CONSTITUTION.md` are load-bearing. Adding, removing, or reframing one requires a major version bump in `kernel/CHANGELOG.md` and a propose → critique → gate → promote loop per `docs/EVOLUTION_CONTRACT.md`.
2. The six-failure-mode taxonomy in `kernel/FAILURE_MODES.md` is a 1:1 mapping. Removing a counter artifact means naming which failure mode is now unprotected. If the answer is "none" — the artifact was not earning its place.
3. The Reasoning Surface is four fields: Knowns, Unknowns, Assumptions, Disconfirmation. Do not rename or collapse them.
4. `kernel/KERNEL_LIMITS.md` declares the kernel's boundary. Claims to universal applicability without updating this file violate Principle I.
5. `kernel/REFERENCES.md` is the attribution contract. Introducing a new load-bearing concept into kernel wording without a primary-source entry violates Principle I.

---

## Workflow convention for non-trivial work

All consequential edits follow the kernel's own loop:

1. **Frame.** State the Core Question in one sentence. Identify the uncomfortable friction driving the work.
2. **Decompose.** Fill the Reasoning Surface (Knowns / Unknowns / Assumptions / Disconfirmation). For high-impact work, provide 2+ options with trade-offs and an explicit because-chain.
3. **Execute.** Prefer smallest reversible action that produces new information. One bounded lane per task owner.
4. **Verify.** Validate against success criteria, not effort. Re-check each assumption. Evaluate hypothesis: validated / refined / invalidated.
5. **Handoff.** Maintainer: a handoff **REPLACES** the private `NEXT_STEPS.md` and **appends exactly one line** to the private `EVENTS.md` history index (see *Commit and handoff conventions*); name residuals explicitly. External contributors: include a Handoff section in the PR description (what shipped, what's left, named residuals) — the maintainer integrates this into the operational record on merge.

High-impact decisions must record to `.episteme/reasoning-surface.json` before the action. See `kernel/HOOKS_MAP.md`.

> **Novel decisions vs. mechanical implementations.** A full Reasoning Surface fires on *novel decisions* — questions still open, alternatives still live. Mechanical implementations of an already-declared pattern produce a minimal `implementation-of` reference instead. See [`kernel/PATTERN_GOVERNANCE.md`](./kernel/PATTERN_GOVERNANCE.md) for the pattern-declaration artifact shape, the promotion gate, and the deviation-from-pattern escape hatch that promotes a "mostly mechanical" change back to novel.

---

## Boundaries

> **Principled basis.** The four sub-lists below are the operational form of the four-tier artifact taxonomy formalized in [`kernel/ARTIFACT_TAXONOMY.md`](./kernel/ARTIFACT_TAXONOMY.md): *frozen-purpose* (no silent mutation; explicit authorization at each change) · *authoritative-living* (mutation expected; rationale required; supersede-with-history) · *working-execution* (standard engineering discipline) · *ephemeral* (untracked-by-design). Read the kernel doc for the failure-mode mechanism (silent mutation of declared contracts to fit drifted generation) the taxonomy counters.

### Do NOT touch

- `core/memory/global/*.md` — operator's personal memory; gitignored; writing to it is an identity violation
- `.claude/settings.local.json` — machine-local overrides; gitignored
- `kernel/MANIFEST.sha256` directly — regenerate with `episteme kernel update` after intentional kernel edits
- Any file matching `**/.env*`, `secrets/*`, private keys

### Handle with care (checkpoint before acting)

- `kernel/*.md` — load-bearing contract; see kernel invariants above
- `docs/MEMORY_CONTRACT.md`, `docs/EVOLUTION_CONTRACT.md` — governance specs
- `core/schemas/*` — versioned JSON schemas; breaking changes require a contract version bump
- Adapters (`adapters/*`, `core/adapters/*.json`) — delivery layer; changes here can silently desync operator profiles across runtimes

### Safe to edit freely

- `docs/*.md` (except the contract files above)
- `skills/custom/*`, `skills/private/*` (see note below — `skills/private/` here means *local-only sync exemption*, not operator-private content)
- `templates/*`
- `tests/*`
- `src/episteme/*` under usual engineering discipline

> **Naming clarification — `skills/private/` is a sync-exemption boundary, not a privacy boundary.** Skills in `skills/private/` are tracked publicly in this repo but are NOT propagated by `episteme sync` to `~/.claude/skills/` (or any other adapter target). Use `skills/private/` for experimental / WIP / project-only skills that should not flow into your global skill library. Operator-private content (lived profile state, operational logs) is privatized via the `~/episteme-private/` symlink mechanism — a different and orthogonal concern.

---

## Prohibited patterns

- **No unattended code-writing-to-merge loops.** Principle IV — the loop needs integrity, not compression past it.
- **No bypassing hooks** with `--no-verify`, `--no-gpg-sign`, or equivalent without explicit user authorization.
- **No `rm -rf`, `git reset --hard`, `git push --force`** without a human checkpoint. `core/hooks/block_dangerous.py` enforces this.
- **No writing to `core/memory/global/`** from any automated flow. It is the operator's first-person memory.
- **No introducing a borrowed concept** into kernel wording without a corresponding `kernel/REFERENCES.md` entry.
- **No claiming universal applicability** for the kernel without updating `kernel/KERNEL_LIMITS.md`.

---

## Git workflow protocol — always-clean-master

> **Why this exists.** Every Event in this repo follows the pattern *branch off master → commit → push → merge back to master.* Three Events in a row (54 / 55-56 / 57) have hit the same recurring failure: `git merge --ff-only <feature-branch>` on local master fails with `Diverging branches can't be fast-forwarded`. Root cause: the chkpt hook (`core/hooks/checkpoint.py`) commits to whatever branch HEAD points at — commonly `master` — which silently diverges local master from origin/master. Once diverged, no fast-forward path exists, and operators fall back to manually opening a PR each time. The fix below holds whether or not the chkpt hook is later fixed at its root.

**Rule.** Use this exact sequence for every Event. Deviation reproduces the divergence.

### Pre-Event (before any work begins)

1. `git fetch origin`
2. Verify clean working tree: `git status` must read `nothing to commit, working tree clean`. If not — commit, stash, or revert before continuing.
3. Sync local master to origin. Order is load-bearing — `git checkout master` MUST happen BEFORE `git pull` (see Footgun A in `### Common footguns` below). Two paths depending on local state:
   - **Local master is clean and merely behind origin** →
     ```bash
     git checkout master                  # FIRST — switch off any feature branch
     git pull --ff-only origin master     # THEN — fast-forward master cleanly
     ```
     Doing these as one chained `&&` is fine, but the order matters: pull operates on the currently-checked-out branch. Running `pull` while still on a feature branch advances the FEATURE BRANCH past its remote-tracking ref and triggers Footgun A later.
   - **Local master has diverged** (chkpt commits or any local-only commits) → operator runs in their own terminal: `cp -R archive /tmp/archive-backup-pre-event` (only if `archive/` has files); `git checkout master`; `git reset --hard origin/master`; `cp -R /tmp/archive-backup-pre-event/. archive/` (restore). The agent **must not** attempt the hard-reset itself — `core/hooks/block_dangerous.py` blocks it; that block is operator policy, respected.
4. Branch off origin/master directly (avoids any leftover local-master state):
   ```bash
   git checkout -b event-NN-shortname origin/master
   ```
5. Begin work.

### During Event

6. All commits land on the feature branch. **Never commit directly to local master.** All work — including small typo fixes — goes through a feature branch.
7. **Never run `git merge` on local master.** Merging happens on origin (via PR) or via post-merge sync (step 11 below), not via local merge.
8. Conventional-commit messages, imperative mood, scoped: `kernel: …`, `docs: …`, `feat(scope): …`, `fix(scope): …`, etc. Checkpoint commits use the Conventional-Commits-valid prefix `chore(chkpt):` (parses as type=chore, release-please-hidden; replaced the bare `chkpt:` that 500'd the release-please parser — CP-RELEASE-PLEASE-CHKPT-FILTER-01).

### Ship Event — pick exactly one path

**Path A · PR-merge (default; preferred when local master may be diverged).**

```bash
git push -u origin event-NN-shortname
gh pr create --title "..." --body "..."     # or via GitHub UI
# Operator merges via GitHub UI or `gh pr merge --merge` (NOT --squash, NOT --rebase)
```

The merge-commit strategy preserves the audit trail matching Pillar 2's append-only ethos. Squash collapses the audit; rebase rewrites it.

**Path B · local fast-forward (only when local master is verified clean and synced AND origin permits direct push to master).**

```bash
git push -u origin event-NN-shortname
git checkout master
git pull --ff-only origin master            # confirm clean ancestor
git merge --ff-only event-NN-shortname
git push origin master
```

If step 3 of Path B fails (any divergence) — abort Path B, switch to Path A. Don't fight the divergence locally; let GitHub handle it.

**Path B caveat — branch protection.** Path B requires origin to permit direct push to master. When master branch protection is enforced (e.g., a `Require a pull request before merging` rule, recommended for any episteme deployment), `git push origin master` returns `GH006: Protected branch update failed for refs/heads/master. Changes must be made through a pull request.` and Path B is impossible. **On `junjslee/episteme`: branch protection IS enforced — Path A only.** Verify protection state on a fresh repo with `gh repo view --json branchProtectionRules,defaultBranchRef`. If branch protection is on, do not even attempt Path B; jump straight to Path A.

### Post-Event sync (BEFORE the next Event begins)

After a PR merges or a local-ff push completes:

9. `git checkout master`
10. `git fetch origin`
11. **Operator runs in their own terminal** (block_dangerous policy): `git reset --hard origin/master`. Restore `/archive/` if needed: `cp -R /tmp/archive-backup-pre-event/. archive/`.
12. Verify: `git log --oneline -5` shows the merge commit at HEAD. `git status` is clean.
13. Optional: delete the local feature branch — `git branch -d event-NN-shortname`. After a PR-merge this `-d` may refuse with `not deleting branch ... not yet merged to refs/remotes/origin/event-NN-...-prep, even though it is merged to HEAD` (Footgun B in `### Common footguns` below). The fix is `git branch -D event-NN-shortname` (force-delete) — safe in this case because the branch's tip commit IS the parent of the merge commit on master; all content is preserved. Optionally also delete the stale remote branch: `git push origin --delete event-NN-shortname`.

### Why this works

- **No local master commits → no divergence class.** The chkpt hook's local-master-commit behavior is sidestepped because operator never sits on master while working.
- **Every Event starts from origin/master directly.** Step 4's `git checkout -b event-NN-shortname origin/master` makes the branch root deterministic, regardless of local-master state.
- **PR-merge always works.** Path A doesn't depend on local-master state at all. Path B is the optimization for the clean case.
- **Post-Event hard-reset re-mirrors local to origin.** Step 11 makes local master a known-clean copy of origin/master, ready for the next Event's step 3.

### Patterns that reproduce the failure (do NOT use)

- Branching off local master without first syncing — inherits any chkpt divergence.
- `git merge --no-ff` on local master after a PR merge already landed — creates a duplicate merge commit that conflicts with origin.
- `git rebase event-NN-shortname onto master` — rewrites already-pushed feature commits.
- `gh pr merge --squash` — collapses the per-commit audit trail. Reserve for backport flows; not the default.

### Long-term root-cause fix (deferred)

The recurring divergence comes from `core/hooks/checkpoint.py` committing to local HEAD. Real fix options for v1.0.1+:

- Have the chkpt hook commit to a dedicated `chkpt/YYYY-MM-DD` branch instead of HEAD, OR
- Have it write to `~/.episteme/state/chkpt-snapshots/` (untracked) instead of git-committing.

Either kills the divergence class entirely. Soak-incompatible right now (touches `core/hooks/`); logged as deferred-discovery for the v1.0.1 cycle. The protocol above holds regardless of when the hook fix lands.

### Common footguns

Two recurring failure modes the protocol above is designed to prevent. Each names the SYMPTOM (so you recognize it in your terminal output) and the FIX. Codified Event 61 after both were observed across Events 56-60.

#### Footgun A · `git pull` on feature branch advances it past remote-tracking ref

**Symptom.** You're on a feature branch (e.g., `event-NN-shortname`). You run `git pull --ff-only origin master` to "sync local master." It says `Updating <SHA>..<SHA>  Fast-forward` and reports the diff stat. **You weren't on master.** The pull just advanced your CURRENT branch (the feature branch) by pulling origin/master into it. Your local feature-branch HEAD is now ahead of `origin/<feature-branch>` (the remote tracking ref). When you later try `git branch -d <feature-branch>`, it refuses with `error: the branch '<feature-branch>' is not fully merged ... If you are sure you want to delete it, run 'git branch -D'`.

**Why it happens.** `git pull` operates on the currently-checked-out branch, regardless of the source argument. `git pull --ff-only origin master` means "fast-forward CURRENT branch by pulling origin/master into it" — not "fast-forward LOCAL master." If your CURRENT branch is `event-NN-shortname`, that's the branch that advances.

**Fix.** Always `git checkout master` BEFORE `git pull`. The Pre-Event step 3 above codifies this order explicitly. If you've already hit Footgun A, the recovery is in Footgun B.

#### Footgun B · Post-PR-merge `git branch -d` refuses with stale-upstream-tracking complaint

**Symptom.** Your PR has merged on origin (verified by `git log --oneline origin/master | head -1` showing the merge commit). You're on local master, synced to origin/master. You run `git branch -d event-NN-shortname` to clean up. Git refuses with:

```
warning: not deleting branch 'event-NN-shortname' that is not yet merged to
         'refs/remotes/origin/event-NN-shortname', even though it is merged to HEAD
error: the branch 'event-NN-shortname' is not fully merged
hint: If you are sure you want to delete it, run 'git branch -D event-NN-shortname'
```

The phrase **"even though it is merged to HEAD"** is the load-bearing tell — git itself confirms the branch IS merged to master.

**Why it happens.** When a PR merges on origin, the source branch on origin (`origin/event-NN-shortname`) is NOT auto-deleted or auto-updated; it stays at whatever SHA was the last push. Your local feature-branch's UPSTREAM tracking ref still points at that stale origin SHA. Meanwhile your local feature-branch HEAD may have advanced (Footgun A) OR stayed where it was — but EITHER way, `git branch -d` checks the local-vs-upstream relationship, sees the upstream is stale, and refuses. It's checking the wrong thing. The branch IS merged to master (via the merge commit on master, whose parent IS the branch's tip).

**Fix.** `git branch -D event-NN-shortname` (force-delete). Safe here because: (a) git itself confirmed `even though it is merged to HEAD`; (b) the branch's tip commit is reachable from master via the merge commit; (c) `-D` only removes the local ref pointer, not the underlying commits. Optionally also delete the stale remote branch:

```bash
git branch -D event-NN-shortname
git push origin --delete event-NN-shortname
```

`-D` is the operator-only command on this repo — `block_dangerous.py` may refuse the agent's attempt depending on its substring rules. Operator runs both lines themselves; ~5 seconds.

**When NOT to use `-D`.** If the branch genuinely has unmerged work (e.g., a feature branch you abandoned mid-Event without merging), `-d` refuses for the right reason. Distinguish Footgun B from a real unmerged-work case by the `even though it is merged to HEAD` line in the warning — that line confirms safety. If git's warning does NOT say `merged to HEAD`, the branch has real unmerged commits and you must decide: merge them or accept the loss.

---

## Release lifecycle (release-please)

Releases are cut by `googleapis/release-please-action@v4` (`.github/workflows/release-please.yml`) driven by `release-please-config.json` + `.release-please-manifest.json`. The versioning contract lives here; the git-merge mechanics that feed it live in `## Git workflow protocol` above.

### rc iteration math (`"versioning": "prerelease"`)

The package config pins `"versioning": "prerelease"` alongside `"prerelease": true` + `"prerelease-type": "rc"`. Under the prerelease strategy (upstream `googleapis/release-please/src/versioning-strategies/prerelease.ts`, `bumpPrerelease()`):

- Last release `1.9.0-rc1`; a releasable commit lands (`feat:` / `fix:` / `perf:` / `deps:` / `revert:` — the non-`hidden` `changelog-sections` types). The strategy sees a prerelease identifier with `patch === 0`, so it increments the trailing prerelease number (zero-padding preserved) and **holds the base**: `1.9.0-rc1` → `1.9.0-rc2` → `1.9.0-rc3`, one bump per release PR merged.
- While an rc is open the commit **type no longer moves the base** — `feat:` vs `fix:` only selects the changelog section; both iterate the same rc counter. The base advances again only after graduation to a stable tag, at which point the next `feat:` opens a fresh cycle.
- **Observed 2026-07-11 (Event 151), correcting an earlier prediction:** the first prerelease of a fresh cycle after a Route-1 stable graduation is the **counter-less `1.10.0-rc`**, not `1.10.0-rc1` as this section previously predicted — release-please appends the bare `prerelease-type` identifier when it bumps a fresh base (no prior rc number to iterate). This is a valid PEP 440 prerelease (normalizes to `1.10.0rc0`) and is harmless; the tag history's uniform `-rc1` came from the pre-Event-146 default-strategy path, not this one. **Pre-committed disconfirmation:** the next releasable commit after `1.10.0-rc` ships must produce `1.10.0-rc1` (the counter iterating, base held). If it instead produces `1.11.0-rc` (base bumping again), the rc-treadmill regressed and the `versioning: prerelease` pin needs re-examination.
- Non-releasable commits (`chore:`, `docs:`, `refactor:`, `test:`, `ci:`, `build:`, `style:`, `chore(chkpt):` — the `hidden` sections) do **not** open a release PR. The strategy change is therefore observable only on the next releasable commit after it merges.

**`versioning` is load-bearing — do not remove it.** `tests/test_release_please_config.py` fails CI if the key is dropped or set to anything but `prerelease`. The JSON schema (upstream `googleapis/release-please/schemas/config.json`) types `versioning` as a bare string with no enum, so a typo would pass schema validation and silently restore the treadmill; the test is the real guard.

### Graduation to a stable GA tag (e.g. `1.9.0`)

Two routes convert the open `1.9.0-rcN` line into the stable `1.9.0` GA. Both are irreversible-once-tagged (a public tag + GitHub Release is a Tier-1 checkpoint per `docs/EVENTS.md` / risk posture) — verify BEFORE merging the release PR.

**Route 1 — `Release-As:` footer (RECOMMENDED; one-shot, deterministic).** `Release-As: x.x.x` bypasses conventional-commit analysis and sets the version verbatim (upstream `googleapis/release-please/README.md`), so it forces exactly `1.9.0` regardless of what accumulated in the commit window — immune to a stray `feat!:` graduating to `2.0.0`. It leaves `prerelease: true` intact, so the next cycle resumes the rc cadence (`1.10.0-rc1`) with no further config change. master is branch-protected (Path A only), so the empty commit lands via a PR, not a direct push:

```bash
git fetch origin
git checkout -b release/graduate-1.9.0 origin/master
git commit --allow-empty -m "chore: release 1.9.0" -m "Release-As: 1.9.0"
git push -u origin release/graduate-1.9.0
gh pr create --title "chore: graduate to 1.9.0 GA" \
  --body "Release-As: 1.9.0 — forces the next release-please proposal to the stable tag, base held."
# Operator merges via GitHub UI or: gh pr merge --merge   (NOT --squash — the footer must survive)
```

The push from that merge triggers a release-please run that opens a release PR proposing `1.9.0`. **Before merging the release PR, verify the proposed version is exactly `1.9.0` with NO `-rc` suffix.** If it shows any `-rc`, the footer was not honored in this action version — STOP, do not merge, fall to Route 2.

**Route 2 — flip `prerelease: false` (ALTERNATIVE; mode change, not one-shot).** Setting `"prerelease": false` in `release-please-config.json` engages the strategy's graduation branch (`if (!this.prerelease)` in `prerelease.ts`): on `1.9.0-rc1` with non-breaking commits it strips the identifier and holds the base → `1.9.0`. Caveats: (i) a pending breaking change (`feat!:` / `BREAKING CHANGE:`) in the window graduates to `2.0.0` instead — audit the window first; (ii) it needs its own config-change PR before the release PR (two PRs); (iii) it is a **mode flip** — after `1.9.0` ships, the next `feat:` produces a STABLE `1.10.0` (no rc). To resume the rc cadence you must flip `prerelease` back to `true`. Use Route 2 only when Route 1's pre-merge check showed an unexpected `-rc`.

**Verify on the resulting GitHub Release (after merging the release PR):**

- Tag name is `episteme-v1.9.0` (`include-v-in-tag: true` + component `episteme`).
- The Release is **NOT** marked "Pre-release". Per upstream `googleapis/release-please/src/manifest.ts`, the prerelease flag on the GitHub Release is `config.prerelease && (version.preRelease || major === 0)`; for `1.9.0` the prerelease identifier is empty and major is `1`, so the box is unchecked even though `config.prerelease` may still be `true`. If the box IS checked, the tag carried a residual `-rc` — investigate before announcing.
- `pyproject.toml`, `kernel/CHANGELOG.md`, and the three `extra-files` (`.claude-plugin/plugin.json` `$.version`, `.claude-plugin/marketplace.json` `$.plugins[0].version` and `$.metadata.version`) all read `1.9.0`.

### Failure mode this closes

Before this config, `prerelease: true` + `prerelease-type: rc` ran under the **default** versioning strategy (no `versioning` key ⇒ default), which strips `-rc`, bumps the BASE per conventional commits, and re-appends `-rc1` every time. Result: **0/11 pipeline releases ever reached a stable tag** — all eleven were `-rc1` (`1.1.0-rc1` .. `1.9.0-rc1`), a `feat:` advanced the minor (`1.9.0-rc1` → `1.10.0-rc1`) instead of the counter, and `-rc2` was structurally unreachable. Pinning `versioning: prerelease` bounds the base within an open rc line so the counter iterates, and makes GA an explicit operator action (Route 1/2) rather than an unreachable state.

---

## Commit and handoff conventions

- Commit messages: imperative mood, scoped (`kernel: …`, `docs: …`, `adapters: …`). Checkpoint commits use the Conventional-Commits-valid prefix `chore(chkpt):`.
- Maintainer workflow — **handoff semantics (compaction discipline, Event 145):** a handoff (1) **REPLACES** the private `NEXT_STEPS.md` (current state · decisions-waiting · next actions · backlog · standing rules) and (2) **appends exactly one line** to the private `EVENTS.md` history index (`| E<N> | date | one-line what | PR/commit/tag refs |`). Appending a "Prior resume" block to `NEXT_STEPS.md` is a protocol violation — the append stack was the accretion disease compaction removed. `PROGRESS.md` is fully retired (tombstone removed E170); its verbatim history lives under `~/episteme-private/docs/archive/`. Do not recreate it. Each handoff carries a Reasoning Surface block and ends with a one-sentence "So-What Now?".
- External contributor workflow: include the Reasoning Surface block + "So-What Now?" inline in the PR description; the maintainer integrates these into the operational record on merge. Contributors do not need to update operational docs themselves.
- Branch naming: `event-NN-shortname` for maintainer-ordered Events (numbering tracked in the maintainer's operational record); `feat/<name>`, `fix/<name>`, `research/<name>`, `ops/<name>`, `docs/<name>` for non-Event work.

---

## Doc classification policy (public vs. private)

Before creating or moving any doc under `docs/`, classify it. The repo splits `docs/` across two visibility tiers; getting the classification right is load-bearing for both competitive position and ecosystem credibility.

**PUBLIC tier (commit to repo):**

- Architecture / spec / contract docs — `DESIGN_V*`, `ARCHITECTURE.md`, `LAYER_MODEL.md`, `EVOLUTION_CONTRACT.md`, `MEMORY_CONTRACT.md`, `SUBSTRATE_BRIDGE.md`. These are the credibility surface; AGPL-3.0 § 13 protects against closed-source extraction.
- Kernel docs (`kernel/*`) — canonical philosophy, reasoning protocol, failure-mode taxonomy, references.
- User references — `HOOKS.md`, `COMMANDS.md`, `SETUP.md`, `CUSTOMIZATION.md`, `DEMOS.md`, `HARNESSES.md`, `SYNC_AND_MEMORY.md`, `SKILLS_AND_PERSONAS.md`, `ANTHROPIC_MANAGED_AGENTS_BRIDGE.md`.
- GTM surface — `README.md` (and translations), `INSTALL.md`, `llms.txt`, `.claude-plugin/README.md`, `OPEN_SOURCE_YOUR_PROFILE.md`.

**PRIVATE tier (symlink to `~/episteme-private/docs/<name>`, gitignore the symlink):**

- Operational state — *"where I am, what I'm doing, what I'm fighting"*: `NEXT_STEPS.md` (REPLACE-on-handoff; carries the active-plan pointer since PLAN.md was retired at Event 168 — it never got tracked), `EVENTS.md` (append-one-line history index), `*_TRIAGE.md`, `*_CALIBRATION.md`. (`PROGRESS.md`'s tombstone was fully removed at Event 170 — its guard condition had already dissolved in the E147/E153 policy rewrites.)
- Operating contract / positioning narrative — *"how I work / how I market"*: `PLAYBOOK.md` (merged operating contract), `POSTURE.md`, `NARRATIVE.md`.
- Historical decision logs (`DECISION_STORY.md`-class once filled with content).
- Anything that documents the operator's *how I work* or *how I market*.

**Default when uncertain: privatize.** Reverting privatization is cheap (republish from private staging); reverting a leak requires `git filter-repo` + force-push + public explanation, with strictly worse optics.

**Classification test.** Could a competitor read this doc and (a) replicate my workflow, (b) anticipate my next move, (c) copy my positioning playbook, (d) find an unfixed weakness to exploit? Any "yes" → PRIVATE.

**Privatize mechanism (4 steps):**

1. `cp docs/<name>.md ~/episteme-private/docs/<name>.md`
2. `diff -q docs/<name>.md ~/episteme-private/docs/<name>.md` (verify byte-identical)
3. `git rm docs/<name>.md`
4. `ln -s ../../episteme-private/docs/<name>.md docs/<name>.md`
5. Append `docs/<name>.md` to `.gitignore` under a dated Event section.

**Cross-ref repair discipline (when privatizing).** Run `git grep -nE '<filename>'` across all tracked files. Repair links in PUBLIC-tier docs (visitor-facing 404s); leave operational/descriptive references that function correctly in user projects (harnesses, skills, agent definitions); never edit `kernel/CHANGELOG.md` historical entries (revisionism).

**For new docs (creation, not move).** Same classification gate before the first write. If the doc would describe operational state, positioning, or strategic decision rationale, create it directly in `~/episteme-private/docs/` and symlink in; do not commit a public version first.

### Canonical-vs-example pattern (operator profiles in `core/memory/global/`)

`core/memory/global/{operator_profile, cognitive_profile, workflow_policy, agent_feedback}.md` follow the SAME privatize-via-symlink pattern as `docs/*.md` above (canonical paths are gitignored symlinks pointing to `~/episteme-private/core/memory/global/<name>.md`). The PUBLIC repo state for these paths is "no tracked file" — and that is intentional.

**Fork-onboarding path:** `core/memory/global/examples/<name>.example.md` ships PUBLIC as the sanitized starting template. Fork users who run `episteme init` get the canonical path seeded from the example template — clean, generic, identity-neutral starting state. Forks then edit their own `core/memory/global/<name>.md` (which is gitignored locally on their machine) to make it theirs.

**Maintainer's lived state:** the operator's actual filled-in profile is at `~/episteme-private/core/memory/global/<name>.md`. The canonical-path symlink in the kernel repo resolves transparently to the private file, so `episteme sync` + `~/.claude/CLAUDE.md` @-imports continue to read the operator's REAL profile during their sessions.

**Why the operator's real profile is NOT shipped publicly as an "example":** the operator's filled-in profile is highly operator-specific (cognitive axes, noise signatures, expertise-map scores) — copying it imports the maintainer's identity, not the user's. The `examples/*.example.md` templates are sanitized + structurally generic + intentionally identity-neutral; they're the right starting point for forks. Shipping the maintainer's REAL profile as a "look, here's a real one" demo creates competitive-intel exposure (cognitive style mappable to decision-making) without onboarding benefit.

**Special case — `agent_feedback.md`.** No `agent_feedback.example.md` ships in `examples/` because agent-learned behavioral rules are PURELY operator-lived — there's no generic template to start from. Forks initialize this file empty (just the section headers) and accumulate their own agent-learned rules over sessions. The kernel's `episteme init` should write a stub with the section structure but no rules.

---

## Scaling by delegation

Subagents live in `core/agents/` and install into `~/.claude/agents/`.

- **Planner** — multi-step sequencing and risk mapping.
- **Researcher** — deep dives into codebases, docs, unknown libraries.
- **Implementer** — focused staged coding once the plan is solid.
- **Reviewer** — cross-referencing implementation against requirements and safety.
- **Orchestrator** — parallel workstream coordination.
- **Structural governance:** domain-architect, reasoning-auditor, governance-safety, domain-owner.

Every delegation begins with a **Shared Context Brief** and ends with a **Verification Artifact**.

---

## When to stop and ask

Stop and surface to the human operator before:

- Editing `kernel/*.md` in any way other than fixing a typo.
- Introducing a new runtime adapter.
- Modifying `core/schemas/*`.
- Any irreversible operation (force-push, hard reset, branch deletion, history rewrite).
- Any change that would require bumping `kernel/CHANGELOG.md` major.

The kernel's Principle IV rule applies to itself: small reversible actions beat large irreversible bets. Asking is cheap. Recovery is not.

---

## Attribution

This file inherits its discipline from the kernel:
- Workflow convention — Deming / Shewhart (PDSA), Boyd (OODA tempo).
- Reasoning Surface — Popper (disconfirmation), Kahneman (WYSIATI counter).
- Boundaries — Principle I (explicit > implicit): what is not named is not governed.

Full sources: [`kernel/REFERENCES.md`](./kernel/REFERENCES.md).
