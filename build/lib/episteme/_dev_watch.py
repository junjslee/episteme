"""Tier 3 — `episteme dev watch` source-to-plugin-cache file watcher.

Polls source paths (kernel/, core/hooks/, core/blueprints/, hooks/) for
mtime changes and propagates to the plugin cache, relieving the friction
loop where source edits to ``core/hooks/*.py`` do not reach the live
runtime hook surface until manual ``episteme sync`` plus a manual rsync
of ``core/hooks/`` to ``~/.claude/plugins/cache/episteme/...`` are run.

This is NOT a long-running daemon. It runs only when ``episteme dev
watch`` is explicitly invoked by the operator. It does not touch the
source — it mirrors source → plugin-cache.

Discipline:

- **Atomic write**: every copy goes through a tempfile + ``os.replace``.
  The plugin cache is never left in a half-copied state, even on watcher
  crash mid-flight.
- **Syntax-validation guard**: ``.py`` files are parsed with
  ``ast.parse`` before copying. A mid-edit syntactically broken file is
  NOT propagated; the watcher skips it and tries again next tick.
- **Polling**: no ``watchdog`` / ``inotify`` dependency (pyproject.toml
  keeps an empty ``dependencies`` list). CPU work is bounded by the
  interval (default 2.0s) — operators on tight CPU budgets can dial it
  to 5-10s.
- **One-shot mode**: ``--once`` performs a full sync (every source file
  copied unconditionally), useful for the first sync after a fresh
  ``episteme sync``. The continuous watch mode mtime-gates after that.

Closes Finding F3 from ``docs/PRIVATE_ANALYSIS_PI_VS_EPISTEME.md`` —
the friction tax on kernel-edit-while-the-kernel-is-the-friction.
"""
from __future__ import annotations

import ast
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

DEFAULT_INTERVAL_SECONDS = 2.0

DEFAULT_SOURCE_PATHS: tuple[str, ...] = (
    "core/hooks",
    "core/blueprints",
    "kernel",
    "hooks",
)

DEFAULT_PLUGIN_CACHE = (
    Path.home() / ".claude" / "plugins" / "cache" / "episteme" / "episteme"
)


@dataclass(frozen=True)
class FileSnapshot:
    """Snapshot of a single source path's mtime + size for change detection."""
    mtime: float
    size: int


@dataclass
class WatchState:
    snapshots: dict[Path, FileSnapshot] = field(default_factory=dict)


# ---------- Helpers -----------------------------------------------------------


def resolve_plugin_cache_target(target_arg: Path | None = None) -> Path | None:
    """Resolve the plugin-cache target. If ``target_arg`` is supplied,
    use that path directly. Otherwise look for the most recent versioned
    subdirectory under DEFAULT_PLUGIN_CACHE. Returns None if no target
    can be resolved."""
    if target_arg is not None:
        return Path(target_arg)
    if not DEFAULT_PLUGIN_CACHE.exists():
        return None
    versioned = [p for p in DEFAULT_PLUGIN_CACHE.iterdir() if p.is_dir()]
    if not versioned:
        return None
    versioned.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return versioned[0]


def is_python_syntactically_valid(path: Path) -> bool:
    if path.suffix != ".py":
        return True
    try:
        ast.parse(path.read_text())
        return True
    except (SyntaxError, OSError):
        return False


def collect_source_files(source_root: Path) -> list[Path]:
    """All files under ``source_root`` (recursive). Skips hidden paths
    (any path component starting with ``.``) and ``__pycache__``."""
    files: list[Path] = []
    if not source_root.exists():
        return files
    for path in source_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        if "__pycache__" in path.parts:
            continue
        files.append(path)
    return files


def snapshot_file(path: Path) -> FileSnapshot:
    stat = path.stat()
    return FileSnapshot(mtime=stat.st_mtime, size=stat.st_size)


