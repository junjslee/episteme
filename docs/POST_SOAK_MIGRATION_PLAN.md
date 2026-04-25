# Post-Soak Migration Plan — Strategic Doc Privatization + Product Protection Strategy

Status: **drafted (executable runbook)** · Drafted 2026-04-25 (Event 58) · Execute window: **AFTER v1.0.0 GA cut** (~2026-04-30 onwards) · Scope: operator-facing migration runbook + product-protection decision matrix.

> **DO NOT EXECUTE DURING SOAK.** This document is drafted during the active v1.0.0-rc1 7-day soak (target close `~2026-04-30 21:23:36Z`). Any execution of the commands below DURING the soak invalidates the soak's claim of stable RC behavior. Operator runs this runbook **after** the v1.0 GA cut completes (Path 2.A in `docs/POST_SOAK_TRIAGE.md` §4) **OR** after the v1.0.1-rc1 cut if Day-7 grading routes to Path 2.B.
>
> **Self-referential note.** This file (`docs/POST_SOAK_MIGRATION_PLAN.md`) appears in the migration list below — when the operator executes Section C, this file moves with the others to the private repo. Until then it lives in the public repo for operator durability (so a local disk failure pre-soak-close doesn't lose the plan).

---

## Why this exists

Earlier this session the operator surfaced a real concern: the public `junjslee/episteme` repo currently contains forward-looking strategic docs — `PLAN.md`, `NEXT_STEPS.md`, `ROADMAP_POST_V1.md`, `DESIGN_V1_1_REASONING_ENGINE.md`, the soak-triage docs — that give competitors a free roadmap. Episteme's own thesis (*reasoning visible on disk*) makes architecture-privatization contradictory; but forward-strategy is operator-business not kernel-identity, and can be privatized without violating the project's core transparency claim.

The agreed split (after rule-shape + tradeoff analysis):

- **Public (project identity, marketing surface, kernel constitutional content):** `README` (all langs), `INSTALL.md`, `AGENTS.md`, `llms.txt`, `LICENSE`, `kernel/**`, `core/**`, `src/**`, `tests/**`, `hooks/**`, `.claude-plugin/**`, `scripts/**`, `web/**`, `demos/**`, `templates/**`, AND any `docs/` file describing what the kernel currently IS or does (`POSTURE`, `NARRATIVE`, `ARCHITECTURE`, `LAYER_MODEL`, `COGNITIVE_SYSTEM_PLAYBOOK`, `DESIGN_V1_0_SEMANTIC_GOVERNANCE`, `MEMORY_CONTRACT`, `EVOLUTION_CONTRACT`, `SUBSTRATE_BRIDGE`, `HOOKS`, `HARNESSES`, `SETUP`, `COMMANDS`, `CUSTOMIZATION`, `SKILLS_AND_PERSONAS`, `DEMOS`, `SYNC_AND_MEMORY`, `ANTHROPIC_MANAGED_AGENTS_BRIDGE`, `OPEN_SOURCE_YOUR_PROFILE`, `CONTRIBUTING`, `DECISION_STORY`, `EPISTEME_ARCHITECTURE`, `PROGRESS` — historical record + trust signal).
- **Private (operator forward-strategy, decay-fast tactical content, not-yet-shipped designs):** `PLAN.md`, `NEXT_STEPS.md`, `ROADMAP_POST_V1.md`, `DESIGN_V1_1_REASONING_ENGINE.md`, `POST_SOAK_TRIAGE.md`, `PREPARED_PATCHES.md`, `DEFERRED_DISCOVERIES_TRIAGE.md`, `DISCRIMINATOR_CALIBRATION.md`, AND this file (`POST_SOAK_MIGRATION_PLAN.md`) once the migration executes.

The mechanism: the private files physically live in a sibling repo at `~/episteme-private/`; the public repo's `docs/` paths become **relative symlinks** pointing into the sibling. Agents read via path (symlinks transparent); git tracks neither the symlink nor the target (gitignored). Strategic content stays operator-private going forward.

---

## Section A · Pre-flight checklist (before running ANY command)

Verify each item before starting Section B. If any fails — **stop and resolve before proceeding**.

```bash
cd ~/episteme

# 1. v1.0 GA cut completed (or v1.0.1-rc1 cut, if routed to Path 2.B)
#    Check: docs/POST_SOAK_TRIAGE.md Phase 4 verdict recorded
#    Check: a v1.0.0 (or v1.0.1-rc1) tag exists
git tag -l | grep -E "v1\.0\.[01]" | sort -V | tail -3

# 2. Master clean and synced to origin
git fetch origin
git status              # must show: "nothing to commit, working tree clean"
[ "$(git rev-parse master)" = "$(git rev-parse origin/master)" ] && echo "synced" || echo "DIVERGED — sync first"

# 3. No active feature branches with uncommitted work
git branch -a           # review; merge or delete stragglers before migration

# 4. Backup the entire public repo (defense in depth)
cd ~
tar -czf ~/episteme-pre-migration-$(date -u +%Y%m%d).tar.gz episteme/
ls -lah ~/episteme-pre-migration-*.tar.gz

# 5. /tmp/archive-backup safety net
[ -d ~/episteme/archive ] && cp -R ~/episteme/archive /tmp/archive-pre-migration

# 6. Path-coupling audit (deferred-discovery from Event 58 surface)
cd ~/episteme
grep -rEn "docs/(PLAN|NEXT_STEPS|ROADMAP_POST_V1|DESIGN_V1_1|POST_SOAK_TRIAGE|PREPARED_PATCHES|DEFERRED_DISCOVERIES_TRIAGE|DISCRIMINATOR_CALIBRATION|POST_SOAK_MIGRATION_PLAN)" tools/ src/ core/hooks/ 2>/dev/null
# If output is non-empty: code paths reference soon-to-be-symlinked files.
# Symlinks WILL resolve transparently for read-only access (Read tool, cat, open).
# But hardcoded write-to-path code may need updating. Audit each hit.
```

If the path-coupling audit (#6) returns hits in `core/hooks/` or `src/episteme/`, **stop and decide per file** whether to: (a) update the code path to take a configurable location, (b) keep the file public despite the strategic-content concern, (c) accept that the symlinked path works for read but not write. Do not skip this step.

---

## Section B · Create the private repo

Operator runs once. Sibling layout — the public repo is at `~/episteme/`, the private repo lands at `~/episteme-private/`.

```bash
cd ~
mkdir episteme-private
cd episteme-private

git init -b master
cat > README.md <<'EOF'
# episteme-private

Strategic forward-planning docs for the public `junjslee/episteme` repo.
Private mirror — accessed by the public repo via relative symlinks at
`~/episteme/docs/<filename>` → `~/episteme-private/<filename>`.

Migrated 2026-XX-XX per `~/episteme/docs/POST_SOAK_MIGRATION_PLAN.md`
(file later moved here by that plan's own execution).
EOF
git add README.md
git commit -m "init: private mirror for episteme strategic docs"
```

Create the private GitHub repo (free tier supports unlimited private repos):

```bash
# Option 1: gh CLI
gh repo create junjslee/episteme-private --private --source=. --remote=origin --push

# Option 2: GitHub web UI — create empty private repo, then:
git remote add origin git@github.com:junjslee/episteme-private.git
git branch -M master
git push -u origin master
```

Verify the private repo is reachable but NOT publicly visible:

```bash
gh repo view junjslee/episteme-private --json visibility    # should print: "PRIVATE"
```

---

## Section C · Migrate the 9 files

Operator runs in `~/episteme/`. Each block is one file — copy, remove from public tracking, symlink, verify. The order is `PROGRESS.md` (the historical record stays public) is **not** in this list — only the 9 strategic files.

The following files migrate together (atomic Event):

1. `docs/PLAN.md`
2. `docs/NEXT_STEPS.md`
3. `docs/ROADMAP_POST_V1.md`
4. `docs/DESIGN_V1_1_REASONING_ENGINE.md`
5. `docs/POST_SOAK_TRIAGE.md`
6. `docs/PREPARED_PATCHES.md`
7. `docs/DEFERRED_DISCOVERIES_TRIAGE.md`
8. `docs/DISCRIMINATOR_CALIBRATION.md`
9. `docs/POST_SOAK_MIGRATION_PLAN.md` (this file — moves with the others)

```bash
cd ~/episteme
git checkout -b event-XX-strategic-docs-privatize origin/master    # use real Event number at time of execution

PRIVATE=~/episteme-private
FILES=(
  docs/PLAN.md
  docs/NEXT_STEPS.md
  docs/ROADMAP_POST_V1.md
  docs/DESIGN_V1_1_REASONING_ENGINE.md
  docs/POST_SOAK_TRIAGE.md
  docs/PREPARED_PATCHES.md
  docs/DEFERRED_DISCOVERIES_TRIAGE.md
  docs/DISCRIMINATOR_CALIBRATION.md
  docs/POST_SOAK_MIGRATION_PLAN.md
)

for f in "${FILES[@]}"; do
  basename=$(basename "$f")

  # 1. Copy real file to private repo
  cp "$f" "$PRIVATE/$basename"

  # 2. Stage removal from public repo (file still in working tree until commit)
  git rm "$f"

  # 3. Replace with relative symlink
  ln -s "../../episteme-private/$basename" "$f"

  # 4. Verify symlink resolves
  cat "$f" > /dev/null && echo "OK: $f resolves to $PRIVATE/$basename" || echo "FAIL: $f"
done
```

Commit the private repo first (so the symlink targets exist):

```bash
cd $PRIVATE
git add -A
git commit -m "migrate: 9 strategic docs from public episteme repo (Event XX)"
git push origin master
cd ~/episteme
```

Update the public repo's `.gitignore` to ignore the symlink paths (so a future `chkpt` hook or `git add -A` doesn't accidentally re-track them):

```bash
cat >> .gitignore <<'EOF'

# ─── Strategic docs migrated to ~/episteme-private/ (Event XX) ───────────────
# These paths are symlinks pointing into the sibling private repo.
# Local agents read them via the symlink; git neither tracks the symlink
# itself nor follows it to the target. See docs/POST_SOAK_MIGRATION_PLAN.md
# (now living in the private repo as part of its own migration).
docs/PLAN.md
docs/NEXT_STEPS.md
docs/ROADMAP_POST_V1.md
docs/DESIGN_V1_1_REASONING_ENGINE.md
docs/POST_SOAK_TRIAGE.md
docs/PREPARED_PATCHES.md
docs/DEFERRED_DISCOVERIES_TRIAGE.md
docs/DISCRIMINATOR_CALIBRATION.md
docs/POST_SOAK_MIGRATION_PLAN.md
EOF
```

Commit the public repo's deletions + gitignore update:

```bash
git add -A
git commit -m "docs(strategy): migrate 9 strategic docs to private mirror (Event XX)"
git push -u origin event-XX-strategic-docs-privatize
gh pr create --title "docs(strategy): privatize forward-planning docs" \
  --body "Moves PLAN/NEXT_STEPS/ROADMAP_POST_V1/DESIGN_V1_1/POST_SOAK_TRIAGE/PREPARED_PATCHES/DEFERRED_DISCOVERIES_TRIAGE/DISCRIMINATOR_CALIBRATION/POST_SOAK_MIGRATION_PLAN to ~/episteme-private/. Public repo's docs/ paths are now symlinks (gitignored). See public history at git log --before=$(date -u +%Y-%m-%d) for archival rationale."
# Operator merges via GitHub UI with --merge strategy (Event-57 protocol Path A)
```

---

## Section D · Update `AGENTS.md` so future agents know about the private mirror

Append a section to `~/episteme/AGENTS.md` (in the same migration commit, OR as a follow-on Event):

```markdown
## Strategic docs live in a sibling private repo

Forward-planning docs were moved to `~/episteme-private/` (private GitHub
mirror) on YYYY-MM-DD per `~/episteme-private/POST_SOAK_MIGRATION_PLAN.md`.
The following paths in this public repo are RELATIVE SYMLINKS, gitignored:

- `docs/PLAN.md`               → `../../episteme-private/PLAN.md`
- `docs/NEXT_STEPS.md`         → `../../episteme-private/NEXT_STEPS.md`
- `docs/ROADMAP_POST_V1.md`    → `../../episteme-private/ROADMAP_POST_V1.md`
- `docs/DESIGN_V1_1_REASONING_ENGINE.md` → `../../episteme-private/DESIGN_V1_1_REASONING_ENGINE.md`
- `docs/POST_SOAK_TRIAGE.md`   → `../../episteme-private/POST_SOAK_TRIAGE.md`
- `docs/PREPARED_PATCHES.md`   → `../../episteme-private/PREPARED_PATCHES.md`
- `docs/DEFERRED_DISCOVERIES_TRIAGE.md` → `../../episteme-private/DEFERRED_DISCOVERIES_TRIAGE.md`
- `docs/DISCRIMINATOR_CALIBRATION.md` → `../../episteme-private/DISCRIMINATOR_CALIBRATION.md`

Agents reading these files via path (Read tool, `cat`, kernel hooks)
follow the symlinks transparently. Agents writing to these paths write
through the symlinks to the private repo. The sibling layout
(`~/episteme/` and `~/episteme-private/`) is required for the relative
symlinks to resolve.

Public repo's `docs/PROGRESS.md` is NOT migrated — historical record +
trust signal stay public.
```

---

## Section E · Verification gates after migration

Run all of these. Any failure stops the migration; rollback per Section F.

```bash
cd ~/episteme

# 1. Symlink resolution — every migrated path must read its content
for f in docs/PLAN.md docs/NEXT_STEPS.md docs/ROADMAP_POST_V1.md \
         docs/DESIGN_V1_1_REASONING_ENGINE.md docs/POST_SOAK_TRIAGE.md \
         docs/PREPARED_PATCHES.md docs/DEFERRED_DISCOVERIES_TRIAGE.md \
         docs/DISCRIMINATOR_CALIBRATION.md; do
  [ -L "$f" ] && [ -r "$f" ] && head -1 "$f" > /dev/null && \
    echo "OK: $f" || echo "FAIL: $f"
done

# 2. Git status must show clean tree (symlinks gitignored)
git status   # nothing to commit; symlinks not appearing as untracked

# 3. episteme doctor — kernel runtime wiring intact
episteme doctor

# 4. episteme kernel verify — manifest integrity
episteme kernel verify

# 5. Test suite passes (one-off — soak is over by now)
PYTHONPATH=. pytest -q | tail -5

# 6. Hook firing on the public repo doesn't leak private content
#    Trigger a synthetic high-impact op and verify the chkpt commit
#    (if any) does NOT contain content from the migrated files.
git log --oneline -5
git show HEAD -- docs/PLAN.md   # should be empty (file no longer in tree)
```

If all six pass: migration successful. The private repo carries forward strategic planning; the public repo carries forward project identity.

---

## Section F · Rollback plan

If verification fails or the operator changes their mind, rollback is straightforward (no force-push, no history rewrite):

```bash
cd ~/episteme

# 1. Drop the migration branch's commit
git checkout master
git branch -D event-XX-strategic-docs-privatize

# 2. Reset public repo to pre-migration state (origin/master untouched if PR not merged)
git fetch origin
git reset --hard origin/master   # operator-only step (block_dangerous policy)

# 3. Verify symlinks gone, real files restored from origin
ls -la docs/PLAN.md   # should show regular file, not symlink
cat docs/PLAN.md      # should show pre-migration content

# 4. Undo gitignore additions
# Manually edit ~/episteme/.gitignore — remove the "Strategic docs migrated..." block

# 5. Optionally archive the private repo (don't delete — operator may revisit)
gh repo edit junjslee/episteme-private --description "ARCHIVED — migration rolled back YYYY-MM-DD"
gh repo archive junjslee/episteme-private
```

If the migration PR was already merged on origin: rollback requires a counter-PR that re-introduces the files (cherry-pick from the pre-migration commit) and removes the gitignore entries. The private repo content stays untouched as a backup.

---

## Section G · Product Protection Strategy

Operator's two questions, answered.

### G.1 · License recommendation

**Operator's stated goal:** *open for individual developers, prevent corporations from cloning and monetizing.*

The license matrix:

| License | Type | Operator-relevant property | Real-world adopters | For episteme |
|---|---|---|---|---|
| **MIT** (current) | Permissive OSS | Anyone can do anything; corps can clone + monetize freely | most of the OSS ecosystem | ❌ no protection — explicitly the case operator wants to leave |
| **Apache-2.0** | Permissive OSS + patent grant | Same as MIT plus patent-retaliation clause | Apache projects, many vendors | ❌ same protection profile as MIT |
| **AGPL-3.0** | Strong copyleft | Network use triggers source-disclosure; if a corp runs episteme as part of an internal service, they must publish the modified source | Grafana, MinIO (pre-AGPL exit), MongoDB (pre-SSPL) | ✅ partial — most corps refuse to AGPL their internal codebases, so it deters integration; OSI-approved (true OSS) |
| **BSL** (Business Source License) | Source-available | Free for non-production use; production use requires a commercial license; converts to OSS license (e.g., Apache) after a fixed time window (typically 4 years) | HashiCorp (Terraform), CockroachDB, Couchbase, Sentry (pre-FSL) | ✅ strong — explicit corp-monetization guard; community-tolerated though not OSI-approved |
| **FSL** (Functional Source License) v1.1 | Source-available | Like BSL but with explicit "non-competing use" exemption — corps can use internally; cannot use to build a competing product; converts to MIT or Apache after 2 years | Sentry (current), Keygen | ✅ best fit — non-competing exemption matches the "individual devs free; competitors restricted" intent precisely |
| **Elastic License v2** | Source-available | Free use except: (a) cannot offer as managed/hosted service, (b) cannot circumvent license, (c) cannot remove license | Elastic, Redis Labs (Redis Stack pre-fork) | ⚠️ targets cloud-resale specifically; episteme isn't primarily a SaaS-resale concern |
| **Commons Clause** + MIT/Apache | License-stack | Restricts "selling" the software; otherwise OSS-permissive | Redis (pre-RSAL), Akka (pre-BSL) | ⚠️ legally messier than purpose-built source-available licenses; community confusion |
| **SSPL** (Server Side Public License) | Aggressive copyleft | Running as a service forces all SaaS dependencies to be open | MongoDB, Elastic (pre-ELv2) | ❌ aggressively rejected by OSS community (Debian, Fedora, AWS); OSI explicitly rejected SSPL as not-open-source |

**Recommendation: FSL (Functional Source License) v1.1 with MIT 2-year future license.** Concrete reasoning:

1. **Non-competing-use exemption matches operator intent.** Individual developers and non-competing companies (anyone not building a *competing cognition-governance kernel for AI agents*) can use, modify, and embed episteme freely under FSL. Companies building competitors must wait the 2-year window before the code converts to MIT.
2. **2-year future-license window strikes the right balance.** Long enough to make near-term commercial cloning unattractive (a competitor would have to build today against 2-year-old episteme); short enough that the project's eventual OSS commitment is real, not theatrical. HashiCorp's BSL uses 4 years; that's longer than necessary for a fast-moving dev-tools space.
3. **Sentry uses FSL for the same business-defensibility reason.** Sentry is the closest comparable positioning to episteme — developer-facing tool, strong monitoring/observability adjacency, explicit anti-competitor framing. Their 2024 switch from BSL to FSL signals FSL is the more refined version of the BSL-class license.
4. **OSI-not-approved is acceptable for episteme's stage.** OSI alignment matters most for projects seeking enterprise/government adoption pipelines that have OSS-compliance procurement gates. Episteme is pre-1.0 with a single maintainer and no enterprise sales motion. The community-trust cost of "source-available, not OSS" is low here.

**Trade-off to be honest about.** Switching from MIT to FSL changes the license forward; everyone who has cloned under MIT keeps MIT for that snapshot. The license-change Event needs an explicit changelog entry naming the date. Some pure-OSS contributors will decline to engage with a non-OSI license — that's a real cost. For episteme's current threat model (corporate cloning + product-integration without licensing), FSL's protection clearly outweighs the contributor-pull cost.

**Implementation when operator chooses FSL:** replace `LICENSE` with the FSL v1.1 text from `https://fsl.software/`; add a clear `LICENSE.notice` explaining the future-MIT conversion; bump `kernel/CHANGELOG.md` MAJOR (license change is governance-class); announce on the public README + a release note.

**If operator prefers a different posture:**

- **Maximum protection (most defensive):** BSL with 4-year window. Discourages every form of commercial cloning more aggressively than FSL but rules out non-competing internal corp use without paid license.
- **Maximum openness with weak protection:** AGPL-3.0. True OSS. Corps technically can monetize but must publish derivatives under AGPL — most won't accept that obligation, so it deters integration.
- **Minimum disruption (status quo):** Keep MIT. Accept that the moat is the user-private chain (each operator's accumulated protocols), not the source code. The architecture-as-public-thesis stance is consistent with MIT.

### G.2 · `git filter-repo` history scrub — recommendation: **DO NOT SCRUB**

The case for scrubbing: removes the historical visibility of `PLAN.md` / `NEXT_STEPS.md` / `DESIGN_V1_1` content from public commits. A determined competitor running `git log -p docs/PLAN.md` post-migration would still see every revision of strategic content prior to the migration.

The case against scrubbing dominates decisively for episteme's specific situation:

| Cost of scrubbing | Detail |
|---|---|
| **Force-push damage** | Rewriting every commit hash invalidates every fork's tracking branch. Anyone who has cloned (estimated < 50 unique clones at this stage but rising) gets a `non-fast-forward` error on next pull. Bad signal — reads as panic / cover-up. |
| **External-reference breakage** | Commit-hash permalinks in old GitHub issues, blog posts, social shares, kernel/CHANGELOG.md cross-references all break. Fixing them requires manual edits across surfaces operator may not control (other people's blog posts). |
| **GitHub indexing residue** | GitHub's own search/cache may retain old content for hours-to-weeks after the force-push. Scrubbing doesn't immediately make content unfindable. |
| **Partial coverage only** | Anyone who cloned BEFORE the scrub keeps the original history forever in their local copy. Scrubbing reduces but does not eliminate strategic-content discoverability. |
| **Trust-signal damage** | A force-push on `master` in a governance-themed project that explicitly markets `tamper-evident` chains is structurally hypocritical — the project would be tampering with its own most authoritative log. |

| Benefit of scrubbing | Detail |
|---|---|
| **Removes one search vector** | A casual `git log -p docs/PLAN.md` no longer surfaces strategic content. Determined adversaries have other vectors (cached clones, web archives, GitHub APIs). |
| **Decay-fast content already self-protects** | This week's `NEXT_STEPS.md` is irrelevant 3 months from now. Strategic content at any one timestamp ages out faster than the cost of scrubbing accrues. |
| **Most useful to true competitors** | A serious competitor who reads PROGRESS.md (which is NOT migrating) gets a clearer engineering retrospective than they would from raw PLAN.md history anyway. The scrub doesn't close the most-useful read. |

**Verdict.** Cost of scrubbing massively outweighs benefit. Leave history alone. Future strategic content goes private at the migration; past public content stays as the trust signal.

**Explicit exception path** (if operator decides to scrub anyway):

```bash
# DO ONLY at v1.0 GA cut, with explicit advance notice
# Pre-scrub: notify any known forkers + post a notice on the repo
git filter-repo --path docs/PLAN.md --path docs/NEXT_STEPS.md \
  --path docs/ROADMAP_POST_V1.md --path docs/DESIGN_V1_1_REASONING_ENGINE.md \
  --path docs/POST_SOAK_TRIAGE.md --path docs/PREPARED_PATCHES.md \
  --path docs/DEFERRED_DISCOVERIES_TRIAGE.md --path docs/DISCRIMINATOR_CALIBRATION.md \
  --invert-paths
git push --force-with-lease origin master

# Post-scrub: explicit changelog entry naming the date and the rationale
# (kernel/CHANGELOG.md major bump — this IS a governance-class operation)
```

If chosen: **schedule the scrub for the same Event as the migration**, not later. Bundling the destructive op with the architecturally-coherent migration commit is more honest than doing it as a separate "spring cleaning" Event whose intent is harder to read.

---

## Section H · Soak invariants (this draft Event)

This Event is **drafting only**; nothing executes during the soak. Specifically:

- ❌ NO `core/hooks/` edits.
- ❌ NO `core/blueprints/` edits.
- ❌ NO `src/episteme/` edits.
- ❌ NO `tests/` edits.
- ❌ NO `kernel/` edits.
- ❌ NO `git filter-repo` execution.
- ❌ NO LICENSE file changes.
- ❌ NO Section C migration commands run.
- ✅ ONE new `docs/POST_SOAK_MIGRATION_PLAN.md` file (this).
- ✅ Event 58 entry in `docs/PROGRESS.md`.
- ✅ Resume-here update in `docs/NEXT_STEPS.md`.

Day-7 grading proceeds unchanged. Soak clock continues from `2026-04-23T21:23:36Z` toward `~2026-04-30 21:23:36Z`. The migration EXECUTES post-soak only — when operator decides per `docs/POST_SOAK_TRIAGE.md` §4 routing.

---

## Section I · References

- `docs/POST_SOAK_TRIAGE.md` — Day-7 gate-grading rubric and Path 2.A / 2.B / 2.C decision rule. Migration triggers on Path 2.A (GA cut) or 2.B (v1.0.1-rc1 cut).
- `AGENTS.md` — `## Git workflow protocol — always-clean-master` (Event 57). The migration follows this protocol's Path A (PR-merge with `--merge` strategy).
- `core/memory/global/agent_feedback.md` — universal-principled rules. The license-change is a `Rule shape — positive vs negative system` decision (FSL is positive: enumerated "non-competing" allowed, default-deny; MIT is negative: enumerated nothing forbidden, default-allow).
- `kernel/CONSTITUTION.md` — root claim. License change is a governance-class operation, requires CHANGELOG MAJOR bump.
- `docs/EVOLUTION_CONTRACT.md` — propose → critique → gate → promote. Migration + license change are the largest single-Event governance ops in the repo's history; a gate-pass on the operator review is required before either executes.
- `https://fsl.software/` — Functional Source License v1.1 reference (FSL).
- `https://mariadb.com/bsl11/` — Business Source License v1.1 reference (BSL).
- `https://www.gnu.org/licenses/agpl-3.0.html` — AGPL-3.0 reference.

---

## Operator decision checklist (resolve before executing)

Answer each before running Section C:

1. **Day-7 routing.** Is Day-7 grading complete? Path 2.A (GA cut) or Path 2.B (v1.0.1-rc1 cut) confirmed? Migration runs in either; do not run during the soak window.
2. **License path.** FSL v1.1 (recommended) · BSL · AGPL-3.0 · keep MIT? Decision affects the LICENSE file edit Event after migration.
3. **History scrub.** Recommended: leave history alone. Operator override possible but strongly advised against. Decision must be made before executing Section C — bundle the scrub with the migration commit if chosen, not later.
4. **Sibling-layout assumption.** Migration assumes `~/episteme/` and `~/episteme-private/` are siblings on the operator's filesystem. Single-machine MacBook-Air-2 usage today is fine; multi-machine usage requires a follow-up plan (path-resolution via env var or git-submodule alternative).
5. **Path-coupling audit.** Section A step 6 — any tool/code that hardcodes a path to one of the 9 migrating files needs a separate decision (read-only is fine via symlink; write needs path update).

Once these five are resolved, Section C is mechanical. Operator runs the commands; migration completes in ~10 minutes.
