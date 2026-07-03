"""Registration-surface parity: sync route vs plugin route.

Three surfaces can register episteme's hooks with Claude Code: the
operator's live ~/.claude/settings.json (hand-maintained), the sync
route (`episteme sync` → adapters/claude.py build_settings()), and the
plugin route (marketplace install → hooks/hooks.json). The 2026-07-03
recon found all three had silently drifted into DIFFERENT hook sets —
a stranger installing via sync got no conclusion_guard/conclusion_gate
(the v2.0 Epistemic Engine pair, Event 139), and a stranger installing
the plugin got no checkpoint/test_runner/prompt_guard.

This suite makes build_settings() the canonical set and pins the
plugin's divergence to a NAMED exclusion list with reasons. Any
unnamed drift — a hook added to one surface and not the other — fails
here, which converts silent set-drift into a conscious decision.
(Rule shape: positive system — every divergence is enumerated.)
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from episteme.adapters import claude as claude_adapter

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"


def _script_name(command: str) -> str:
    """Normalize a hook command string to its script basename."""
    for token in command.split():
        if token.endswith(".py"):
            return token.rsplit("/", 1)[-1]
    return command.strip()  # non-script commands (echo ...) verbatim


def _extract_pairs(hooks_map: dict) -> set[tuple[str, str]]:
    """(event, script basename) pairs from a Claude hooks map."""
    pairs: set[tuple[str, str]] = set()
    for event, entries in hooks_map.items():
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                if cmd:
                    pairs.add((event, _script_name(cmd)))
    return pairs


def _canonical_pairs(mode: str = "balanced") -> set[tuple[str, str]]:
    return _extract_pairs(claude_adapter.build_settings(mode)["hooks"])


def _plugin_pairs() -> set[tuple[str, str]]:
    data = json.loads(PLUGIN_HOOKS_JSON.read_text(encoding="utf-8"))
    return _extract_pairs(data["hooks"])


# ---------------------------------------------------------------------------
# Named divergences. Every entry is a conscious decision with a reason;
# an empty reason is not allowed to compile. Adding a hook to ONE
# surface without updating the other (or this list) fails the parity
# tests below.
# ---------------------------------------------------------------------------

# Canonical (sync) hooks the plugin deliberately does NOT ship.
PLUGIN_OMITS: dict[tuple[str, str], str] = {
    ("Stop", "checkpoint.py"):
        "auto-committing a stranger's repo on every Stop is invasive; "
        "operator-machine behavior only (known chkpt-on-master issue)",
    ("SubagentStop", "checkpoint.py"):
        "same as Stop checkpoint",
    ("PreToolUse", "_arm_a_pre.py"):
        "operator-profile trajectory instrumentation tied to the "
        "operator's lived memory files; meaningless without them",
    ("PostToolUse", "_arm_a_post.py"):
        "pairs with _arm_a_pre.py",
    ("PreToolUse", "prompt_guard.py"):
        "pending decision: plugin posture for prompt-shape advisories "
        "not yet made — named here so the drift is visible, not silent",
    ("PostToolUse", "test_runner.py"):
        "runs pytest with a 60s timeout on every Write/Edit; too "
        "opinionated for arbitrary stranger repos without opt-in",
    ("PostToolUse", "context_guard.py"):
        "pending decision: same as prompt_guard.py",
    ("PermissionRequest", "echo '{\"decision\":\"allow\"}'"):
        "machine-local convenience auto-allow; must never ship to "
        "strangers (removes the harness consent gate)",
}

# Plugin hooks the sync route deliberately does NOT register.
# (Empty today; matcher-level divergences that don't change the
# (event, script) set are pinned by their own tests below.)
PLUGIN_EXTRAS: dict[tuple[str, str], str] = {}


class SyncRouteDeliversTheEngine(unittest.TestCase):
    """The v2.0 conclusion pair must reach sync-route users."""

    def test_conclusion_guard_registered_on_user_prompt_submit(self):
        pairs = _canonical_pairs()
        self.assertIn(("UserPromptSubmit", "conclusion_guard.py"), pairs)

    def test_conclusion_gate_registered_on_stop(self):
        pairs = _canonical_pairs()
        self.assertIn(("Stop", "conclusion_gate.py"), pairs)

    def test_conclusion_pair_present_in_all_modes(self):
        for mode in ("balanced", "strict", "minimal"):
            with self.subTest(mode=mode):
                pairs = _canonical_pairs(mode)
                self.assertIn(
                    ("UserPromptSubmit", "conclusion_guard.py"), pairs
                )
                self.assertIn(("Stop", "conclusion_gate.py"), pairs)

    def test_conclusion_gate_ordered_before_checkpoint(self):
        # checkpoint commits the working tree; the gate's one-shot
        # nudge must fire before that bookkeeping (live settings.json
        # order: quality_gate, conclusion_gate, checkpoint).
        stop_entries = claude_adapter.build_settings("balanced")["hooks"]["Stop"]
        scripts = [
            _script_name(h["command"])
            for entry in stop_entries
            for h in entry["hooks"]
        ]
        self.assertLess(
            scripts.index("conclusion_gate.py"),
            scripts.index("checkpoint.py"),
        )


class RegistrationParity(unittest.TestCase):
    """Exact-set parity between sync and plugin routes."""

    def test_canonical_minus_plugin_is_exactly_the_named_omissions(self):
        diff = _canonical_pairs() - _plugin_pairs()
        self.assertEqual(
            diff, set(PLUGIN_OMITS),
            "sync-route hooks missing from the plugin that are not "
            "named in PLUGIN_OMITS (or a named omission that no longer "
            f"exists): {diff ^ set(PLUGIN_OMITS)}",
        )

    def test_plugin_minus_canonical_is_exactly_the_named_extras(self):
        diff = _plugin_pairs() - _canonical_pairs()
        self.assertEqual(
            diff, set(PLUGIN_EXTRAS),
            "plugin hooks missing from the sync route that are not "
            "named in PLUGIN_EXTRAS (or a named extra that no longer "
            f"exists): {diff ^ set(PLUGIN_EXTRAS)}",
        )

    def test_every_divergence_carries_a_reason(self):
        for table in (PLUGIN_OMITS, PLUGIN_EXTRAS):
            for key, reason in table.items():
                self.assertTrue(
                    reason and len(reason) >= 15,
                    f"divergence {key} needs a substantive reason",
                )

    def test_plugin_scripts_exist_in_repo(self):
        # A plugin entry pointing at a script that does not ship is a
        # broken install for every marketplace user.
        for _event, script in _plugin_pairs():
            if script.endswith(".py"):
                self.assertTrue(
                    (REPO_ROOT / "core" / "hooks" / script).exists(),
                    f"hooks.json references missing script {script}",
                )

    def test_canonical_scripts_exist_in_repo(self):
        for _event, script in _canonical_pairs():
            if script.endswith(".py"):
                self.assertTrue(
                    (REPO_ROOT / "core" / "hooks" / script).exists(),
                    f"build_settings references missing script {script}",
                )

    def test_known_matcher_divergence_state_tracker(self):
        # Matcher-level divergence invisible at (event, script)
        # granularity, pinned here so it stays a conscious decision:
        # the plugin ALSO runs state_tracker on Write|Edit|MultiEdit
        # (async) while sync registers it for Bash only. If either
        # side changes, this test forces the decision to be re-made.
        plugin = json.loads(PLUGIN_HOOKS_JSON.read_text(encoding="utf-8"))
        plugin_matchers = {
            entry.get("matcher", "")
            for entry in plugin["hooks"]["PostToolUse"]
            if any(
                "state_tracker.py" in h.get("command", "")
                for h in entry.get("hooks", [])
            )
        }
        self.assertEqual(
            plugin_matchers, {"Write|Edit|MultiEdit", "Bash"}
        )
        sync_matchers = {
            entry.get("matcher", "")
            for entry in claude_adapter.build_settings("balanced")["hooks"]["PostToolUse"]
            if any(
                "state_tracker.py" in h.get("command", "")
                for h in entry.get("hooks", [])
            )
        }
        self.assertEqual(sync_matchers, {"Bash"})


if __name__ == "__main__":
    unittest.main()