def atomic_copy(src: Path, dst: Path) -> None:
    """Copy ``src`` → ``dst`` atomically (write to temp + rename). Creates
    parent dirs as needed. Preserves mtime via ``shutil.copy2``."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    shutil.copy2(src, tmp)
    os.replace(tmp, dst)


# ---------- Detection + propagation -------------------------------------------


def detect_changes(
    project_root: Path,
    source_paths: Iterable[str],
    state: WatchState,
) -> list[tuple[Path, str]]:
    """Compare current mtime/size to ``state.snapshots``. Returns list of
    ``(relative_path_from_project_root, change_kind)`` where ``kind`` ∈
    ``{'new', 'changed'}``. Updates ``state.snapshots`` in place."""
    changed: list[tuple[Path, str]] = []
    for source_path_str in source_paths:
        source_root = project_root / source_path_str
        for f in collect_source_files(source_root):
            relative = f.relative_to(project_root)
            current = snapshot_file(f)
            prior = state.snapshots.get(relative)
            if prior is None:
                state.snapshots[relative] = current
                changed.append((relative, "new"))
            elif (current.mtime, current.size) != (prior.mtime, prior.size):
                state.snapshots[relative] = current
                changed.append((relative, "changed"))
    return changed


def propagate_changes(
    project_root: Path,
    target_root: Path,
    changes: list[tuple[Path, str]],
    on_skip: Callable[[Path, str], None] | None = None,
) -> int:
    """Copy each changed file from ``project_root/relative`` to
    ``target_root/relative``. Skip files that fail syntactic validation
    (``.py`` files only). Returns count copied (skipped do not count)."""
    count = 0
    for relative, _kind in changes:
        src = project_root / relative
        if not src.exists():
            continue
        if not is_python_syntactically_valid(src):
            if on_skip is not None:
                on_skip(src, "syntactically invalid")
            continue
        dst = target_root / relative
        atomic_copy(src, dst)
        count += 1
    return count


def collect_all_files(
    project_root: Path,
    source_paths: Iterable[str],
) -> list[tuple[Path, str]]:
    """Return every file under ``source_paths`` as a ``(relative, 'new')``
    tuple. Used by --once mode to force a full unconditional sync."""
    items: list[tuple[Path, str]] = []
    for source_path_str in source_paths:
        source_root = project_root / source_path_str
        for f in collect_source_files(source_root):
            items.append((f.relative_to(project_root), "new"))
    return items


# ---------- Entry point -------------------------------------------------------


def run_dev_watch(
    *,
    project_root: Path | None = None,
    target: Path | None = None,
    paths: Iterable[str] = DEFAULT_SOURCE_PATHS,
    interval: float = DEFAULT_INTERVAL_SECONDS,
    once: bool = False,
    quiet: bool = False,
    out=None,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_ticks: int | None = None,
) -> int:
    if out is None:
        out = sys.stdout
    project_root = (project_root or Path.cwd()).resolve()
    target_root = resolve_plugin_cache_target(target)
    if target_root is None:
        out.write(
            "[episteme dev watch] error: no plugin-cache target found; "
            "pass --target=<path> or check ~/.claude/plugins/cache/episteme/\n"
        )
        out.flush()
        return 1
    target_root = target_root.resolve()
    paths = tuple(paths)

    if not quiet:
        out.write(
            f"[episteme dev watch] project: {project_root}\n"
            f"  paths:    {', '.join(paths)}\n"
            f"  target:   {target_root}\n"
            f"  interval: {interval}s\n"
            f"  mode:     {'once (unconditional full sync)' if once else 'continuous (Ctrl-C to stop)'}\n"
        )
        out.flush()

    if once:
        all_files = collect_all_files(project_root, paths)
        copied = propagate_changes(
            project_root, target_root, all_files,
            on_skip=_make_skip_logger(out, quiet),
        )
        if not quiet:
            out.write(
                f"[episteme dev watch] one-shot: copied {copied} of "
                f"{len(all_files)} file(s)\n"
            )
            out.flush()
        return 0

    state = WatchState()
    detect_changes(project_root, paths, state)  # prime baseline; do not propagate
    ticks = 0
    try:
        while True:
            sleep_fn(interval)
            ticks += 1
            changes = detect_changes(project_root, paths, state)
            if changes:
                copied = propagate_changes(
                    project_root, target_root, changes,
                    on_skip=_make_skip_logger(out, quiet),
                )
                if not quiet:
                    out.write(
                        f"[episteme dev watch] copied {copied} of "
                        f"{len(changes)} change(s)\n"
                    )
                    out.flush()
            if max_ticks is not None and ticks >= max_ticks:
                return 0
    except KeyboardInterrupt:
        if not quiet:
            out.write("\n[episteme dev watch] stopped\n")
            out.flush()
        return 0


def _make_skip_logger(out, quiet: bool) -> Callable[[Path, str], None] | None:
    if quiet:
        return None

    def _log(path: Path, reason: str) -> None:
        out.write(f"[episteme dev watch] skip {path.name}: {reason}\n")
        out.flush()

    return _log
