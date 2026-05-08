"""Tests for Tier 2.1b — `episteme check new <name>` scaffolder.

Covers:

- Name validation (kebab-case regex; reject path traversal / leading hyphen / >64 chars / non-string).
- Template selection (block / advisory / surface).
- Output path resolution (default examples/checks/<name>.py vs --output).
- File creation + permissions (0755).
- Refuses to overwrite existing file without --force; overwrites with --force.
- Renders all three template types syntactically (compile() the rendered output).
"""
from __future__ import annotations

import compileall
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

# Make src/episteme importable from the test (mirrors other tests/ files).
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from episteme import _check_new  # noqa: E402


class NameValidation(unittest.TestCase):

    def test_valid_kebab(self):
        for name in ("my-check", "block-rmrf", "x", "abc123", "a-b-c-d"):
            with self.subTest(name=name):
                _check_new.validate_name(name)  # should not raise

    def test_valid_underscore(self):
        # underscores allowed per the regex (parity with the existing
        # examples/checks/require_disconfirmation_for_irreversible.py)
        _check_new.validate_name("require_disconfirmation_for_irreversible")

    def test_rejects_uppercase(self):
        with self.assertRaises(_check_new.CheckNewError):
            _check_new.validate_name("MyCheck")

    def test_rejects_leading_hyphen(self):
        with self.assertRaises(_check_new.CheckNewError):
            _check_new.validate_name("-leading")

    def test_rejects_path_traversal(self):
        for bad in ("../foo", "..", "foo/bar", "foo\\bar"):
            with self.subTest(name=bad):
                with self.assertRaises(_check_new.CheckNewError):
                    _check_new.validate_name(bad)

    def test_rejects_empty(self):
        with self.assertRaises(_check_new.CheckNewError):
            _check_new.validate_name("")

    def test_rejects_too_long(self):
        with self.assertRaises(_check_new.CheckNewError):
            _check_new.validate_name("a" * 65)

    def test_rejects_non_string(self):
        with self.assertRaises(_check_new.CheckNewError):
            _check_new.validate_name(None)  # type: ignore[arg-type]


class TemplateRendering(unittest.TestCase):

    def test_block_template_compiles(self):
        rendered = _check_new.render_template("my-check", "block")
        compile(rendered, "<my-check.py>", "exec")  # would raise on syntax error
        self.assertIn("PATTERN = re.compile", rendered)
        self.assertIn("[my-check] Refused: pattern match", rendered)
        self.assertIn("return 2", rendered)

    def test_advisory_template_compiles(self):
        rendered = _check_new.render_template("my-advisory", "advisory")
        compile(rendered, "<my-advisory.py>", "exec")
        self.assertIn("PROTECTED_PREFIXES", rendered)
        self.assertIn("[my-advisory] Advisory:", rendered)
        # Advisory must NOT block (exit 0).
        self.assertIn("return 0  # advisory only", rendered)

    def test_surface_template_compiles(self):
        rendered = _check_new.render_template("my-surface", "surface")
        compile(rendered, "<my-surface.py>", "exec")
        self.assertIn("REQUIRED_SURFACE_FIELD", rendered)
        self.assertIn("disconfirmation", rendered)
        self.assertIn("[my-surface] Refused: gated op", rendered)

    def test_unknown_type_raises(self):
        with self.assertRaises(_check_new.CheckNewError):
            _check_new.render_template("x", "nonexistent")

    def test_name_humanization(self):
        rendered = _check_new.render_template("block-foo-bar", "block")
        # NAME_HUMAN should be Title-Cased "Block Foo Bar".
        self.assertIn("Block Foo Bar", rendered)


class ScaffoldChecks(unittest.TestCase):

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_creates_file_in_default_location(self):
        path = _check_new.scaffold_check("my-check", "block", project_root=self.root)
        self.assertEqual(path, (self.root / "examples" / "checks" / "my-check.py").resolve())
        self.assertTrue(path.exists())
        # File has executable bits.
        self.assertEqual(path.stat().st_mode & 0o111, 0o111)

    def test_custom_output_path(self):
        target = self.root / "custom" / "subdir" / "x.py"
        path = _check_new.scaffold_check("my-check", "block", output=target)
        self.assertEqual(path, target.resolve())
        self.assertTrue(path.exists())

    def test_refuses_overwrite_without_force(self):
        target = self.root / "examples" / "checks" / "my-check.py"
        target.parent.mkdir(parents=True)
        target.write_text("# existing\n")
        with self.assertRaises(_check_new.CheckNewError):
            _check_new.scaffold_check("my-check", "block", project_root=self.root)
        # Existing file untouched.
        self.assertEqual(target.read_text(), "# existing\n")

    def test_overwrites_with_force(self):
        target = self.root / "examples" / "checks" / "my-check.py"
        target.parent.mkdir(parents=True)
        target.write_text("# existing\n")
        path = _check_new.scaffold_check(
            "my-check", "block", project_root=self.root, force=True,
        )
        self.assertEqual(path, target.resolve())
        # Existing file overwritten with template content.
        self.assertNotEqual(target.read_text(), "# existing\n")
        self.assertIn("PATTERN = re.compile", target.read_text())

    def test_invalid_name_does_not_create_file(self):
        with self.assertRaises(_check_new.CheckNewError):
            _check_new.scaffold_check("BadName", "block", project_root=self.root)
        # No file created.
        self.assertFalse((self.root / "examples").exists())


class ListTemplates(unittest.TestCase):

    def test_list_templates_returns_string_with_all_three(self):
        text = _check_new.list_templates()
        for t in _check_new.TEMPLATE_TYPES:
            self.assertIn(t, text)


if __name__ == "__main__":
    unittest.main()
