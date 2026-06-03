"""CP-EXAMPLES-SCHEMA-PARITY-01 — tests for `episteme verify-examples`.

Mirrors tests/test_tier1_audit_cli.py conventions: sys.path insert of src/,
tmp_path fixtures, capsys.

The committed examples are at v2 parity (Event 77) and must NOT be edited. The
drift tests build a throwaway repo tree under tmp_path (copying the real
canonical + example files) and mutate the copy, so the real tree is never
touched.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GLOBAL = _REPO_ROOT / "core" / "memory" / "global"
_EXAMPLES = _GLOBAL / "examples"


@pytest.fixture
def mod():
    src_dir = _REPO_ROOT / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from episteme import _verify_examples
    return _verify_examples


def _build_tmp_repo(tmp_path: Path) -> Path:
    """Materialize a self-contained copy of the parity surface under tmp_path.

    Canonical files are symlinks into the private repo; copy follows the
    symlink (`shutil.copy` reads through it) so the tmp tree is concrete and
    independent of the private repo's presence. Returns the tmp repo root."""
    glob = tmp_path / "core" / "memory" / "global"
    examples = glob / "examples"
    examples.mkdir(parents=True)

    for name in ("operator_profile.md", "cognitive_profile.md", "workflow_policy.md"):
        shutil.copy(_GLOBAL / name, glob / name)
    for name in (
        "operator_profile.example.md",
        "cognitive_profile.example.md",
        "workflow_policy.example.md",
        "agent_feedback.example.md",
    ):
        shutil.copy(_EXAMPLES / name, examples / name)
    return tmp_path


class TestVerifyExamplesCli:
    def test_committed_examples_pass(self, mod, capsys):
        # Runs against the REAL repo tree (run_verify_examples resolves repo
        # root from the module location). Requires the private repo to be
        # present; if absent it would return EXIT_USAGE — assert OK explicitly
        # so an absent-private-repo run fails loudly rather than masquerading.
        rc = mod.run_verify_examples()
        out = capsys.readouterr().out
        assert rc == mod.EXIT_OK, out
        assert "PASS" in out

    def test_committed_examples_check_examples_ok(self, mod):
        code, lines = mod.check_examples(_REPO_ROOT)
        assert code == mod.EXIT_OK, lines

    def test_deleted_axis_flags_drift(self, mod, tmp_path):
        repo = _build_tmp_repo(tmp_path)
        ex = repo / "core/memory/global/examples/operator_profile.example.md"
        text = ex.read_text(encoding="utf-8")
        # Remove the `fence_discipline:` declaration line + its `value:` line so
        # the axis key disappears from the fenced region.
        lines = [
            ln for ln in text.splitlines()
            if not ln.startswith("fence_discipline:")
        ]
        ex.write_text("\n".join(lines), encoding="utf-8")
        code, report = mod.check_examples(repo)
        assert code == mod.EXIT_DRIFT
        assert any("fence_discipline" in r for r in report)

    def test_deleted_canonical_section_flags_drift(self, mod, tmp_path):
        repo = _build_tmp_repo(tmp_path)
        ex = repo / "core/memory/global/examples/cognitive_profile.example.md"
        text = ex.read_text(encoding="utf-8")
        # Drop the example's "## Collaboration Stance" header so the canonical
        # section is no longer a subset.
        text = text.replace("## Collaboration Stance", "## Renamed Section")
        ex.write_text(text, encoding="utf-8")
        code, report = mod.check_examples(repo)
        assert code == mod.EXIT_DRIFT
        assert any("Collaboration Stance" in r for r in report)

    def test_flag_then_pass_roundtrip(self, mod, tmp_path):
        repo = _build_tmp_repo(tmp_path)
        ex = repo / "core/memory/global/examples/workflow_policy.example.md"
        original = ex.read_text(encoding="utf-8")
        # Break: drop a canonical section.
        broken = original.replace("## Parallelism Policy", "## Lanes Policy")
        ex.write_text(broken, encoding="utf-8")
        code, report = mod.check_examples(repo)
        assert code == mod.EXIT_DRIFT
        assert any("Parallelism Policy" in r for r in report)
        # Restore: parity returns.
        ex.write_text(original, encoding="utf-8")
        code, report = mod.check_examples(repo)
        assert code == mod.EXIT_OK, report

    def test_agent_feedback_absent_flagged(self, mod, tmp_path):
        repo = _build_tmp_repo(tmp_path)
        (repo / "core/memory/global/examples/agent_feedback.example.md").unlink()
        code, report = mod.check_examples(repo)
        assert code == mod.EXIT_DRIFT
        assert any("agent_feedback.example.md" in r and "absent" in r for r in report)

    def test_agent_feedback_missing_section_flagged(self, mod, tmp_path):
        repo = _build_tmp_repo(tmp_path)
        ex = repo / "core/memory/global/examples/agent_feedback.example.md"
        text = ex.read_text(encoding="utf-8")
        text = text.replace("## Universal-principled rules", "## Other rules")
        ex.write_text(text, encoding="utf-8")
        code, report = mod.check_examples(repo)
        assert code == mod.EXIT_DRIFT
        assert any("Universal-principled rules" in r for r in report)

    def test_title_suffix_not_flagged(self, mod, tmp_path):
        repo = _build_tmp_repo(tmp_path)
        ex = repo / "core/memory/global/examples/workflow_policy.example.md"
        text = ex.read_text(encoding="utf-8")
        # Append ' (Example)' to every canonical H2 in the example — the
        # normalizer must strip it so parity still holds.
        for h2 in (
            "## Standard Flow",
            "## Stage Definitions",
            "## Signal-over-Noise Rules",
            "## Risk and Autonomy Policy",
            "## Project Memory Contract",
            "## Parallelism Policy",
            "## Local Integration",
        ):
            text = text.replace(h2 + "\n", h2 + " (Example)\n")
        ex.write_text(text, encoding="utf-8")
        code, report = mod.check_examples(repo)
        assert code == mod.EXIT_OK, report

    def test_confidence_value_difference_not_flagged(self, mod, tmp_path):
        repo = _build_tmp_repo(tmp_path)
        ex = repo / "core/memory/global/examples/operator_profile.example.md"
        text = ex.read_text(encoding="utf-8")
        # Change a stub confidence to elicited and a value — presence is
        # unchanged, so the guard must stay green (value is by-design divergent).
        text = text.replace("confidence: stub", "confidence: elicited")
        text = text.replace("value: 3", "value: 5")
        ex.write_text(text, encoding="utf-8")
        code, report = mod.check_examples(repo)
        assert code == mod.EXIT_OK, report

    def test_canonical_unreadable_returns_usage(self, mod, tmp_path):
        # An empty tmp repo has no canonical files → reading them raises
        # FileNotFoundError, which must map to EXIT_USAGE, not a traceback.
        empty = tmp_path / "empty"
        (empty / "core/memory/global/examples").mkdir(parents=True)
        code, report = mod.check_examples(empty)
        assert code == mod.EXIT_USAGE
        assert any("canonical unreadable" in r for r in report)

    def test_cli_bad_arg_returns_usage(self, mod):
        rc = mod.main(["--nonexistent-flag"])
        assert rc == mod.EXIT_USAGE

    def test_json_output_parses(self, mod, capsys):
        rc = mod.run_verify_examples(json_out=True)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["exit_code"] == rc
        assert data["status"] == "ok"
        assert isinstance(data["report"], list)
