"""CP-EXAMPLES-SCHEMA-PARITY-01 — structural-parity guard for the
`core/memory/global/examples/*.example.md` onboarding templates.

The example templates are what a fresh clone seeds personal memory from
(`episteme init`). They must stay structurally at parity with the canonical
operator memory files so the onboarding surface never drifts behind the schema
the canonical files actually use. The canonical files were brought to v2 parity
in Event 77; this module is the regression guard that keeps them there — it does
NOT edit either side.

What "parity" means here is *structural presence*, never value:

- `operator_profile.example.md` — every axis key the schema defines (6 process,
  9 cognitive, plus `expertise_map`) is present, and each present axis carries
  its metadata fields. Presence only: canonical `confidence: elicited` vs example
  `confidence: stub` is by-design and must NOT flag.
- `cognitive_profile.example.md` / `workflow_policy.example.md` — the canonical
  `## ` (H2) section set is a *subset* of the example's H2 set (the example may
  add onboarding-only sections). The example's ` (Example)` title-suffix is
  normalized away before comparison. H3 bodies are not compared.
- `agent_feedback.example.md` — exists and carries its three H2 sections.

The canonical H2 section lists for cognitive_profile / workflow_policy are
derived *dynamically* by parsing the canonical files, so the guard tracks the
canonical surface automatically as it evolves. The 16-axis operator-profile enum
is hardcoded (source: kernel/OPERATOR_PROFILE_SCHEMA.md §4a/4b/4c) because it is
the schema contract the guard exists to pin — deriving it from canonical would
let a canonical deletion silently relax the guard.

Canonical files are symlinks into the private repo (~/episteme-private). When the
private repo is absent the symlink targets are unreadable; rather than emit a
traceback the checker returns EXIT_USAGE with a clear message.

Exit codes:
- EXIT_OK    (0) — examples at parity.
- EXIT_DRIFT (1) — one or more parity violations found.
- EXIT_USAGE (64) — canonical files unreadable (private repo absent?) or bad CLI.

Parsing is stdlib-only: regex for `## ` headers and for YAML axis keys appearing
at column 0 inside fenced code blocks.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_USAGE = 64

# --- operator_profile axis enum (schema §4a/4b/4c) -------------------------
# Hardcoded on purpose — this is the schema contract the guard pins. Deriving
# it from the canonical file would let a canonical deletion silently relax the
# guard, defeating the regression purpose.
PROCESS_AXES = (
    "planning_strictness",
    "risk_tolerance",
    "testing_rigor",
    "parallelism_preference",
    "documentation_rigor",
    "automation_level",
)
COGNITIVE_AXES = (
    "dominant_lens",
    "noise_signature",
    "abstraction_entry",
    "decision_cadence",
    "explanation_depth",
    "feedback_mode",
    "uncertainty_tolerance",
    "asymmetry_posture",
    "fence_discipline",
)
EXPERTISE_KEY = "expertise_map"
ALL_AXES = PROCESS_AXES + COGNITIVE_AXES + (EXPERTISE_KEY,)

# Metadata fields every scored axis must carry. Most axes expose a scalar
# `value`; two are typed and expose sub-keys instead.
COMMON_META = ("confidence", "last_observed", "evidence_refs", "note")
TYPED_AXIS_SUBKEYS = {
    "noise_signature": ("primary", "secondary"),
    "decision_cadence": ("tempo", "commit_after"),
}

# agent_feedback canonical H2 set (small + stable; the file has no fenced YAML to
# parse, so its three sections are the parity contract).
AGENT_FEEDBACK_H2 = (
    "How to classify new agent-learned feedback",
    "Universal rules",
    "Universal-principled rules",
)

_H2_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_EXAMPLE_SUFFIX_RE = re.compile(r"\s*\(Example\)\s*$", re.IGNORECASE)
# A YAML key at column 0 (no leading whitespace) — an axis declaration inside a
# fenced block. `^` is line-anchored under re.MULTILINE.
_COL0_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*):", re.MULTILINE)
_FENCE_RE = re.compile(r"^```", re.MULTILINE)


def _read_text(path: Path) -> str:
    """Read a memory file. Raises OSError (incl. FileNotFoundError) when the
    path — or, for a symlink, its target — is unreadable. Callers translate
    that into EXIT_USAGE rather than a traceback."""
    return path.read_text(encoding="utf-8")


def _h2_sections(text: str, *, normalize_suffix: bool = False) -> set[str]:
    """Return the set of `## ` H2 titles in `text`. When `normalize_suffix`,
    strip a trailing ` (Example)` from each title so the example surface can
    carry it without false-flagging."""
    titles = set()
    for raw in _H2_RE.findall(text):
        title = raw.strip()
        if normalize_suffix:
            title = _EXAMPLE_SUFFIX_RE.sub("", title).strip()
        titles.add(title)
    return titles


def _fenced_regions(text: str) -> str:
    """Concatenate the contents of every ``` ... ``` fenced block in `text`.

    Axis keys are only meaningful inside the YAML fences; restricting the
    column-0-key scan to fenced regions avoids matching prose lines like a
    Markdown heading's residue or an unfenced `note:`-style line. Unterminated
    final fences are tolerated (treated as running to EOF)."""
    out: list[str] = []
    inside = False
    start = 0
    for m in _FENCE_RE.finditer(text):
        if not inside:
            start = m.end()
            inside = True
        else:
            out.append(text[start:m.start()])
            inside = False
    if inside:
        out.append(text[start:])
    return "\n".join(out)


def _axis_block(fenced: str, axis: str) -> str | None:
    """Return the text block for `axis` — from its column-0 declaration up to
    the next column-0 key (or EOF). Returns None if the axis key is absent."""
    decls = list(_COL0_KEY_RE.finditer(fenced))
    for i, m in enumerate(decls):
        if m.group(1) == axis:
            start = m.start()
            end = decls[i + 1].start() if i + 1 < len(decls) else len(fenced)
            return fenced[start:end]
    return None


def _subkey_present(block: str, subkey: str) -> bool:
    """True if `subkey:` appears as an indented child line inside `block`."""
    pat = re.compile(r"^[ \t]+" + re.escape(subkey) + r":", re.MULTILINE)
    return bool(pat.search(block))


def _check_operator_profile(canonical: Path, example: Path) -> list[str]:
    """Compare the example operator profile against the hardcoded axis enum.

    Presence-only: every axis must be declared, and each scored axis must carry
    its metadata fields (the typed axes via their sub-keys, all axes via the
    common metadata). `expertise_map` is a container, not a scored axis, so it
    only needs to be present. Canonical is read solely to confirm readability —
    the enum is the contract, not the canonical file's current axis list."""
    problems: list[str] = []
    # Touch canonical so an absent private repo surfaces as EXIT_USAGE upstream.
    _read_text(canonical)
    text = _read_text(example)
    fenced = _fenced_regions(text)

    for axis in ALL_AXES:
        block = _axis_block(fenced, axis)
        if block is None:
            problems.append(
                f"operator_profile.example.md: missing axis key '{axis}'"
            )
            continue
        if axis == EXPERTISE_KEY:
            # Container, not a scored axis — presence is the whole contract.
            continue
        if axis in TYPED_AXIS_SUBKEYS:
            for sub in TYPED_AXIS_SUBKEYS[axis]:
                if not _subkey_present(block, sub):
                    problems.append(
                        f"operator_profile.example.md: axis '{axis}' "
                        f"missing typed sub-key '{sub}'"
                    )
        else:
            if not _subkey_present(block, "value"):
                problems.append(
                    f"operator_profile.example.md: axis '{axis}' "
                    f"missing field 'value'"
                )
        for field in COMMON_META:
            if not _subkey_present(block, field):
                problems.append(
                    f"operator_profile.example.md: axis '{axis}' "
                    f"missing metadata field '{field}'"
                )
    return problems


