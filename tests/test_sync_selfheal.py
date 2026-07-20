"""Event 150 · sync self-heal — the forgotten-`episteme sync` gap.

Covers `_sync_selfheal_line()` (SessionStart) + the adapter substrate
(`settings_in_sync`, `read_sync_meta`, the sync sidecar): a synced runtime
stays silent; registration drift with a KNOWN governance pack (sidecar)
auto-heals and says so; drift with an UNKNOWN pack advises without writing
(healing with a guessed pack could silently downgrade strict); any failure
degrades to silence. Detection and heal target the same tree
(episteme.cli.HOME) by construction.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.hooks import session_context as sc  # pyright: ignore[reportAttributeAccessIssue]

import episteme.cli as ecli  # pyright: ignore[reportMissingImports]
from episteme.adapters import claude as cadapter  # pyright: ignore[reportMissingImports]


class _TmpHome:
    """Context manager: point episteme.cli.HOME at a tmp dir and run a real
    `sync('balanced')` there so tests start from a genuinely-synced state."""

    def __enter__(self):
        self._td = tempfile.TemporaryDirectory()
        self._orig = ecli.HOME
        ecli.HOME = Path(self._td.name)
        cadapter.sync("balanced")
        self.claude_root = ecli.HOME / ".claude"
        return self

    def __exit__(self, *exc):
        ecli.HOME = self._orig
        self._td.cleanup()
        return False


class SyncMetaTests(unittest.TestCase):
    def test_sidecar_written_by_sync_and_readable(self):
        with _TmpHome() as th:
            meta = cadapter.read_sync_meta(th.claude_root)
            self.assertEqual(meta.get("governance_pack"), "balanced")
            self.assertIn("synced_at", meta)

    def test_read_sync_meta_absent_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(cadapter.read_sync_meta(Path(td)), {})

    def test_read_sync_meta_malformed_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / cadapter.SYNC_META_FILENAME).write_text("not json{", encoding="utf-8")
            self.assertEqual(cadapter.read_sync_meta(Path(td)), {})


class SettingsInSyncTests(unittest.TestCase):
    def test_freshly_synced_settings_are_in_sync(self):
        with _TmpHome() as th:
            existing = json.loads((th.claude_root / "settings.json").read_text(encoding="utf-8"))
            self.assertTrue(cadapter.settings_in_sync(existing, "balanced"))

    def test_removed_hook_entry_is_drift(self):
        with _TmpHome() as th:
            existing = json.loads((th.claude_root / "settings.json").read_text(encoding="utf-8"))
            hooks = existing.get("hooks", {})
            first_event = next(iter(hooks))
            hooks[first_event] = hooks[first_event][1:]  # drop one registration
            self.assertFalse(cadapter.settings_in_sync(existing, "balanced"))


class SelfHealLineTests(unittest.TestCase):
    def test_synced_state_is_silent(self):
        with _TmpHome():
            self.assertIsNone(sc._sync_selfheal_line())

    def test_settings_drift_with_sidecar_heals_and_reports(self):
        with _TmpHome() as th:
            settings_path = th.claude_root / "settings.json"
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
            first_event = next(iter(existing["hooks"]))
            existing["hooks"][first_event] = existing["hooks"][first_event][1:]
            settings_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

            line = sc._sync_selfheal_line()
            assert line is not None
            self.assertIn("sync-selfheal", line)
            self.assertIn("balanced", line)
            self.assertIn("next session", line)
            healed = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertTrue(cadapter.settings_in_sync(healed, "balanced"))

    def test_claude_md_drift_with_sidecar_heals(self):
        with _TmpHome() as th:
            claude_md = th.claude_root / "CLAUDE.md"
            claude_md.write_text("# something the operator pasted over it\n", encoding="utf-8")
            line = sc._sync_selfheal_line()
            assert line is not None
            self.assertIn("sync-selfheal", line)
            body = claude_md.read_text(encoding="utf-8")
            self.assertIn("episteme Global Memory", body)

    def test_drift_without_sidecar_advises_without_writing(self):
        with _TmpHome() as th:
            (th.claude_root / cadapter.SYNC_META_FILENAME).unlink()
            settings_path = th.claude_root / "settings.json"
            existing = json.loads(settings_path.read_text(encoding="utf-8"))
            first_event = next(iter(existing["hooks"]))
            existing["hooks"][first_event] = existing["hooks"][first_event][1:]
            drifted = json.dumps(existing, indent=2) + "\n"
            settings_path.write_text(drifted, encoding="utf-8")

            line = sc._sync_selfheal_line()
            assert line is not None
            self.assertIn("run `episteme sync`", line)
            self.assertIn("not auto-written", line)
            # Fail-safe: nothing was rewritten.
            self.assertEqual(settings_path.read_text(encoding="utf-8"), drifted)

    def test_any_exception_degrades_to_silence(self):
        with _TmpHome():
            with mock.patch.object(
                cadapter, "render_user_claude_md", side_effect=RuntimeError("boom")
            ):
                self.assertIsNone(sc._sync_selfheal_line())


class DeployPruneTests(unittest.TestCase):
    """Event 159 — sync cleans up after itself. Positive-system
    ownership: only names the PRIOR sync manifest recorded as deployed
    are prune candidates; operator-authored entries under
    ~/.claude/{skills,agents} were never manifested and are
    structurally untouchable."""

    def _seed_ghosts(self, th, *, manifest: bool) -> None:
        """Plant a deployed skill dir + agent file whose repo source is
        gone; optionally record them in the sync sidecar manifest."""
        ghost_skill = th.claude_root / "skills" / "ghost-skill"
        ghost_skill.mkdir(parents=True, exist_ok=True)
        (ghost_skill / "SKILL.md").write_text("orphan", encoding="utf-8")
        (th.claude_root / "agents" / "ghost-agent.md").write_text(
            "orphan", encoding="utf-8"
        )
        if manifest:
            meta = cadapter.read_sync_meta(th.claude_root)
            meta["deployed_skills"] = list(
                meta.get("deployed_skills") or []
            ) + ["ghost-skill"]
            meta["deployed_agents"] = list(
                meta.get("deployed_agents") or []
            ) + ["ghost-agent.md"]
            (th.claude_root / cadapter.SYNC_META_FILENAME).write_text(
                __import__("json").dumps(meta), encoding="utf-8"
            )

    def test_prior_manifest_orphans_pruned_on_next_sync(self):
        with _TmpHome() as th:
            self._seed_ghosts(th, manifest=True)
            cadapter.sync("balanced")
            self.assertFalse(
                (th.claude_root / "skills" / "ghost-skill").exists()
            )
            self.assertFalse(
                (th.claude_root / "agents" / "ghost-agent.md").exists()
            )

    def test_unmanifested_entries_never_touched(self):
        with _TmpHome() as th:
            self._seed_ghosts(th, manifest=False)
            cadapter.sync("balanced")
            self.assertTrue(
                (th.claude_root / "skills" / "ghost-skill" / "SKILL.md").exists()
            )
            self.assertTrue(
                (th.claude_root / "agents" / "ghost-agent.md").exists()
            )

    def test_pre_e159_sidecar_without_fields_prunes_nothing(self):
        with _TmpHome() as th:
            self._seed_ghosts(th, manifest=False)
            # Rewrite the sidecar WITHOUT the deployed_* fields — the
            # pre-E159 shape.
            (th.claude_root / cadapter.SYNC_META_FILENAME).write_text(
                '{"governance_pack": "balanced", "synced_at": "2026-01-01T00:00:00+00:00"}',
                encoding="utf-8",
            )
            cadapter.sync("balanced")
            self.assertTrue(
                (th.claude_root / "skills" / "ghost-skill").exists()
            )
            meta = cadapter.read_sync_meta(th.claude_root)
            self.assertIsInstance(meta.get("deployed_skills"), list)
            self.assertIsInstance(meta.get("deployed_agents"), list)

    def test_meta_records_current_deployed_sets(self):
        with _TmpHome() as th:
            meta = cadapter.read_sync_meta(th.claude_root)
            expected_skills = sorted(
                d.name for d in ecli._managed_skills()
            )
            expected_agents = sorted(
                f.name
                for f in (ecli.REPO_ROOT / "core" / "agents").glob("*.md")
            )
            self.assertEqual(meta.get("deployed_skills"), expected_skills)
            self.assertEqual(meta.get("deployed_agents"), expected_agents)

    def test_prune_archives_verbatim_before_delete(self):
        # [K] archive-verbatim: a formerly-managed copy may carry
        # operator hand-edits that exist nowhere else.
        with _TmpHome() as th:
            self._seed_ghosts(th, manifest=True)
            cadapter.sync("balanced")
            archive_root = th.claude_root / "_archive"
            hits = list(archive_root.rglob("ghost-skill/SKILL.md"))
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0].read_text(encoding="utf-8"), "orphan")
            self.assertTrue(list(archive_root.rglob("ghost-agent.md")))

    def test_case_alias_of_wanted_name_never_pruned(self):
        # Event 159 review finding: on a case-insensitive filesystem a
        # case-variant candidate aliases the currently-wanted copy —
        # deleting it would delete the wanted skill. The guard is set
        # logic, so this test holds on case-sensitive CI too.
        with _TmpHome() as th:
            wanted = th.claude_root / "skills" / "kept-skill"
            wanted.mkdir(parents=True, exist_ok=True)
            (wanted / "SKILL.md").write_text("wanted", encoding="utf-8")
            pruned = cadapter.prune_orphaned_deploy_copies(
                th.claude_root,
                {"deployed_skills": ["Kept-Skill"], "deployed_agents": []},
                current_skills={"kept-skill"},
                current_agents=set(),
            )
            self.assertEqual(pruned, [])
            self.assertTrue((wanted / "SKILL.md").exists())

    def test_symlinked_entry_under_manifested_name_skipped(self):
        # sync never deploys symlinks; a symlink under a manifested name
        # is operator-authored — neither the link nor its target may be
        # touched.
        with _TmpHome() as th:
            real = Path(self_dir := tempfile.mkdtemp()) / "real-content"
            real.mkdir()
            (real / "SKILL.md").write_text("precious", encoding="utf-8")
            link = th.claude_root / "skills" / "linked-skill"
            link.symlink_to(real)
            pruned = cadapter.prune_orphaned_deploy_copies(
                th.claude_root,
                {"deployed_skills": ["linked-skill"], "deployed_agents": []},
                current_skills=set(),
                current_agents=set(),
            )
            self.assertEqual(pruned, [])
            self.assertTrue(link.is_symlink())
            self.assertTrue((real / "SKILL.md").exists())

    def test_traversal_shaped_manifest_names_skipped(self):
        with _TmpHome() as th:
            meta = cadapter.read_sync_meta(th.claude_root)
            meta["deployed_skills"] = ["../outside-skill"]
            meta["deployed_agents"] = ["../../outside.md"]
            (th.claude_root / cadapter.SYNC_META_FILENAME).write_text(
                __import__("json").dumps(meta), encoding="utf-8"
            )
            outside = th.claude_root / "outside-skill"
            outside.mkdir(parents=True, exist_ok=True)
            (outside / "SKILL.md").write_text("x", encoding="utf-8")
            cadapter.sync("balanced")
            self.assertTrue((outside / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()


class SyncOriginGuardTests(unittest.TestCase):
    """Event 166, from a live incident — a sync run from a scratchpad
    CLONE rewrote the operator's real ~/.claude/CLAUDE.md to @-reference
    that clone's EXAMPLE memory files, silently swapping the encoded
    operator profile for defaults in every future session. The kernel
    already had the rule ('never sync from a worktree') as prose wired
    to no gate."""

    def test_primary_checkout_is_allowed(self):
        with _TmpHome() as th:
            self.assertIsNone(
                cadapter.sync_origin_problem(ecli.REPO_ROOT, th.claude_root)
                if hasattr(cadapter, "sync_origin_problem")
                else ecli.sync_origin_problem(ecli.REPO_ROOT, th.claude_root)
            )

    def test_linked_worktree_refused(self):
        with _TmpHome() as th, tempfile.TemporaryDirectory() as td:
            wt = Path(td) / "wt"
            wt.mkdir()
            # A linked worktree carries .git as a FILE, not a directory.
            (wt / ".git").write_text("gitdir: /elsewhere/.git/worktrees/wt")
            problem = ecli.sync_origin_problem(wt, th.claude_root)
            assert problem is not None
            self.assertIn("worktree", problem)

    def test_temp_checkout_refused(self):
        with _TmpHome() as th, tempfile.TemporaryDirectory() as td:
            clone = Path(td).resolve() / "repo2"
            (clone / ".git").mkdir(parents=True)
            problem = ecli.sync_origin_problem(clone, th.claude_root)
            assert problem is not None
            self.assertIn("temp root", problem)

    def test_second_checkout_refused_when_sidecar_names_another(self):
        with _TmpHome() as th, tempfile.TemporaryDirectory() as td:
            other = Path(td) / "other-checkout"
            (other / ".git").mkdir(parents=True)
            meta = cadapter.read_sync_meta(th.claude_root)
            meta["repo_root"] = str(other)
            (th.claude_root / cadapter.SYNC_META_FILENAME).write_text(
                json.dumps(meta), encoding="utf-8"
            )
            problem = ecli.sync_origin_problem(ecli.REPO_ROOT, th.claude_root)
            assert problem is not None
            self.assertIn("last deployed", problem)

    def test_sidecar_records_repo_root(self):
        with _TmpHome() as th:
            meta = cadapter.read_sync_meta(th.claude_root)
            self.assertEqual(meta.get("repo_root"), str(ecli.REPO_ROOT))

    def test_missing_prior_root_does_not_refuse(self):
        # First-ever sync has nothing to compare against.
        with _TmpHome() as th:
            meta = cadapter.read_sync_meta(th.claude_root)
            meta.pop("repo_root", None)
            (th.claude_root / cadapter.SYNC_META_FILENAME).write_text(
                json.dumps(meta), encoding="utf-8"
            )
            self.assertIsNone(
                ecli.sync_origin_problem(ecli.REPO_ROOT, th.claude_root)
            )

    def test_force_downgrades_refusal_to_warning(self):
        with _TmpHome() as th, tempfile.TemporaryDirectory() as td:
            other = Path(td) / "other-checkout"
            (other / ".git").mkdir(parents=True)
            meta = cadapter.read_sync_meta(th.claude_root)
            meta["repo_root"] = str(other)
            (th.claude_root / cadapter.SYNC_META_FILENAME).write_text(
                json.dumps(meta), encoding="utf-8"
            )
            self.assertEqual(
                ecli._enforce_sync_origin(th.claude_root, False), 2
            )
            self.assertIsNone(
                ecli._enforce_sync_origin(th.claude_root, True)
            )


class CodexAdapterTests(unittest.TestCase):
    """Event 167 — the Codex adapter was DECLARED in
    core/adapters/codex.json but never implemented, so `episteme sync`
    never reached ~/.codex. AGENTS.md there is the operator's own
    contract (428 lines of hand-authored directives when this shipped),
    so the adapter must ADD a managed region and preserve every byte
    outside it — the E166 clobber class, hours old at the time."""

    def _codex_home(self, stack):
        td = stack.enter_context(tempfile.TemporaryDirectory())
        home = Path(td)
        (home / ".codex").mkdir()
        return home

    def test_not_installed_is_a_no_op(self):
        import contextlib
        from episteme.adapters import codex as cadex  # pyright: ignore[reportMissingImports]
        with contextlib.ExitStack() as stack:
            td = stack.enter_context(tempfile.TemporaryDirectory())
            orig, ecli.HOME = ecli.HOME, Path(td)  # no ~/.codex
            try:
                self.assertFalse(cadex.sync())
            finally:
                ecli.HOME = orig

    def test_preserves_operator_authored_agents_md(self):
        import contextlib
        from episteme.adapters import codex as cadex  # pyright: ignore[reportMissingImports]
        with contextlib.ExitStack() as stack:
            home = self._codex_home(stack)
            agents = home / ".codex" / "AGENTS.md"
            operator_text = (
                "<!-- AUTONOMY DIRECTIVE — DO NOT REMOVE -->\n"
                "YOU ARE AN AUTONOMOUS CODING AGENT.\n\n"
                "## My own section\n\nhand-authored, exists nowhere else\n"
            )
            agents.write_text(operator_text, encoding="utf-8")
            orig, ecli.HOME = ecli.HOME, home
            try:
                self.assertTrue(cadex.sync())
                after = agents.read_text(encoding="utf-8")
            finally:
                ecli.HOME = orig
            # Every operator line survives, verbatim.
            for line in operator_text.strip().splitlines():
                self.assertIn(line, after)
            self.assertIn("episteme — operator governance contract", after)

    def test_resync_is_idempotent_and_still_preserves(self):
        import contextlib
        from episteme.adapters import codex as cadex  # pyright: ignore[reportMissingImports]
        with contextlib.ExitStack() as stack:
            home = self._codex_home(stack)
            agents = home / ".codex" / "AGENTS.md"
            agents.write_text("## operator\nkeep me\n", encoding="utf-8")
            orig, ecli.HOME = ecli.HOME, home
            try:
                runs = []
                for _ in range(3):
                    cadex.sync()
                    runs.append(agents.read_text(encoding="utf-8"))
            finally:
                ecli.HOME = orig
            # The shared _compose_managed_file primitive normalizes one
            # blank line between the appended block and pre-existing
            # content on the SECOND write, then converges. That is
            # pre-existing behavior of the primitive (shared with the
            # Claude and Hermes adapters), not something this adapter
            # introduces — pinned here as the real contract rather than
            # asserted away. Filed as a deferred discovery.
            self.assertEqual(runs[1], runs[2], "must converge after the first resync")
            # The properties that actually matter hold on EVERY run.
            for r in runs:
                self.assertIn("keep me", r)
                self.assertEqual(r.count("episteme — operator governance contract"), 1)

    def test_creates_agents_md_when_absent(self):
        import contextlib
        from episteme.adapters import codex as cadex  # pyright: ignore[reportMissingImports]
        with contextlib.ExitStack() as stack:
            home = self._codex_home(stack)
            orig, ecli.HOME = ecli.HOME, home
            try:
                self.assertTrue(cadex.sync())
            finally:
                ecli.HOME = orig
            self.assertTrue((home / ".codex" / "AGENTS.md").is_file())

    def test_managed_skills_added_without_touching_operator_skills(self):
        import contextlib
        from episteme.adapters import codex as cadex  # pyright: ignore[reportMissingImports]
        with contextlib.ExitStack() as stack:
            home = self._codex_home(stack)
            skills = home / ".codex" / "skills"
            (skills / "ask-claude").mkdir(parents=True)
            (skills / "ask-claude" / "SKILL.md").write_text("operator's own", encoding="utf-8")
            system = skills / ".system"
            system.mkdir()
            (system / "bundled.md").write_text("codex bundled", encoding="utf-8")
            orig, ecli.HOME = ecli.HOME, home
            try:
                cadex.sync()
            finally:
                ecli.HOME = orig
            # Operator + Codex-bundled content untouched...
            self.assertEqual(
                (skills / "ask-claude" / "SKILL.md").read_text(encoding="utf-8"),
                "operator's own",
            )
            self.assertEqual(
                (system / "bundled.md").read_text(encoding="utf-8"), "codex bundled"
            )
            # ...and managed skills landed alongside.
            managed = {d.name for d in ecli._managed_skills()}
            deployed = {p.name for p in skills.iterdir() if p.is_dir()}
            self.assertTrue(managed.issubset(deployed))

    def test_declared_adapter_spec_matches_implementation(self):
        # The JSON registry is the contract; drift between it and the
        # code is what let this adapter sit unimplemented for months.
        from episteme.adapters import codex as cadex  # pyright: ignore[reportMissingImports]
        spec = json.loads(
            (ecli.REPO_ROOT / "core" / "adapters" / "codex.json").read_text(encoding="utf-8")
        )
        self.assertEqual(spec["sync"]["skills_dir"], "~/.codex/skills")
        self.assertEqual(spec["project_contract"], "AGENTS.md")
        self.assertIn(".system", cadex.PROTECTED_SKILL_DIRS)


class ToxicCloneHookPruneTests(unittest.TestCase):
    """Event 170 — live incident residue: the E166 rogue sync ALSO
    merged its clone-path hook registrations into settings.json, and
    prune_managed_hook_entries preserved them as 'external hooks'
    (positive-system keep). 19 scripts ran DOUBLE on every governed op.
    The rule that separates residue from genuinely-foreign hooks: a
    command whose script BASENAME matches a managed hook but whose path
    is outside the primary checkout is clone residue; a non-managed
    script name is operator content and stays."""

    def _settings_with(self, extra_cmd):
        base = cadapter.build_settings("balanced")
        base["hooks"].setdefault("PreToolUse", []).append(
            {"matcher": "Bash", "hooks": [{"type": "command", "command": extra_cmd}]}
        )
        return base

    def test_managed_basename_under_foreign_root_is_pruned(self):
        toxic = "/usr/bin/python3 /tmp/somewhere/repo2/core/hooks/workflow_guard.py"
        s = cadapter.prune_managed_hook_entries(
            self._settings_with(toxic), "balanced"
        )
        flat = json.dumps(s)
        self.assertNotIn("/tmp/somewhere/repo2", flat)

    def test_operator_authored_foreign_hook_survives(self):
        mine = "/usr/bin/python3 /Users/x/my-own-hooks/notify_slack.py"
        s = cadapter.prune_managed_hook_entries(
            self._settings_with(mine), "balanced"
        )
        self.assertIn("notify_slack.py", json.dumps(s))

    def test_primary_root_managed_hooks_untouched(self):
        s = cadapter.prune_managed_hook_entries(
            cadapter.build_settings("balanced"), "balanced"
        )
        flat = json.dumps(s)
        self.assertIn("workflow_guard.py", flat)
        self.assertIn(str(ecli.REPO_ROOT), flat)
