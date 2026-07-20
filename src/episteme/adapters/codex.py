"""Codex CLI adapter. Mounts the operator context into ~/.codex as a
managed region inside AGENTS.md, and adds managed skills alongside the
operator's own.

Event 167 — the adapter was DECLARED in ``core/adapters/codex.json``
(detect paths, ``sync.skills_dir``, ``project_contract: AGENTS.md``, and
the explicit note that episteme must not overwrite
``~/.codex/skills/.system``) but never implemented: ``episteme sync``
wrote to Claude, Hermes, OMO and OMX, so a Codex session carried none of
the operator's governance state.

## Why a managed REGION, not a managed file

``~/.codex/AGENTS.md`` is the operator's own primary contract — 428 lines
of hand-authored directives at the time this shipped, starting with an
autonomy directive that predates episteme. Codex reads it the way Claude
Code reads ``CLAUDE.md``. Overwriting it would destroy operator content
that exists nowhere else, which is precisely the failure Event 166
recovered from hours earlier in the same session (a sync from a
throwaway checkout rewrote the operator's global memory to point at
example files).

So this adapter uses ``_write_managed_file``: episteme owns only the
text between its markers, and every byte outside them survives every
sync. The managed block is appended on first sync and updated in place
thereafter.

## Posture conflict is surfaced, not resolved

The operator's existing directive tells Codex to execute autonomously
without asking. episteme's posture gates irreversible operations. Those
are in genuine tension, and an adapter is the wrong place to silently
pick a winner — so the managed block states the precedence question
plainly and leaves the resolution to the operator's own text.
"""
from __future__ import annotations

from pathlib import Path

from .. import cli as _cli


# Distinct from the default marker so a future Codex-specific migration
# can find exactly this block without touching other managed files.
CODEX_MARKER = "episteme:codex"

# The adapter spec forbids touching this: it is Codex's own bundled
# skill namespace, not ours to manage.
PROTECTED_SKILL_DIRS = {".system"}


def _compose_codex_context() -> str:
    """The managed block written into ~/.codex/AGENTS.md.

    Path-references the operator's real memory files rather than
    inlining them: the files are the source of truth, they change on
    every `episteme sync`, and a copy here would silently rot.
    """
    memory = _cli.REPO_ROOT / "core" / "memory" / "global"
    digest = _cli._resolve_memory_file("runtime_digest")
    feedback = _cli._resolve_memory_file("agent_feedback")
    python_policy = _cli._resolve_memory_file("python_runtime_policy")
    return (
        "# episteme — operator governance contract\n\n"
        "Managed by `episteme sync`. Edit the source of truth in\n"
        f"`{memory}`, not this block — changes here are overwritten.\n\n"
        "## Always-on\n\n"
        f"- `{digest}` — the single control surface: precedence contract,\n"
        "  hard rules, decision posture, session flow.\n"
        f"- `{feedback}` — behavioral rules learned across sessions\n"
        "  (includes: never add AI-attribution trailers to commits or PRs).\n"
        f"- `{python_policy}` — Python runtime policy for this machine.\n\n"
        "## Read on demand\n\n"
        f"- `{memory / 'cognitive_profile.md'}` — mental models + Decision Protocol\n"
        f"- `{memory / 'workflow_policy.md'}` — the five stages, signal-over-noise rules\n"
        f"- `{memory / 'operator_profile.md'}` — per-axis operator profile\n"
        f"- `{memory / 'overview.md'}` — project topology\n\n"
        "## Precedence with the rest of this file\n\n"
        "This block is additive. Where a directive elsewhere in AGENTS.md\n"
        "conflicts with the governance posture above — most likely around\n"
        "autonomy versus gating irreversible operations — the operator's\n"
        "own text in this file wins, and the conflict should be raised\n"
        "rather than silently resolved in either direction.\n"
    )


def sync() -> bool:
    """Mount operator context + managed skills into ~/.codex if present.

    Returns True when Codex was found and synced, False when it is not
    installed. Never removes or rewrites operator-authored content.
    """
    codex_root = _cli.HOME / ".codex"
    if not codex_root.exists():
        return False

    skills_dst = codex_root / "skills"
    for skill_dir in _cli._managed_skills():
        if skill_dir.name in PROTECTED_SKILL_DIRS:
            continue
        _cli._copy_tree(skill_dir, skills_dst / skill_dir.name)

    # AGENTS.md is Codex's project contract AND the operator's own file.
    # Managed-region write: everything outside the markers is preserved.
    _cli._write_managed_file(
        codex_root / "AGENTS.md",
        _compose_codex_context(),
        marker=CODEX_MARKER,
    )
    return True


__all__ = ["sync", "CODEX_MARKER", "PROTECTED_SKILL_DIRS"]