def _check_h2_subset(
    canonical: Path, example: Path, label: str
) -> list[str]:
    """Confirm the canonical H2 section set is a subset of the example's
    (suffix-normalized) H2 set. The example may add onboarding-only sections;
    it may not drop a canonical one. H3 bodies are not compared."""
    canonical_h2 = _h2_sections(_read_text(canonical))
    example_h2 = _h2_sections(_read_text(example), normalize_suffix=True)
    missing = sorted(canonical_h2 - example_h2)
    return [f"{label}: missing canonical section '## {s}'" for s in missing]


def _check_agent_feedback(example: Path) -> list[str]:
    """Confirm agent_feedback.example.md exists and carries its 3 H2s. This
    example has no canonical symlink partner in the parity set, so its contract
    is the hardcoded section list."""
    if not example.exists():
        return ["agent_feedback.example.md: file is absent"]
    h2 = _h2_sections(_read_text(example), normalize_suffix=True)
    return [
        f"agent_feedback.example.md: missing section '## {s}'"
        for s in AGENT_FEEDBACK_H2
        if s not in h2
    ]


def check_examples(repo_root: Path) -> tuple[int, list[str]]:
    """Run every parity check. Returns (exit_code, report_lines).

    EXIT_USAGE when a canonical file is unreadable (private repo absent or a
    broken symlink) — never a traceback. EXIT_DRIFT when any parity violation
    is found. EXIT_OK when the examples are at parity."""
    glob = repo_root / "core" / "memory" / "global"
    examples = glob / "examples"

    canonical_operator = glob / "operator_profile.md"
    canonical_cognitive = glob / "cognitive_profile.md"
    canonical_workflow = glob / "workflow_policy.md"

    ex_operator = examples / "operator_profile.example.md"
    ex_cognitive = examples / "cognitive_profile.example.md"
    ex_workflow = examples / "workflow_policy.example.md"
    ex_agent_feedback = examples / "agent_feedback.example.md"

    problems: list[str] = []
    try:
        problems += _check_operator_profile(canonical_operator, ex_operator)
        problems += _check_h2_subset(
            canonical_cognitive, ex_cognitive, "cognitive_profile.example.md"
        )
        problems += _check_h2_subset(
            canonical_workflow, ex_workflow, "workflow_policy.example.md"
        )
    except (FileNotFoundError, OSError) as exc:
        return (
            EXIT_USAGE,
            [
                "canonical unreadable (private repo absent?): "
                f"{exc.__class__.__name__}: {exc}"
            ],
        )

    # agent_feedback has no canonical partner — its check never touches the
    # private repo, so run it after the canonical reads.
    problems += _check_agent_feedback(ex_agent_feedback)

    if problems:
        return EXIT_DRIFT, problems
    return EXIT_OK, ["examples at v2 schema parity"]


