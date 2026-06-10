#!/usr/bin/env python3
"""UserPromptSubmit hook — conclusion-shape detection (Event 139 · v2.0).

The Epistemic Engine's primary decision shape is a load-bearing
conclusion handed to the operator (DESIGN_V2_0 § 4) — but until this
hook, only tool-level ops had triggers: the gate guarded `git push`
while the recommendation that *caused* the push went unexamined. This
hook detects the shape at its origin: the operator's own prompt.

Mechanism: a conservative, positive-system lexicon of decision-question
shapes (EN + KR). On a hit in a kernel-governed project (`.episteme/`
present), it (a) writes a per-prompt conclusion-pending marker that
`conclusion_gate.py` reads at Stop, and (b) injects ONE factual context
line naming the interrogation path. Misses are silent; ungoverned
projects are silent; a prompt arriving while a fresh interrogation
verdict already exists is silent (the work is already done).

Alarm-fatigue discipline (Event 137 lesson): the lexicon is tight by
design — a false negative costs nothing (the agent can still
interrogate voluntarily); a false positive costs one context line and
at most one Stop nudge. Tone is factual statements, not imperatives,
per the hooks doctrine.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))


MARKER_FILENAME = "conclusion-pending.json"

# Positive system (named consciously per the rule-shape discipline):
# only these shapes trigger; everything else is default-silent.
CONCLUSION_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("should-we", re.compile(r"\bshould\s+(?:we|i|you)\b", re.I)),
    ("what-should", re.compile(r"\bwhat\s+should\s+(?:we|i)\b", re.I)),
    ("recommend", re.compile(
        r"\b(?:do|would)\s+you\s+recommend\b|\byour\s+recommendation\b",
        re.I,
    )),
    ("is-it-safe", re.compile(
        r"\bis\s+it\s+(?:safe|correct|right|ok(?:ay)?|wise)\s+to\b", re.I,
    )),
    ("which-better", re.compile(
        r"\bwhich\s+(?:one|option|approach|design|path|library|tool|"
        r"model|way|stack)\b",
        re.I,
    )),
    ("decide-between", re.compile(
        r"\b(?:decide|decision|choose|choosing|pick)\s+between\b", re.I,
    )),
    ("evaluate-whether", re.compile(
        r"\b(?:evaluate|assess|judge)\s+whether\b", re.I,
    )),
    ("pros-cons", re.compile(
        r"\bpros\s+and\s+cons\b|\btrade-?offs?\s+of\b", re.I,
    )),
    # Any verb stem + ~야 modal ("해야/가야/봐야 할까") — the decision
    # shape lives in the ending, not the stem.
    ("ko-should", re.compile(
        r"[가-힣]야\s*(?:할까|하나요|할지|되나)|하는\s*게\s*맞"
    )),
    ("ko-recommend", re.compile(r"추천해|추천할|권장해")),
    ("ko-which-better", re.compile(
        r"어떤\s*(?:게|것이)\s*(?:더\s*)?(?:나을|좋을|낫)"
    )),
    ("ko-okay", re.compile(r"괜찮을까|괜찮은가|괜찮나")),
)


def detect_conclusion_shape(prompt: str) -> str | None:
    """Return the matched shape label, or None."""
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    for label, pattern in CONCLUSION_PATTERNS:
        if pattern.search(prompt):
            return label
    return None


def _canonical_project_root(cwd: Path) -> Path | None:
    """Nearest ancestor holding `.episteme/`, or None when the project
    is not kernel-governed (this hook is global; ungoverned projects
    get zero noise and zero state files)."""
    probe = cwd.resolve() if cwd.exists() else cwd
    for _ in range(8):
        if (probe / ".episteme").is_dir():
            return probe
        if probe.parent == probe:
            return None
        probe = probe.parent
    return None


def marker_path(root: Path) -> Path:
    return root / ".episteme" / MARKER_FILENAME


def write_marker(root: Path, session_id: str, prompt: str, shape: str) -> None:
    payload = {
        "session_id": session_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "prompt_head": prompt.strip()[:160],
        "shape": shape,
        "nudged": False,
    }
    try:
        marker_path(root).write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass  # marker bookkeeping never blocks a prompt


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if not isinstance(payload, dict):
        return 0

    prompt = str(payload.get("prompt") or "")
    shape = detect_conclusion_shape(prompt)
    if shape is None:
        return 0

    import os
    cwd = Path(payload.get("cwd") or os.getcwd())
    root = _canonical_project_root(cwd)
    if root is None:
        return 0

    # A fresh verdict (ok or stop) means the interrogation already ran
    # this cycle — no marker, no context line.
    try:
        import _interrogation  # type: ignore  # pyright: ignore[reportMissingImports]
        i_status, _ = _interrogation.artifact_status(root)
        if i_status in ("ok", "stop"):
            return 0
    except Exception:
        pass

    session_id = str(payload.get("session_id") or "")
    write_marker(root, session_id, prompt, shape)

    context = (
        f"This prompt asks for a load-bearing conclusion "
        f"(shape: {shape}). The epistemic-interrogation protocol applies "
        f"to conclusion-class decisions: decompose into tiered claims, "
        f"verify load-bearing claims in a fresh context against external "
        f"evidence, argue the opposition, name the weakest link, "
        f"pre-commit a disconfirmation — verdict artifact at "
        f".episteme/interrogation.json. A conclusion delivered without "
        f"it will receive one reminder at turn end."
    )
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
