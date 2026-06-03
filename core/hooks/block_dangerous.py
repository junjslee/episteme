#!/usr/bin/env python3
import json
import re
import sys


PATTERNS = [
    (re.compile(r"\brm\s+-rf\b"), "Blocked destructive recursive delete."),
    (re.compile(r"\bgit\s+reset\s+--hard\b"), "Blocked hard reset."),
    (re.compile(r"\bgit\s+clean\s+-f[d|x]*\b"), "Blocked forced git clean."),
    (re.compile(r"\bgit\s+checkout\s+--\b"), "Blocked checkout overwrite."),
    (re.compile(r"\bgit\s+push\s+--force(?:-with-lease)?\b"), "Blocked force push."),
    (re.compile(r"\bfind\b.*\s-delete\b"), "Blocked find -delete."),
    (re.compile(r"\bsudo\b"), "Blocked sudo."),
    (re.compile(r"\bpkill\b"), "Blocked pkill."),
    (re.compile(r"\bkill\s+-9\b"), "Blocked kill -9."),
    (re.compile(r"\bchmod\s+777\b"), "Blocked world-writable chmod."),
    (re.compile(r"\btruncate\s"), "Blocked truncate."),
    (re.compile(r"\bdd\b.*\bif=/dev/zero\b"), "Blocked dd zero-fill."),
    (re.compile(r"\bmkfs\b"), "Blocked mkfs."),
    (re.compile(r">\s*/dev/sd[a-z]"), "Blocked direct disk write."),
]


# Heredoc body + quoted-string-literal strippers. The matcher must see the
# *executable skeleton* of a command, not descriptive prose carried inside a
# commit-message HEREDOC or a quoted string. Without this, a commit body that
# merely MENTIONS a destructive token (e.g. documenting that Tier 3 blocks
# `rm -rf /`) is false-positive-blocked, even though no destructive command
# runs.
#
# SECURITY INVARIANT (Event 136 review): stripping is ONLY safe when the
# heredoc/quote is inert ARGUMENT data (a commit message, a `cat`/`echo`
# arg). When the content is fed to a SHELL INTERPRETER it is EXECUTABLE —
# `sh -c '<destructive>'`, `bash -c "<destructive>"`, `bash <<EOF ... EOF`
# all RUN the command. `_command_feeds_a_shell` detects those forms and the
# caller then scans the ORIGINAL (unstripped) command so the destructive
# token stays visible. Default-deny on uncertainty: any shell-executor shape
# disables stripping entirely.
_SHELL_EXECUTOR_RE = re.compile(
    r"\b(?:sh|bash|zsh|ksh|dash|fish|ash)\s+-[A-Za-z]*c\b"   # sh -c '...'
    r"|\b(?:sh|bash|zsh|ksh|dash|fish|ash)\s*<<"             # bash <<EOF (heredoc → shell)
    r"|\|\s*(?:sh|bash|zsh|ksh|dash|fish|ash)\b"             # ... | bash
    r"|\beval\b"                                              # eval '...'
)

# Opener captures the trailing content on the heredoc opener LINE (group
# `rest`) so a command chained after `<<WORD` on the same line —
# `echo <<X && rm -rf /` — is PRESERVED for matching, not swallowed with
# the body. Only the body strictly between the opener line's newline and the
# terminator line is blanked.
_HEREDOC_RE = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1(?P<rest>[^\n]*)\n.*?^\s*\2\b",
    re.DOTALL | re.MULTILINE,
)
_SQUOTE_RE = re.compile(r"'[^']*'")
_DQUOTE_RE = re.compile(r'"[^"]*"')


def _command_feeds_a_shell(command: str) -> bool:
    """True when `command` pipes/feeds content INTO a shell interpreter, so
    its heredoc/quoted content is EXECUTABLE, not inert argument prose."""
    return bool(_SHELL_EXECUTOR_RE.search(command))


def _heredoc_sub(m: "re.Match[str]") -> str:
    # Preserve the opener-line trailing content (e.g. ` && rm -rf /`); blank
    # only the body between the opener newline and the terminator.
    return " " + m.group("rest") + " "


def _strip_message_bodies(command: str) -> str:
    """Return the command with heredoc BODIES and quoted string literals
    blanked out, so PATTERNS match only at executable command position.

    Caller MUST NOT use this when `_command_feeds_a_shell(command)` is true —
    in that case the heredoc/quote is executable and the original command is
    scanned instead. Here we assume inert-argument context. The heredoc strip
    preserves any command chained on the opener line (group `rest`) so
    `echo <<X && rm -rf /` keeps its `&& rm -rf /` visible to the matcher.
    """
    stripped = _HEREDOC_RE.sub(_heredoc_sub, command)
    stripped = _SQUOTE_RE.sub(" ", stripped)
    stripped = _DQUOTE_RE.sub(" ", stripped)
    return stripped


def _extract_command(payload: dict) -> str:
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if isinstance(tool_input, str):
        return tool_input
    if isinstance(tool_input, dict):
        return (
            tool_input.get("command")
            or tool_input.get("cmd")
            or tool_input.get("bash_command")
            or ""
        )
    return ""


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    command = _extract_command(payload)
    # Choose the scan target. When the command feeds a shell interpreter
    # (sh -c / bash -c / bash <<EOF / | bash / eval), its heredoc + quoted
    # content is EXECUTABLE — scan the ORIGINAL so a destructive token inside
    # it is still caught (Event 136 review: stripping those forms was a
    # security regression). Otherwise the heredoc/quote is inert argument
    # prose (commit message, cat/echo arg) — scan the stripped skeleton so a
    # documented `rm -rf /` mention is not false-positive-blocked.
    if _command_feeds_a_shell(command):
        scan_target = command
    else:
        scan_target = _strip_message_bodies(command)
    for pattern, message in PATTERNS:
        if pattern.search(scan_target):
            # Echo the ORIGINAL command so the operator sees what they typed.
            sys.stderr.write(f"{message}\nCommand: {command}\n")
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