def _print_report(code: int, lines: list[str], json_out: bool) -> None:
    if json_out:
        status = {
            EXIT_OK: "ok",
            EXIT_DRIFT: "drift",
            EXIT_USAGE: "usage",
        }.get(code, "usage")
        print(json.dumps(
            {"exit_code": code, "status": status, "report": lines},
            indent=2,
            sort_keys=True,
        ))
        return
    print("episteme — examples schema-parity guard (CP-EXAMPLES-SCHEMA-PARITY-01)")
    print("=" * 60)
    if code == EXIT_OK:
        print("PASS — examples at v2 schema parity.")
    elif code == EXIT_DRIFT:
        print(f"DRIFT — {len(lines)} parity violation(s):")
        for line in lines:
            print(f"  - {line}")
    else:
        print("USAGE ERROR:")
        for line in lines:
            print(f"  - {line}")


def run_verify_examples(json_out: bool = False) -> int:
    """Thin CLI runner. Resolves the repo root from this module's location,
    runs the parity checks, prints the report, and returns the exit code."""
    repo_root = Path(__file__).resolve().parents[2]
    code, lines = check_examples(repo_root)
    _print_report(code, lines, json_out)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="episteme verify-examples",
        description=(
            "Structural-parity guard: confirm core/memory/global/examples/"
            "*.example.md stay at v2 schema parity with the canonical memory "
            "files (CP-EXAMPLES-SCHEMA-PARITY-01)."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a human-readable report",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # argparse exits 2 on bad args; normalize to EXIT_USAGE.
        return EXIT_USAGE
    return run_verify_examples(json_out=args.json)


if __name__ == "__main__":
    sys.exit(main())
