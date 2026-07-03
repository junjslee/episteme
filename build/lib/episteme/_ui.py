"""Zero-dep ANSI terminal rendering primitives.

The kernel's `dependencies = []` posture forbids hard dependencies on
Rich / Textual / Colorama. This module implements the small subset of
terminal rendering we actually need — boxes, colored headers, simple
sparklines, progress indicators — using only stdlib + ANSI escape
codes that work on every modern terminal.

Detection layers (rendering downgrades gracefully):
  1. EPISTEME_NO_RICH=1 in env  →  plain ASCII, no color, no boxes
  2. NO_COLOR set (per https://no-color.org)  →  plain ASCII, no color, boxes OK
  3. stdout is not a TTY (piped, redirected, CI)  →  plain ASCII, no color
  4. otherwise  →  full rendering

The module exposes:
  - `Renderer.is_rich()`  whether full rendering is active
  - `header(text)`  rendered section header
  - `box(text, title=None)`  rendered box around text
  - `colored(text, color)`  colored text or pass-through
  - `health_indicator(metric, thresholds)`  ●●● green/yellow/red dots
  - `sparkline(values)`  unicode-block sparkline for a sparse series
  - `progress(current, total, label)`  one-line progress indicator
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from typing import Iterable, List, Literal, Optional, Tuple


# ─── ANSI codes ──────────────────────────────────────────────────────────

ESC = "\033["
RESET = f"{ESC}0m"
BOLD = f"{ESC}1m"
DIM = f"{ESC}2m"

FG_BLACK = f"{ESC}30m"
FG_RED = f"{ESC}31m"
FG_GREEN = f"{ESC}32m"
FG_YELLOW = f"{ESC}33m"
FG_BLUE = f"{ESC}34m"
FG_MAGENTA = f"{ESC}35m"
FG_CYAN = f"{ESC}36m"
FG_WHITE = f"{ESC}37m"
FG_GREY = f"{ESC}90m"

BG_RED = f"{ESC}41m"
BG_GREEN = f"{ESC}42m"
BG_YELLOW = f"{ESC}43m"


Color = Literal[
    "red", "green", "yellow", "blue", "magenta", "cyan", "grey", "bold", "dim",
]

_COLOR_MAP = {
    "red": FG_RED,
    "green": FG_GREEN,
    "yellow": FG_YELLOW,
    "blue": FG_BLUE,
    "magenta": FG_MAGENTA,
    "cyan": FG_CYAN,
    "grey": FG_GREY,
    "bold": BOLD,
    "dim": DIM,
}


# ─── Detection ───────────────────────────────────────────────────────────


def _detect_rich_enabled() -> bool:
    """Return True iff full rendering should be enabled."""
    if os.environ.get("EPISTEME_NO_RICH", "").lower() in {"1", "true", "yes"}:
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    # NO_COLOR-set means no color, but we still render boxes; flagged separately.
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def _detect_color_enabled() -> bool:
    """Return True iff color is enabled (subset of rich)."""
    if os.environ.get("EPISTEME_NO_RICH", "").lower() in {"1", "true", "yes"}:
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def _detect_box_enabled() -> bool:
    """Boxes use Unicode characters; OK on most terminals even with NO_COLOR."""
    if os.environ.get("EPISTEME_NO_RICH", "").lower() in {"1", "true", "yes"}:
        return False
    return True


def terminal_width(default: int = 72) -> int:
    """Detect terminal width; fall back to default on detection failure."""
    try:
        return max(40, shutil.get_terminal_size((default, 24)).columns)
    except (AttributeError, OSError):
        return default


# ─── Renderer class ──────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Renderer:
    rich: bool
    color: bool
    box: bool
    width: int

    @classmethod
    def detect(cls) -> "Renderer":
        return cls(
            rich=_detect_rich_enabled(),
            color=_detect_color_enabled(),
            box=_detect_box_enabled(),
            width=terminal_width(),
        )

    def is_rich(self) -> bool:
        return self.rich


# ─── Color helpers ───────────────────────────────────────────────────────


def colored(text: str, color: Color, *, force: Optional[bool] = None) -> str:
    """Wrap text in an ANSI color code if color is enabled.

    If `force` is True/False, override auto-detection (used in tests).
    """
    if force is False:
        return text
    if force is True or _detect_color_enabled():
        return f"{_COLOR_MAP[color]}{text}{RESET}"
    return text


def health_indicator(value: float, *, good_threshold: float, warn_threshold: float) -> str:
    """Render a single ● colored by health.

    Convention: `value >= good_threshold` is green; `value >= warn_threshold` is yellow;
    below `warn_threshold` is red. Pass thresholds in the metric's own units.

    On non-rich terminals, falls back to ASCII characters [+] / [~] / [!].
    """
    rich = _detect_color_enabled()
    if value >= good_threshold:
        return colored("●", "green") if rich else "[+]"
    if value >= warn_threshold:
        return colored("●", "yellow") if rich else "[~]"
    return colored("●", "red") if rich else "[!]"


def health_indicator_inverse(value: float, *, good_threshold: float, warn_threshold: float) -> str:
    """Health indicator where LOWER values are better (e.g., chain breaks).

    `value <= good_threshold` is green; `value <= warn_threshold` is yellow;
    above `warn_threshold` is red.
    """
    rich = _detect_color_enabled()
    if value <= good_threshold:
        return colored("●", "green") if rich else "[+]"
    if value <= warn_threshold:
        return colored("●", "yellow") if rich else "[~]"
    return colored("●", "red") if rich else "[!]"


# ─── Box rendering ───────────────────────────────────────────────────────


# Box-drawing characters per Unicode block U+2500–U+257F
_BOX_CHARS = {
    "tl": "┌", "tr": "┐", "bl": "└", "br": "┘",
    "h": "─", "v": "│",
    "title_left": "┤", "title_right": "├",
    "mid_left": "├", "mid_right": "┤",
}

_BOX_ASCII = {
    "tl": "+", "tr": "+", "bl": "+", "br": "+",
    "h": "-", "v": "|",
    "title_left": "[", "title_right": "]",
    "mid_left": "+", "mid_right": "+",
}


def _box_chars():
    return _BOX_CHARS if _detect_box_enabled() else _BOX_ASCII


def box(text: str, *, title: Optional[str] = None, width: Optional[int] = None,
        color: Optional[Color] = None) -> str:
    """Render a bordered box around text.

    The text can be multi-line; each line is padded to width-2 (allowing for
    the left and right borders). If `title` is given, it appears in the top
    border between flanking title markers.
    """
    bc = _box_chars()
    w = width if width is not None else min(terminal_width(), 80)

    # Header
    if title:
        title_str = f" {title} "
        if color and _detect_color_enabled():
            title_str = colored(title_str.strip(), color)
            title_str = f" {title_str} "
        # Account for visible title length, not ANSI-escaped length
        visible_title_len = len(title) + 2  # spaces around
        top_pad = w - 2 - visible_title_len - 1
        top_pad = max(top_pad, 1)
        top = f"{bc['tl']}{bc['h']}{bc['title_left']}{title_str}{bc['title_right']}{bc['h'] * top_pad}{bc['tr']}"
    else:
        top = f"{bc['tl']}{bc['h'] * (w - 2)}{bc['tr']}"

    bottom = f"{bc['bl']}{bc['h'] * (w - 2)}{bc['br']}"

    lines = text.split("\n")
    body_lines = []
    for line in lines:
        # Truncate / pad to w-4 (2 borders + 2 spaces padding)
        inner_width = w - 4
        if len(line) > inner_width:
            line = line[: inner_width - 1] + "…"
        body_lines.append(f"{bc['v']} {line:<{inner_width}} {bc['v']}")

    return "\n".join([top] + body_lines + [bottom])


# ─── Header / Section ────────────────────────────────────────────────────


def header(text: str, *, level: int = 1, color: Color = "cyan") -> str:
    """Render a section header.

    Level 1: bold + colored + underlined with dashes (4 chars + spaces)
    Level 2: bold + colored, no underline
    Level 3: plain bold
    """
    rich = _detect_color_enabled()
    if level == 1:
        if rich:
            colored_text = f"{BOLD}{_COLOR_MAP[color]}{text}{RESET}"
        else:
            colored_text = text.upper()
        underline = "─" * len(text) if _detect_box_enabled() else "-" * len(text)
        if rich:
            underline = colored(underline, "grey")
        return f"{colored_text}\n{underline}"
    if level == 2:
        if rich:
            return f"{BOLD}{_COLOR_MAP[color]}{text}{RESET}"
        return f"## {text}"
    return colored(text, "bold") if rich else text


def divider(*, width: Optional[int] = None, char: Optional[str] = None) -> str:
    """Render a horizontal divider line."""
    w = width if width is not None else min(terminal_width(), 80)
    c = char if char is not None else ("─" if _detect_box_enabled() else "-")
    line = c * w
    if _detect_color_enabled():
        return colored(line, "grey")
    return line


# ─── Sparkline ───────────────────────────────────────────────────────────


_SPARKLINE_BLOCKS = "▁▂▃▄▅▆▇█"
_SPARKLINE_ASCII = ".:|"


def sparkline(values: Iterable[float], *, width: Optional[int] = None) -> str:
    """Render a unicode-block sparkline for a sequence of values.

    On non-rich terminals, falls back to ASCII chars `.:` etc.
    Returns a single-line string the same length as `values` (after width clamping).
    """
    vals = list(values)
    if not vals:
        return ""
    if width and len(vals) > width:
        # Down-sample: take evenly-spaced samples
        step = len(vals) / width
        vals = [vals[int(i * step)] for i in range(width)]

    blocks = _SPARKLINE_BLOCKS if _detect_box_enabled() else _SPARKLINE_ASCII
    vmin = min(vals)
    vmax = max(vals)
    span = (vmax - vmin) or 1.0

    def _block(v: float) -> str:
        norm = (v - vmin) / span
        idx = min(int(norm * len(blocks)), len(blocks) - 1)
        return blocks[idx]

    return "".join(_block(v) for v in vals)


# ─── Progress indicator ──────────────────────────────────────────────────


def progress(current: float, total: float, *, label: str = "", width: int = 30) -> str:
    """Render a one-line progress indicator: [████░░░░░░] 4/10 label

    `current`/`total` accept floats so a fractional metric (e.g. 5.2 of 7
    soak days) renders without losing its decimal; ints render as ints.
    """
    if total <= 0:
        return label
    filled = int((current / total) * width)
    filled = max(0, min(filled, width))
    if _detect_box_enabled():
        bar = "█" * filled + "░" * (width - filled)
    else:
        bar = "#" * filled + "." * (width - filled)
    if _detect_color_enabled():
        bar = colored(bar, "cyan")
    return f"[{bar}] {current}/{total}  {label}" if label else f"[{bar}] {current}/{total}"


# ─── Two-column key-value pad ────────────────────────────────────────────


def kv_table(rows: List[Tuple[str, str]], *, key_width: int = 28) -> str:
    """Render a 2-column key/value pad. Keys aligned, values wrapped to width.

    rows: list of (key, value) tuples. Values rendered as-is on one line.
    """
    out: List[str] = []
    for k, v in rows:
        key = k.ljust(key_width)
        if _detect_color_enabled():
            key = colored(key, "grey")
        out.append(f"{key} {v}")
    return "\n".join(out)
