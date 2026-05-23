"""Tests for the tiered irreversible-op classifier.

Covers the three-tier classification across:
- Tier 3 denylist hits (force-push, hard reset, branch delete, history
  rewrite, destructive SQL, catastrophic shell).
- Tier 1 allowlist hits (feature-branch push, prerelease, gh issue ops,
  pip install).
- Tier 2 default (anything in HIGH_IMPACT_BASH that didn't qualify for
  Tier 1 / 3).
- Edge cases: protected-branch resolution via explicit args vs.
  current-branch fallback; normalization of bypass shapes; dangerous-flag
  escalation; config-driven Tier 1 toggles.
"""
from __future__ import annotations

import json

import pytest

from datetime import datetime, timedelta, timezone

from core.practice.irreversible_tier import (
    GitContext,
    MICRO_SURFACE_DISCONFIRMATION_MIN_LEN,
    MICRO_SURFACE_RATIONALE_MIN_LEN,
    MICRO_SURFACE_TTL_SECONDS,
    OperatorProfile,
    SOAK_GATE_MIN_OPS,
    SOAK_GATE_MIN_DAYS,
    SOAK_GATE_MIN_RATIONALE_ACCURACY,
    Tier,
    classify,
    load_protected_branches,
    normalize_command,
    soak_gate_open,
    validate_micro_surface,
    write_tier1_record,
)


# ---------------------------------------------------------------------------
# Test fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def feature_branch_ctx() -> GitContext:
    return GitContext(
        current_branch="event-134-tier-gate",
        protected_branches=frozenset({"main", "master"}),
    )


@pytest.fixture
def main_branch_ctx() -> GitContext:
    return GitContext(
        current_branch="main",
        protected_branches=frozenset({"main", "master"}),
    )


@pytest.fixture
def detached_head_ctx() -> GitContext:
    return GitContext(
        current_branch=None,
        protected_branches=frozenset({"main", "master"}),
    )


# ---------------------------------------------------------------------------
# Tier 3 — denylist.
# ---------------------------------------------------------------------------


