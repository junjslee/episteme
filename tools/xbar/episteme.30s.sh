#!/usr/bin/env bash
# <xbar.title>episteme</xbar.title>
# <xbar.version>v1.0</xbar.version>
# <xbar.desc>Menu-bar glance at episteme governance state (E174). Consumes `episteme status --json` for the project it is pointed at; click-through opens the live dashboard (`episteme viewer`).</xbar.desc>
# <xbar.dependencies>episteme,jq</xbar.dependencies>
#
# Install: copy (or symlink) into xbar/SwiftBar's plugin folder, e.g.
#   ln -s ~/episteme/tools/xbar/episteme.30s.sh \
#     "$HOME/Library/Application Support/xbar/plugins/episteme.30s.sh"
# Set EPISTEME_XBAR_PROJECT to the project to watch (default: ~/episteme).
# The 30s cadence is in the filename, per xbar convention.

set -u

PROJECT="${EPISTEME_XBAR_PROJECT:-$HOME/episteme}"
VIEWER_URL="http://127.0.0.1:37776/"
EPISTEME_BIN="$(command -v episteme || true)"
JQ_BIN="$(command -v jq || true)"

if [ -z "$EPISTEME_BIN" ] || [ -z "$JQ_BIN" ]; then
  echo "epi ?"
  echo "---"
  echo "episteme or jq not on PATH | color=red"
  exit 0
fi

STATUS="$(cd "$PROJECT" 2>/dev/null && "$EPISTEME_BIN" status --json 2>/dev/null)"
if [ -z "$STATUS" ]; then
  echo "epi ✕"
  echo "---"
  echo "episteme status failed in $PROJECT | color=red"
  exit 0
fi

FRESH="$(echo "$STATUS" | "$JQ_BIN" -r '.surface.fresh')"
AGE="$(echo "$STATUS" | "$JQ_BIN" -r '.surface.age_minutes // empty')"
EXISTS="$(echo "$STATUS" | "$JQ_BIN" -r '.surface.exists')"
# Strip xbar's directive separator from repo-controlled strings — a branch
# named `feat|color=red` must not inject menu directives (review nit).
BRANCH="$(echo "$STATUS" | "$JQ_BIN" -r '.branch' | tr -d '|')"
PROTOCOLS="$(echo "$STATUS" | "$JQ_BIN" -r '.framework.protocols // 0')"
DEFERRED="$(echo "$STATUS" | "$JQ_BIN" -r '.framework.deferred_discoveries // 0')"
RIGOR="$(echo "$STATUS" | "$JQ_BIN" -r '.rigor.level // "?"')"

# Menu-bar line: one glyph carries the surface state.
if [ "$EXISTS" != "true" ]; then
  echo "epi ○"          # no surface declared
elif [ "$FRESH" = "true" ]; then
  echo "epi ●"          # fresh
else
  echo "epi ◐"          # stale
fi

echo "---"
echo "project: $(basename "$PROJECT") ($BRANCH)"
if [ "$EXISTS" != "true" ]; then
  echo "surface: none declared | color=red"
elif [ "$FRESH" = "true" ]; then
  echo "surface: fresh (${AGE}m) | color=green"
else
  echo "surface: STALE (${AGE}m) | color=orange"
fi
echo "rigor: $RIGOR"
echo "protocols: $PROTOCOLS · deferred: $DEFERRED"
echo "---"
echo "Open dashboard | href=$VIEWER_URL"
echo "Refresh | refresh=true"
