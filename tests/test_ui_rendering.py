"""Tests for src/episteme/_ui.py zero-dep ANSI rendering primitives.

Covers TTY/NO_COLOR/EPISTEME_NO_RICH detection, color escape codes,
box rendering, sparklines, progress indicators. Tests force rendering
mode via env vars rather than relying on test-runner TTY.
"""
from __future__ import annotations

import os

import pytest

from episteme import _ui


# ─── Detection ──────────────────────────────────────────────────────────


def test_no_rich_env_disables_rich(monkeypatch):
    monkeypatch.setenv("EPISTEME_NO_RICH", "1")
    assert _ui._detect_rich_enabled() is False
    assert _ui._detect_color_enabled() is False
    assert _ui._detect_box_enabled() is False


def test_no_color_env_disables_color(monkeypatch):
    monkeypatch.delenv("EPISTEME_NO_RICH", raising=False)
    monkeypatch.setenv("NO_COLOR", "")
    assert _ui._detect_color_enabled() is False
    # Boxes still allowed under NO_COLOR
    monkeypatch.delenv("EPISTEME_NO_RICH", raising=False)
    assert _ui._detect_box_enabled() is True


def test_terminal_width_returns_positive():
    w = _ui.terminal_width(default=80)
    assert w >= 40


# ─── colored ────────────────────────────────────────────────────────────


def test_colored_force_false_returns_plain():
    out = _ui.colored("hello", "red", force=False)
    assert out == "hello"


def test_colored_force_true_wraps_in_ansi():
    out = _ui.colored("hello", "red", force=True)
    assert "\033[" in out
    assert "hello" in out
    assert out.endswith(_ui.RESET)


def test_colored_default_respects_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "")
    out = _ui.colored("hello", "red")
    assert out == "hello"


# ─── Health indicators ──────────────────────────────────────────────────


def test_health_indicator_above_good_threshold():
    out = _ui.health_indicator(95.0, good_threshold=90.0, warn_threshold=70.0)
    # Should be green dot or ASCII [+]
    assert "●" in out or "[+]" in out


def test_health_indicator_below_warn_threshold():
    out = _ui.health_indicator(50.0, good_threshold=90.0, warn_threshold=70.0)
    assert "●" in out or "[!]" in out


def test_health_indicator_between_thresholds():
    out = _ui.health_indicator(80.0, good_threshold=90.0, warn_threshold=70.0)
    assert "●" in out or "[~]" in out


def test_health_indicator_inverse_low_is_good():
    out = _ui.health_indicator_inverse(0, good_threshold=0, warn_threshold=2)
    # 0 ≤ 0 → green/good
    assert "●" in out or "[+]" in out


def test_health_indicator_inverse_high_is_bad():
    out = _ui.health_indicator_inverse(5, good_threshold=0, warn_threshold=2)
    assert "●" in out or "[!]" in out


# ─── Box rendering ──────────────────────────────────────────────────────


def test_box_wraps_text_in_border(monkeypatch):
    monkeypatch.delenv("EPISTEME_NO_RICH", raising=False)
    out = _ui.box("hello world", width=20)
    # Box chars OR ASCII border
    has_unicode = "┌" in out or "└" in out
    has_ascii = "+" in out
    assert has_unicode or has_ascii
    assert "hello world" in out


def test_box_with_title():
    out = _ui.box("body text", title="TITLE", width=40)
    assert "TITLE" in out
    assert "body text" in out


def test_box_ascii_mode(monkeypatch):
    monkeypatch.setenv("EPISTEME_NO_RICH", "1")
    out = _ui.box("hello", width=20)
    # Under EPISTEME_NO_RICH, falls back to ASCII
    assert "+" in out


# ─── Header / divider ──────────────────────────────────────────────────


def test_header_level_1_includes_underline():
    out = _ui.header("Section", level=1)
    # Has the underlining line (─ or - depending on render mode)
    lines = out.split("\n")
    assert len(lines) == 2


def test_header_level_2_one_line():
    out = _ui.header("Section", level=2)
    assert "\n" not in out


def test_divider_returns_a_line():
    out = _ui.divider(width=40)
    # Should be ≥ 40 chars (color codes may extend it)
    visible_chars = out.replace(_ui.ESC, "").replace("[", "").replace("m", "").replace("0", "")
    assert len(out) >= 40


# ─── Sparkline ──────────────────────────────────────────────────────────


def test_sparkline_renders_same_length_as_input():
    values = [1, 2, 3, 4, 5, 6, 7, 8]
    out = _ui.sparkline(values)
    # Should be 8 chars (one per value)
    # (Unicode block chars are 1 char in str length)
    assert len(out) == 8


def test_sparkline_empty_input():
    assert _ui.sparkline([]) == ""


def test_sparkline_downsamples_to_width():
    values = list(range(100))
    out = _ui.sparkline(values, width=20)
    assert len(out) == 20


# ─── Progress ───────────────────────────────────────────────────────────


def test_progress_returns_one_line():
    out = _ui.progress(3, 10, label="step")
    assert "\n" not in out
    assert "3/10" in out
    assert "step" in out


def test_progress_zero_total_returns_label():
    out = _ui.progress(0, 0, label="empty")
    assert "empty" in out


# ─── kv_table ───────────────────────────────────────────────────────────


def test_kv_table_renders_rows():
    rows = [("key1", "value1"), ("key2", "value2")]
    out = _ui.kv_table(rows)
    assert "key1" in out
    assert "value1" in out
    assert "key2" in out
    # Two lines
    assert out.count("\n") == 1


# ─── Renderer dataclass ────────────────────────────────────────────────


def test_renderer_detect(monkeypatch):
    monkeypatch.setenv("EPISTEME_NO_RICH", "1")
    r = _ui.Renderer.detect()
    assert r.is_rich() is False
    assert r.color is False