class TestTier3Denylist:
    def test_force_push_to_main_is_tier_3(self, main_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git push --force origin main"},
            main_branch_ctx,
        )
        assert verdict.tier == Tier.THREE
        assert "force" in verdict.reason.lower()

    def test_force_push_short_flag_to_main_is_tier_3(self, main_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git push -f origin main"},
            main_branch_ctx,
        )
        assert verdict.tier == Tier.THREE

    def test_force_with_lease_to_main_is_still_tier_3(self, main_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git push --force-with-lease origin main"},
            main_branch_ctx,
        )
        assert verdict.tier == Tier.THREE, (
            "lease narrows the race window but rewrite intent is unchanged"
        )

    def test_force_push_to_feature_branch_falls_to_tier_2(self, feature_branch_ctx):
        # Force-push to a feature branch is not Tier 3 (no shared history
        # to destroy), but it's still not Tier 1 — full surface required.
        verdict = classify(
            "Bash",
            {"command": "git push --force origin event-134-tier-gate"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_hard_reset_on_main_is_tier_3(self, main_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git reset --hard HEAD~5"},
            main_branch_ctx,
        )
        assert verdict.tier == Tier.THREE

    def test_hard_reset_on_feature_branch_is_tier_2(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git reset --hard HEAD~5"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_branch_delete_dash_capital_d_on_main_is_tier_3(self, main_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git branch -D main"},
            main_branch_ctx,
        )
        assert verdict.tier == Tier.THREE

    def test_filter_branch_is_always_tier_3(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git filter-branch --tree-filter 'rm -f .secret' HEAD"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.THREE
        assert "filter-branch" in verdict.pattern

    def test_filter_repo_is_always_tier_3(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git filter-repo --invert-paths --path .env"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.THREE

    def test_rebase_root_is_always_tier_3(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git rebase --root -i"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.THREE

    def test_drop_database_is_tier_3(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "psql -c 'DROP DATABASE prod;'"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.THREE

    def test_rm_rf_root_is_tier_3(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "rm -rf /"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.THREE

    def test_rm_rf_home_is_tier_3(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "rm -rf $HOME"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.THREE


# ---------------------------------------------------------------------------
# Tier 1 — allowlist.
# ---------------------------------------------------------------------------


class TestTier1Allowlist:
    def test_push_to_feature_branch_explicit_is_tier_1(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git push origin event-134-tier-gate"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.ONE
        assert "git push" in verdict.pattern

    def test_push_to_main_explicit_is_tier_2(self, main_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git push origin main"},
            main_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_push_to_master_explicit_is_tier_2(self, main_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git push origin master"},
            main_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_bare_git_push_on_feature_branch_is_tier_1(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git push"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.ONE

    def test_bare_git_push_on_main_branch_is_tier_2(self, main_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git push"},
            main_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_push_u_head_on_feature_is_tier_1(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "git push -u origin HEAD"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.ONE

    def test_detached_head_push_falls_to_tier_2(self, detached_head_ctx):
        # Cannot confirm bounded blast radius without knowing target —
        # safe-fail to Tier 2.
        verdict = classify(
            "Bash",
            {"command": "git push"},
            detached_head_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_gh_release_with_prerelease_is_tier_1(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {
                "command": (
                    "gh release create v1.4.0-rc1 "
                    "--prerelease --notes 'Release candidate'"
                )
            },
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.ONE

    def test_gh_release_short_prerelease_flag_is_tier_1(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "gh release create v1.4.0 -p"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.ONE

    def test_gh_release_without_prerelease_is_tier_2(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "gh release create v1.4.0 --notes 'GA'"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_gh_issue_create_is_tier_1(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "gh issue create --title 'Bug' --body 'Repro: ...'"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.ONE

    def test_gh_pr_create_is_tier_1(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "gh pr create --title 'feat: tiered gate' --body '...'"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.ONE

    def test_gh_pr_comment_is_tier_1(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "gh pr comment 84 --body 'LGTM'"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.ONE

    # Event 134.1 operator resolution: pip install was REMOVED from the
    # Tier 1 allowlist. Rationale: supply-chain attack class (typosquatting,
    # malicious setup.py / install-phase macros) can exfiltrate env vars
    # and keys from disk before any code runs, even though `pip uninstall`
    # is technically a rollback. Blast radius is not strictly bounded.
    def test_pip_install_is_tier_2(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "pip install requests"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO
        assert "pip install" in verdict.pattern


# ---------------------------------------------------------------------------
# Tier 2 — default fallthrough.
# ---------------------------------------------------------------------------


class TestTier2Default:
    def test_npm_publish_is_tier_2(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "npm publish"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_terraform_apply_is_tier_2(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "terraform apply -auto-approve"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_kubectl_delete_is_tier_2(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "kubectl delete deployment api"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_gh_pr_merge_is_tier_2(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "gh pr merge 84 --merge"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_alembic_upgrade_is_tier_2(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "alembic upgrade head"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_truncate_table_is_tier_2(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "psql -c 'TRUNCATE TABLE users;'"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_drop_table_is_tier_2(self, feature_branch_ctx):
        # DROP TABLE is Tier 2 (recoverable from backup); DROP DATABASE
        # is Tier 3.
        verdict = classify(
            "Bash",
            {"command": "psql -c 'DROP TABLE staging.tmp;'"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO

    def test_unknown_command_is_tier_2(self, feature_branch_ctx):
        # ls is not in HIGH_IMPACT_BASH — out of scope for this gate.
        # Classifier returns Tier 2 with empty pattern to signal "no
        # match." The hook ignores Tier 2 verdicts with empty patterns;
        # only matched-but-Tier-2 ops trigger the strict-block path.
        verdict = classify(
            "Bash",
            {"command": "ls -la"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO
        assert verdict.pattern == ""

    def test_non_bash_tool_returns_tier_2_no_pattern(self, feature_branch_ctx):
        verdict = classify(
            "Read",
            {"file_path": "/etc/hosts"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO
        assert verdict.pattern == ""


# ---------------------------------------------------------------------------
# Normalization — bypass shapes route to the same classification.
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_subprocess_run_list_form_normalizes(self, feature_branch_ctx):
        # Bypass shape from `core/hooks/reasoning_surface_guard.py` docstring.
        verdict = classify(
            "Bash",
            {
                "command": (
                    "python -c \"subprocess.run(['git','push','--force',"
                    "'origin','main'])\""
                )
            },
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.THREE, (
            "subprocess.run list-form bypass must route to the same "
            "classification as bare `git push --force origin main`"
        )

    def test_backtick_form_normalizes(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "eval `git push --force origin main`"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.THREE

    def test_os_system_form_normalizes(self, feature_branch_ctx):
        verdict = classify(
            "Bash",
            {"command": "python -c 'os.system(\"git push --force origin main\")'"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.THREE

    def test_normalize_command_strips_separators(self):
        result = normalize_command("subprocess.run(['git','push'])")
        # Commas, brackets, and quotes become spaces; the regex-word-boundary
        # pattern then matches `git push` as if it were bare shell.
        assert "git" in result
        assert "push" in result
        # No stray quoting / bracketing left.
        assert "'" not in result
        assert "[" not in result


# ---------------------------------------------------------------------------
# Protected-branches loader.
# ---------------------------------------------------------------------------


class TestProtectedBranchesLoader:
    def test_default_when_no_config(self, tmp_path):
        result = load_protected_branches(tmp_path)
        assert result == frozenset({"main", "master"})

    def test_loads_custom_list(self, tmp_path):
        config_dir = tmp_path / ".episteme"
        config_dir.mkdir()
        config_file = config_dir / "protected_branches.json"
        config_file.write_text(json.dumps(["main", "release", "stable"]))

        result = load_protected_branches(tmp_path)
        assert result == frozenset({"main", "release", "stable"})

    def test_malformed_json_falls_back_to_default(self, tmp_path):
        config_dir = tmp_path / ".episteme"
        config_dir.mkdir()
        config_file = config_dir / "protected_branches.json"
        config_file.write_text("not valid json {{{")

        result = load_protected_branches(tmp_path)
        assert result == frozenset({"main", "master"})

    def test_empty_list_falls_back_to_default(self, tmp_path):
        config_dir = tmp_path / ".episteme"
        config_dir.mkdir()
        config_file = config_dir / "protected_branches.json"
        config_file.write_text(json.dumps([]))

        result = load_protected_branches(tmp_path)
        assert result == frozenset({"main", "master"})

    def test_non_list_json_falls_back_to_default(self, tmp_path):
        config_dir = tmp_path / ".episteme"
        config_dir.mkdir()
        config_file = config_dir / "protected_branches.json"
        config_file.write_text(json.dumps({"main": True}))

        result = load_protected_branches(tmp_path)
        assert result == frozenset({"main", "master"})

    def test_custom_protected_list_changes_classification(self):
        # If 'develop' is protected, pushing to it should be Tier 2 not Tier 1.
        ctx = GitContext(
            current_branch="develop",
            protected_branches=frozenset({"main", "master", "develop"}),
        )
        verdict = classify("Bash", {"command": "git push origin develop"}, ctx)
        assert verdict.tier == Tier.TWO


# ---------------------------------------------------------------------------
# Precedence — Tier 3 wins over Tier 1.
# ---------------------------------------------------------------------------


class TestTierPrecedence:
    def test_tier_3_takes_priority_over_tier_1(self, feature_branch_ctx):
        # `git push --force origin <feature-branch>` matches both Tier-3
        # force-push pattern AND Tier-1 git-push pattern. Tier 3 wins.
        verdict = classify(
            "Bash",
            {"command": "git push --force origin event-134-tier-gate"},
            feature_branch_ctx,
        )
        # Tier 3 force-push has `requires_protected=True`, so non-protected
        # target downgrades to Tier 2 (not Tier 1, because dangerous flag
        # disqualifies Tier 1 too).
        assert verdict.tier == Tier.TWO
        assert "force" in verdict.pattern.lower()

    def test_dangerous_flag_blocks_tier_1_even_on_feature_branch(
        self, feature_branch_ctx
    ):
        # --no-verify is a dangerous flag — predicate must reject Tier 1.
        verdict = classify(
            "Bash",
            {"command": "git push --no-verify origin event-134-tier-gate"},
            feature_branch_ctx,
        )
        assert verdict.tier == Tier.TWO


# ---------------------------------------------------------------------------
# Event 134.1 — Micro-surface validator with branch-binding.
# ---------------------------------------------------------------------------


def _fresh_surface(
    branch: str = "event-134-tier-gate",
    rationale: str = "feature-branch push — no protected impact; revert via gh pr close + branch delete",
    disconfirmation: str = "if pytest CI on the PR fails, close PR without merging",
    timestamp: str | None = None,
) -> dict:
    """Helper producing a well-formed micro-surface for branch
    `event-134-tier-gate`. Tests mutate one field at a time to exercise
    each validator gate independently."""
    return {
        "tier": 1,
        "branch": branch,
        "rationale_one_line": rationale,
        "disconfirmation_one_line": disconfirmation,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }


class TestMicroSurfaceValidator:
    def test_well_formed_surface_passes(self, feature_branch_ctx):
        ok, reason = validate_micro_surface(_fresh_surface(), feature_branch_ctx)
        assert ok, reason
        assert reason == "ok"

    def test_tier_must_equal_1(self, feature_branch_ctx):
        surface = _fresh_surface()
        surface["tier"] = 2
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert not ok
        assert "tier field must equal 1" in reason

    def test_missing_branch_field_rejected(self, feature_branch_ctx):
        surface = _fresh_surface()
        del surface["branch"]
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert not ok
        assert "branch field" in reason

    def test_empty_branch_field_rejected(self, feature_branch_ctx):
        surface = _fresh_surface(branch="   ")
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert not ok
        assert "branch field" in reason

    def test_branch_mismatch_rejected_even_with_fresh_surface(self, feature_branch_ctx):
        # Operator's named context-bleed counter: surface declared one
        # branch, agent switched to another between authoring and exec.
        surface = _fresh_surface(branch="some-other-branch")
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert not ok
        assert "branch-binding mismatch" in reason
        assert "context-bleed" in reason

    def test_rationale_below_minimum_rejected(self, feature_branch_ctx):
        # Just under the 40-char minimum.
        short = "x" * (MICRO_SURFACE_RATIONALE_MIN_LEN - 1)
        surface = _fresh_surface(rationale=short)
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert not ok
        assert "rationale_one_line below minimum length" in reason

    def test_rationale_at_minimum_accepted(self, feature_branch_ctx):
        exact = "x" * MICRO_SURFACE_RATIONALE_MIN_LEN
        surface = _fresh_surface(rationale=exact)
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert ok, reason

    def test_disconfirmation_below_minimum_rejected(self, feature_branch_ctx):
        short = "y" * (MICRO_SURFACE_DISCONFIRMATION_MIN_LEN - 1)
        surface = _fresh_surface(disconfirmation=short)
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert not ok
        assert "disconfirmation_one_line below minimum length" in reason

    def test_timestamp_beyond_ttl_rejected(self, feature_branch_ctx):
        stale_ts = (
            datetime.now(timezone.utc)
            - timedelta(seconds=MICRO_SURFACE_TTL_SECONDS + 30)
        ).isoformat()
        surface = _fresh_surface(timestamp=stale_ts)
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert not ok
        assert "stale" in reason

    def test_timestamp_within_ttl_accepted(self, feature_branch_ctx):
        near_stale_ts = (
            datetime.now(timezone.utc)
            - timedelta(seconds=MICRO_SURFACE_TTL_SECONDS - 30)
        ).isoformat()
        surface = _fresh_surface(timestamp=near_stale_ts)
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert ok, reason

    def test_future_timestamp_rejected(self, feature_branch_ctx):
        future_ts = (
            datetime.now(timezone.utc) + timedelta(seconds=60)
        ).isoformat()
        surface = _fresh_surface(timestamp=future_ts)
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert not ok
        assert "future" in reason

    def test_malformed_timestamp_rejected(self, feature_branch_ctx):
        surface = _fresh_surface(timestamp="not-an-iso-string")
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert not ok
        assert "does not parse" in reason

    def test_trailing_z_timestamp_accepted(self, feature_branch_ctx):
        # The schema documents `2026-05-23T14:30:00Z` form; validator must
        # accept it via the `Z → +00:00` swap before fromisoformat.
        z_ts = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        ).replace("+00:00", "Z")
        surface = _fresh_surface(timestamp=z_ts)
        ok, reason = validate_micro_surface(surface, feature_branch_ctx)
        assert ok, reason

    def test_non_dict_surface_rejected(self, feature_branch_ctx):
        # Intentionally pass a non-dict to exercise the type-guard branch.
        ok, reason = validate_micro_surface(
            ["not", "a", "dict"],  # type: ignore[arg-type]
            feature_branch_ctx,
        )
        assert not ok
        assert "not a dict" in reason

    def test_explicit_now_parameter_honored(self, feature_branch_ctx):
        # Caller supplies an explicit `now` (e.g., for hermetic testing
        # or replay against historical telemetry).
        anchor = datetime(2026, 5, 23, 12, 0, 0, tzinfo=timezone.utc)
        # Surface timestamped 60s before the anchor — well within TTL.
        surface = _fresh_surface(
            timestamp=(anchor - timedelta(seconds=60)).isoformat()
        )
        ok, reason = validate_micro_surface(surface, feature_branch_ctx, now=anchor)
        assert ok, reason

    def test_micro_surface_does_not_apply_to_detached_head(self, detached_head_ctx):
        # When current_branch is None (detached HEAD), branch-binding
        # cannot match — even a well-formed surface fails this gate.
        # Loss-averse: no Tier 1 dispatch in detached state.
        surface = _fresh_surface()
        ok, reason = validate_micro_surface(surface, detached_head_ctx)
        assert not ok
        assert "branch-binding mismatch" in reason


# ---------------------------------------------------------------------------
# Event 134.1 — Profile-aware classifier (risk_tolerance==0 incident mode).
# ---------------------------------------------------------------------------


class TestProfileAwareClassifier:
    def test_none_profile_preserves_static_tier_1_behavior(self, feature_branch_ctx):
        # Stage 0 default: callers pass operator_profile=None and get
        # the static loss-averse classification — unchanged from the
        # pre-134.1 contract.
        verdict = classify(
            "Bash",
            {"command": "git push origin event-134-tier-gate"},
            feature_branch_ctx,
            operator_profile=None,
        )
        assert verdict.tier == Tier.ONE

    def test_default_profile_preserves_static_tier_1_behavior(self, feature_branch_ctx):
        # OperatorProfile() with default risk_tolerance=2 (the operator's
        # current elicited value) does NOT force-escalate.
        verdict = classify(
            "Bash",
            {"command": "git push origin event-134-tier-gate"},
            feature_branch_ctx,
            operator_profile=OperatorProfile(),
        )
        assert verdict.tier == Tier.ONE

    def test_risk_tolerance_zero_forces_tier_2_on_tier_1_op(self, feature_branch_ctx):
        # Operator's incident-mode override: risk_tolerance=0 means every
        # Tier 1 hit force-escalates to Tier 2 strict-block. Tier 1 label
        # preserved in `pattern` so telemetry sees what WOULD have been
        # Tier 1.
        verdict = classify(
            "Bash",
            {"command": "git push origin event-134-tier-gate"},
            feature_branch_ctx,
            operator_profile=OperatorProfile(risk_tolerance=0),
        )
        assert verdict.tier == Tier.TWO
        assert "force-escalated" in verdict.reason
        assert "risk_tolerance=0" in verdict.reason
        # Original Tier 1 pattern label preserved for telemetry.
        assert verdict.pattern == "git push (non-protected branch)"

    def test_risk_tolerance_zero_does_not_relax_tier_3(self, main_branch_ctx):
        # The override only tightens — it never relaxes Tier 3. Force-push
        # to main is Tier 3 regardless of profile.
        verdict = classify(
            "Bash",
            {"command": "git push --force origin main"},
            main_branch_ctx,
            operator_profile=OperatorProfile(risk_tolerance=0),
        )
        assert verdict.tier == Tier.THREE

    def test_risk_tolerance_zero_does_not_affect_existing_tier_2_ops(
        self, feature_branch_ctx
    ):
        # An op that was already Tier 2 stays Tier 2; the override
        # changes the LABEL slightly but not the verdict — let's verify
        # the verdict is unchanged.
        verdict = classify(
            "Bash",
            {"command": "npm publish"},
            feature_branch_ctx,
            operator_profile=OperatorProfile(risk_tolerance=0),
        )
        assert verdict.tier == Tier.TWO

    def test_risk_tolerance_zero_force_escalates_gh_release_prerelease(
        self, feature_branch_ctx
    ):
        # Confirms the override fires across all Tier 1 patterns, not
        # just git push.
        verdict = classify(
            "Bash",
            {"command": "gh release create v1.4.0-rc1 --prerelease"},
            feature_branch_ctx,
            operator_profile=OperatorProfile(risk_tolerance=0),
        )
        assert verdict.tier == Tier.TWO
        assert "force-escalated" in verdict.reason

    def test_risk_tolerance_zero_force_escalates_gh_issue_create(
        self, feature_branch_ctx
    ):
        verdict = classify(
            "Bash",
            {"command": "gh issue create --title 'Bug'"},
            feature_branch_ctx,
            operator_profile=OperatorProfile(risk_tolerance=0),
        )
        assert verdict.tier == Tier.TWO
        assert "force-escalated" in verdict.reason


# ---------------------------------------------------------------------------
# Event 135 — Stage 3 soak gate + telemetry writer.
# ---------------------------------------------------------------------------


def _make_tier1_record(
    when: datetime,
    confirmed: bool = True,
    reverted: bool = False,
    pattern: str = "git push (non-protected branch)",
) -> dict:
    return {
        "correlation_id": f"cid-{when.timestamp()}",
        "timestamp": when.isoformat(),
        "pattern": pattern,
        "branch": "event-135",
        "rationale_one_line": "feature push — safe; revert via gh pr close",
        "exit_code": 0,
        "operator_confirmed": confirmed,
        "subsequent_revert_within_24h": reverted,
    }


class TestSoakGate:
    def test_empty_telemetry_keeps_gate_closed(self, tmp_path):
        target = tmp_path / "tier1.jsonl"
        is_open, reason = soak_gate_open(path=target)
        assert is_open is False
        assert "no telemetry" in reason

    def test_below_min_ops_keeps_gate_closed(self, tmp_path):
        target = tmp_path / "tier1.jsonl"
        now = datetime.now(timezone.utc)
        for i in range(SOAK_GATE_MIN_OPS - 1):
            write_tier1_record(
                _make_tier1_record(now - timedelta(days=SOAK_GATE_MIN_DAYS + 1, seconds=i)),
                path=target,
            )
        is_open, reason = soak_gate_open(path=target, now=now)
        assert is_open is False
        assert "< " in reason and "required" in reason

    def test_below_min_days_keeps_gate_closed(self, tmp_path):
        target = tmp_path / "tier1.jsonl"
        now = datetime.now(timezone.utc)
        # N ops but all clustered in last 24h — fails calendar-span gate.
        for i in range(SOAK_GATE_MIN_OPS):
            write_tier1_record(
                _make_tier1_record(now - timedelta(hours=i)),
                path=target,
            )
        is_open, reason = soak_gate_open(path=target, now=now)
        assert is_open is False
        assert "span" in reason

    def test_below_accuracy_keeps_gate_closed(self, tmp_path):
        target = tmp_path / "tier1.jsonl"
        now = datetime.now(timezone.utc)
        anchor = now - timedelta(days=SOAK_GATE_MIN_DAYS + 1)
        # 20 confirmed ops; 5 reverted → accuracy 75% < 90% threshold.
        for i in range(SOAK_GATE_MIN_OPS):
            reverted = i < 5
            write_tier1_record(
                _make_tier1_record(
                    anchor + timedelta(hours=i),
                    confirmed=True,
                    reverted=reverted,
                ),
                path=target,
            )
        is_open, reason = soak_gate_open(path=target, now=now)
        assert is_open is False
        assert "rationale-accuracy" in reason

    def test_all_thresholds_passed_opens_gate(self, tmp_path):
        target = tmp_path / "tier1.jsonl"
        now = datetime.now(timezone.utc)
        anchor = now - timedelta(days=SOAK_GATE_MIN_DAYS + 1)
        # 20 confirmed ops, 1 reverted → 95% accuracy ≥ 90%.
        for i in range(SOAK_GATE_MIN_OPS):
            reverted = i == 0
            write_tier1_record(
                _make_tier1_record(
                    anchor + timedelta(hours=i * 8),
                    confirmed=True,
                    reverted=reverted,
                ),
                path=target,
            )
        is_open, reason = soak_gate_open(path=target, now=now)
        assert is_open is True, reason
        assert "OPEN" in reason

    def test_corrupt_lines_skipped_not_crashed(self, tmp_path):
        target = tmp_path / "tier1.jsonl"
        now = datetime.now(timezone.utc)
        anchor = now - timedelta(days=SOAK_GATE_MIN_DAYS + 1)
        for i in range(SOAK_GATE_MIN_OPS):
            write_tier1_record(
                _make_tier1_record(anchor + timedelta(hours=i * 8)),
                path=target,
            )
        # Inject a corrupt line in the middle.
        with open(target, "a", encoding="utf-8") as f:
            f.write("not-json-{{\n")
        # Should still pass — corrupt lines skipped.
        is_open, _ = soak_gate_open(path=target, now=now)
        assert is_open is True

    def test_zero_confirmed_keeps_gate_closed(self, tmp_path):
        # All records have operator_confirmed=False → rationale-accuracy
        # rate is undefined → gate stays closed.
        target = tmp_path / "tier1.jsonl"
        now = datetime.now(timezone.utc)
        anchor = now - timedelta(days=SOAK_GATE_MIN_DAYS + 1)
        for i in range(SOAK_GATE_MIN_OPS):
            write_tier1_record(
                _make_tier1_record(
                    anchor + timedelta(hours=i * 8),
                    confirmed=False,
                ),
                path=target,
            )
        is_open, reason = soak_gate_open(path=target, now=now)
        assert is_open is False
        assert "zero operator-confirmed" in reason


class TestWriteTier1Record:
    def test_creates_parent_dir(self, tmp_path):
        target = tmp_path / "deep" / "nested" / "tier1.jsonl"
        record = _make_tier1_record(datetime.now(timezone.utc))
        write_tier1_record(record, path=target)
        assert target.is_file()

    def test_appends_one_line_per_call(self, tmp_path):
        target = tmp_path / "tier1.jsonl"
        now = datetime.now(timezone.utc)
        for i in range(3):
            write_tier1_record(_make_tier1_record(now + timedelta(seconds=i)), path=target)
        lines = target.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        for line in lines:
            import json as _json
            obj = _json.loads(line)
            assert obj["pattern"] == "git push (non-protected branch)"


class TestLoadOperatorProfile:
    def test_returns_none_when_no_source(self, monkeypatch, tmp_path):
        # Both disk sources missing — function returns None and the
        # classifier's static defaults apply.
        from core.practice import irreversible_tier as it
        monkeypatch.setattr(it, "_DERIVED_KNOBS_PATH", tmp_path / "missing.json")
        monkeypatch.setattr(it, "_OPERATOR_PROFILE_MD", tmp_path / "missing.md")
        assert it.load_operator_profile() is None

    def test_reads_derived_knobs_json(self, monkeypatch, tmp_path):
        import json as _json
        from core.practice import irreversible_tier as it
        knobs = tmp_path / "derived_knobs.json"
        knobs.write_text(_json.dumps({
            "risk_tolerance": 0,
            "asymmetry_posture": "loss-averse",
        }))
        monkeypatch.setattr(it, "_DERIVED_KNOBS_PATH", knobs)
        profile = it.load_operator_profile()
        assert profile is not None
        assert profile.risk_tolerance == 0
        assert profile.asymmetry_posture == "loss-averse"

    def test_falls_back_to_markdown(self, monkeypatch, tmp_path):
        from core.practice import irreversible_tier as it
        md = tmp_path / "operator_profile.md"
        md.write_text("""
risk_tolerance:
  value: 2
  confidence: elicited

asymmetry_posture:
  value: loss-averse
  confidence: elicited
""")
        monkeypatch.setattr(it, "_DERIVED_KNOBS_PATH", tmp_path / "missing.json")
        monkeypatch.setattr(it, "_OPERATOR_PROFILE_MD", md)
        profile = it.load_operator_profile()
        assert profile is not None
        assert profile.risk_tolerance == 2
        assert profile.asymmetry_posture == "loss-averse"

    def test_malformed_knobs_returns_none(self, monkeypatch, tmp_path):
        from core.practice import irreversible_tier as it
        knobs = tmp_path / "derived_knobs.json"
        knobs.write_text("not valid json {{{")
        monkeypatch.setattr(it, "_DERIVED_KNOBS_PATH", knobs)
        monkeypatch.setattr(it, "_OPERATOR_PROFILE_MD", tmp_path / "missing.md")
        assert it.load_operator_profile() is None


# Quiet pyright on the test-file's pytest import in environments where
# the analyzer doesn't see the installed package.
_ = pytest
