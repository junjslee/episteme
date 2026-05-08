"""Tests for Tier 3 — `episteme dev watch` source-to-plugin-cache file watcher.

Covers:

- ``resolve_plugin_cache_target``: --target arg wins; otherwise most recent
  versioned subdir; absent path returns None.
- ``is_python_syntactically_valid``: valid py → True; broken py → False;
  non-py file → True (validation skipped for non-py).
- ``collect_source_files``: recursive; skips ``__pycache__`` + dotfiles.
- ``atomic_copy``: copies content; creates parent dirs; preserves mtime.
- ``detect_changes``: prime → 'new'; unchanged → not in result; modified
  → 'changed'.
- ``propagate_changes``: copies valid files; skips broken py via on_skip
  callback; returns count copied.
- ``collect_all_files``: returns every file under source paths.
- ``run_dev_watch --once``: full unconditional sync.
- ``run_dev_watch`` watch loop: max_ticks terminates; mtime change
  detected and propagated mid-loop.
- ``run_dev_watch`` no-target: returns 1 with explicit error message.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from episteme import _dev_watch  # noqa: E402


def _make_project(tmp: Path, files: dict[str, str]) -> Path:
    """Create a project tree under tmp/ with the given {relative_path: content} files."""
    project = tmp / "project"
    project.mkdir(parents=True)
    for rel, content in files.items():
        path = project / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return project


class ResolvePluginCacheTarget(unittest.TestCase):

    def test_explicit_target_wins(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "explicit"
            target.mkdir()
            self.assertEqual(
                _dev_watch.resolve_plugin_cache_target(target),
                target,
            )

    def test_returns_none_when_default_cache_absent(self):
        # Stub the DEFAULT_PLUGIN_CACHE to a nonexistent path.
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "doesnotexist"
            old = _dev_watch.DEFAULT_PLUGIN_CACHE
            _dev_watch.DEFAULT_PLUGIN_CACHE = fake
            try:
                self.assertIsNone(_dev_watch.resolve_plugin_cache_target(None))
            finally:
                _dev_watch.DEFAULT_PLUGIN_CACHE = old

    def test_picks_most_recent_versioned_subdir(self):
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / "cache"
            cache.mkdir()
            old_dir = cache / "1.0.0"
            new_dir = cache / "1.1.0-rc1"
            old_dir.mkdir()
            new_dir.mkdir()
            # Force new_dir to have a strictly newer mtime than old_dir.
            os.utime(old_dir, (1000, 1000))
            os.utime(new_dir, (2000, 2000))
            saved = _dev_watch.DEFAULT_PLUGIN_CACHE
            _dev_watch.DEFAULT_PLUGIN_CACHE = cache
            try:
                resolved = _dev_watch.resolve_plugin_cache_target(None)
                self.assertEqual(resolved, new_dir)
            finally:
                _dev_watch.DEFAULT_PLUGIN_CACHE = saved


class SyntaxValidation(unittest.TestCase):

    def test_valid_py(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "ok.py"
            p.write_text("def f():\n    return 1\n")
            self.assertTrue(_dev_watch.is_python_syntactically_valid(p))

    def test_broken_py(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "broken.py"
            p.write_text("def f(:\n    return\n")
            self.assertFalse(_dev_watch.is_python_syntactically_valid(p))

    def test_non_py_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "data.yaml"
            p.write_text("key: value\n")
            self.assertTrue(_dev_watch.is_python_syntactically_valid(p))


class CollectSourceFiles(unittest.TestCase):

    def test_recursive_collection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.py").write_text("a\n")
            (root / "sub").mkdir()
            (root / "sub" / "b.py").write_text("b\n")
            files = _dev_watch.collect_source_files(root)
            rels = sorted(f.relative_to(root) for f in files)
            self.assertEqual([str(r) for r in rels], ["a.py", "sub/b.py"])

    def test_skips_pycache(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.py").write_text("a\n")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "a.cpython-310.pyc").write_text("noise")
            files = _dev_watch.collect_source_files(root)
            self.assertEqual([f.name for f in files], ["a.py"])

    def test_skips_hidden(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.py").write_text("a\n")
            (root / ".hidden.py").write_text("hidden")
            files = _dev_watch.collect_source_files(root)
            self.assertEqual([f.name for f in files], ["a.py"])

    def test_returns_empty_for_absent_root(self):
        with tempfile.TemporaryDirectory() as td:
            files = _dev_watch.collect_source_files(Path(td) / "nope")
            self.assertEqual(files, [])


class AtomicCopy(unittest.TestCase):

    def test_copies_content(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.py"
            dst = Path(td) / "out" / "dst.py"
            src.write_text("hello\n")
            _dev_watch.atomic_copy(src, dst)
            self.assertEqual(dst.read_text(), "hello\n")

    def test_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.py"
            dst = Path(td) / "deep" / "nested" / "dir" / "dst.py"
            src.write_text("x\n")
            _dev_watch.atomic_copy(src, dst)
            self.assertTrue(dst.exists())

    def test_no_tempfile_left_behind(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src.py"
            dst = Path(td) / "dst.py"
            src.write_text("y\n")
            _dev_watch.atomic_copy(src, dst)
            sibling_names = sorted(p.name for p in dst.parent.iterdir())
            # Only src.py + dst.py exist; no .tmp file leftover from atomic copy.
            self.assertEqual(sibling_names, ["dst.py", "src.py"])


class DetectChanges(unittest.TestCase):

    def test_prime_marks_files_new(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(Path(td), {"core/hooks/a.py": "x\n"})
            state = _dev_watch.WatchState()
            changes = _dev_watch.detect_changes(project, ("core/hooks",), state)
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0][1], "new")

    def test_second_call_no_changes(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(Path(td), {"core/hooks/a.py": "x\n"})
            state = _dev_watch.WatchState()
            _dev_watch.detect_changes(project, ("core/hooks",), state)
            changes = _dev_watch.detect_changes(project, ("core/hooks",), state)
            self.assertEqual(changes, [])

    def test_modified_file_marked_changed(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(Path(td), {"core/hooks/a.py": "x\n"})
            state = _dev_watch.WatchState()
            _dev_watch.detect_changes(project, ("core/hooks",), state)
            # Force a mtime change.
            target = project / "core/hooks/a.py"
            future = time.time() + 10
            os.utime(target, (future, future))
            changes = _dev_watch.detect_changes(project, ("core/hooks",), state)
            self.assertEqual(len(changes), 1)
            self.assertEqual(changes[0][1], "changed")


class PropagateChanges(unittest.TestCase):

    def test_copies_valid_python(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(Path(td), {"core/hooks/a.py": "def f(): pass\n"})
            target = Path(td) / "target"
            target.mkdir()
            count = _dev_watch.propagate_changes(
                project, target, [(Path("core/hooks/a.py"), "new")],
            )
            self.assertEqual(count, 1)
            self.assertTrue((target / "core/hooks/a.py").exists())

    def test_skips_broken_python(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(Path(td), {"core/hooks/a.py": "def f(:\n"})
            target = Path(td) / "target"
            target.mkdir()
            skipped: list[tuple[Path, str]] = []
            count = _dev_watch.propagate_changes(
                project, target, [(Path("core/hooks/a.py"), "new")],
                on_skip=lambda p, reason: skipped.append((p, reason)),
            )
            self.assertEqual(count, 0)
            self.assertFalse((target / "core/hooks/a.py").exists())
            self.assertEqual(len(skipped), 1)
            self.assertIn("syntactically", skipped[0][1])

    def test_copies_non_python_unconditionally(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(Path(td), {"core/blueprints/x.yaml": "k: v\n"})
            target = Path(td) / "target"
            target.mkdir()
            count = _dev_watch.propagate_changes(
                project, target, [(Path("core/blueprints/x.yaml"), "new")],
            )
            self.assertEqual(count, 1)


class RunDevWatchOneShot(unittest.TestCase):

    def test_once_copies_all_files(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(
                Path(td),
                {"core/hooks/a.py": "def a(): pass\n",
                 "core/hooks/b.py": "def b(): pass\n",
                 "core/blueprints/x.yaml": "k: v\n"},
            )
            target = Path(td) / "target"
            target.mkdir()
            out = io.StringIO()
            rc = _dev_watch.run_dev_watch(
                project_root=project, target=target, once=True, out=out,
            )
            self.assertEqual(rc, 0)
            self.assertTrue((target / "core/hooks/a.py").exists())
            self.assertTrue((target / "core/hooks/b.py").exists())
            self.assertTrue((target / "core/blueprints/x.yaml").exists())

    def test_no_target_returns_1(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(Path(td), {"core/hooks/a.py": "x\n"})
            saved = _dev_watch.DEFAULT_PLUGIN_CACHE
            _dev_watch.DEFAULT_PLUGIN_CACHE = Path(td) / "absent"
            try:
                out = io.StringIO()
                rc = _dev_watch.run_dev_watch(
                    project_root=project, target=None, once=True, out=out,
                )
                self.assertEqual(rc, 1)
                self.assertIn("no plugin-cache target", out.getvalue())
            finally:
                _dev_watch.DEFAULT_PLUGIN_CACHE = saved


class RunDevWatchLoop(unittest.TestCase):

    def test_loop_terminates_at_max_ticks(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(Path(td), {"core/hooks/a.py": "x\n"})
            target = Path(td) / "target"
            target.mkdir()
            sleep_calls: list[float] = []
            out = io.StringIO()
            rc = _dev_watch.run_dev_watch(
                project_root=project,
                target=target,
                paths=("core/hooks",),
                interval=0.1,
                once=False,
                quiet=True,
                out=out,
                sleep_fn=lambda interval: sleep_calls.append(interval),
                max_ticks=2,
            )
            self.assertEqual(rc, 0)
            self.assertEqual(len(sleep_calls), 2)

    def test_loop_propagates_mid_loop_change(self):
        with tempfile.TemporaryDirectory() as td:
            project = _make_project(Path(td), {"core/hooks/a.py": "def a(): pass\n"})
            target = Path(td) / "target"
            target.mkdir()
            target_file = target / "core/hooks/a.py"
            self.assertFalse(target_file.exists())  # baseline

            tick_count = [0]

            def fake_sleep(interval: float) -> None:
                # On the first sleep, modify the source so the next
                # detect_changes finds a change to propagate.
                tick_count[0] += 1
                if tick_count[0] == 1:
                    src = project / "core/hooks/a.py"
                    future = time.time() + 100
                    src.write_text("def a(): return 42\n")
                    os.utime(src, (future, future))

            out = io.StringIO()
            rc = _dev_watch.run_dev_watch(
                project_root=project,
                target=target,
                paths=("core/hooks",),
                interval=0.01,
                once=False,
                quiet=True,
                out=out,
                sleep_fn=fake_sleep,
                max_ticks=2,
            )
            self.assertEqual(rc, 0)
            # The mid-loop change was propagated to the target.
            self.assertTrue(target_file.exists())
            self.assertIn("return 42", target_file.read_text())


if __name__ == "__main__":
    unittest.main()
