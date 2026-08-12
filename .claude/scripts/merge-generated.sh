#!/usr/bin/env bash
# Git merge driver for files Trellis generates.
#
# A generated file has no meaningful merge: both sides are derived from their own tree, and the correct
# result is derived from the MERGED tree — which is what regenerating produces. Resolving these by hand,
# or by picking a side, produces a file that is wrong in a way nobody notices because nobody reads it.
#
# Registered by .gitattributes. Git calls it as: merge-generated.sh %A %O %B %P
#   %A current version (and the file we must leave the result in)   %P the real pathname
set -uo pipefail
CURRENT="${1:-}"; PATHNAME="${4:-}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 1

case "$PATHNAME" in
  docs/map/OVERVIEW.md)
    # Regenerate from the merged tree. If that fails, keep ours rather than leaving conflict markers in
    # a file the agent reads as fact.
    ( cd "$ROOT" && .claude/scripts/build-map.py >/dev/null 2>&1 ) \
      && cp "$ROOT/docs/map/OVERVIEW.md" "$CURRENT" 2>/dev/null
    ;;
  *)
    # Other generated files are session artifacts — a handoff, a run digest. Neither side is more
    # correct, and both are superseded by the next run. Keep ours and move on.
    ;;
esac
exit 0
