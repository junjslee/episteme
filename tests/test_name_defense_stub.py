"""The episteme-kernel name-defense stub stays honest (§9.2, Event 143).

The stub exists to hold the PyPI name, and its whole contract is that it
CANNOT be mistaken for the product: importing it must fail loudly with
pointers to the two real install paths. These tests pin that contract and
the package metadata so a future edit can't quietly turn the stub into a
half-working install path (§9.2 option (b) is a separate decision).
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STUB_ROOT = REPO_ROOT / "packaging" / "episteme-kernel-stub"


class NameDefenseStub(unittest.TestCase):
    def test_stub_module_refuses_import_with_real_paths_named(self):
        init = STUB_ROOT / "src" / "episteme_kernel" / "__init__.py"
        spec = importlib.util.spec_from_file_location("episteme_kernel_stub_probe", init)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        with self.assertRaises(ImportError) as ctx:
            spec.loader.exec_module(module)
        message = str(ctx.exception)
        self.assertIn("name-defense stub", message)
        self.assertIn("/plugin marketplace add junjslee/episteme", message)
        self.assertIn("git clone https://github.com/junjslee/episteme", message)

    def test_stub_metadata_claims_the_name_and_nothing_more(self):
        pyproject = (STUB_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('name = "episteme-kernel"', pyproject)
        self.assertIn('version = "0.0.1"', pyproject)
        self.assertIn("Development Status :: 1 - Planning", pyproject)
        # The stub must not grow entry points or dependencies — either
        # would make it look like a real install unit.
        self.assertNotIn("[project.scripts]", pyproject)
        self.assertNotIn("dependencies", pyproject)

    def test_stub_is_not_part_of_the_main_package_tree(self):
        # The main pyproject must not pull packaging/ into its build; the
        # stub is a sibling artifact, published by the operator only.
        main_pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn("episteme-kernel-stub", main_pyproject)
        self.assertNotIn("packaging/", main_pyproject)


if __name__ == "__main__":
    unittest.main()
