#!/usr/bin/env bash
# Writes the run report for a spec.
#
# Shared by the unattended runner and the interactive /spec-next command, because delivery requires a
# report and only one of those two paths used to produce one. A spec built interactively could not be
# delivered by the automation, and nothing said so — the door was simply never openable.
#
# Usage: write-run-report.sh <spec-id> <outcome> [detail]
#   outcome: DONE | BLOCKED | FAILED | TAMPERED
#
# SLOW, and not obviously so from the name. It runs the gates to state their result as fact, so on a
# project with a11y and perf gates this takes minutes rather than seconds — longer than a foreground
# command is allowed. Background it and poll the log, exactly as delivery is backgrounded:
#
#   .claude/scripts/write-run-report.sh SPEC-024 DONE > /tmp/report.log 2>&1 &
#
# The gates are re-run rather than trusted from earlier because the report states them as fact, and a
# fact copied from a previous commit is a claim about work that has since changed.
set -uo pipefail

SPEC_ID="${1:-}"
OUTCOME="${2:-}"
DETAIL="${3:-}"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repository" >&2; exit 1; }
cd "$ROOT" || exit 1

[ -n "$SPEC_ID" ] || { echo "usage: write-run-report.sh <spec-id> <outcome> [detail]" >&2; exit 2; }
[ -n "$OUTCOME" ] || { echo "usage: write-run-report.sh <spec-id> <outcome> [detail]" >&2; exit 2; }

RUN_DIR="docs/runs"
REPORT="${RUN_DIR}/${SPEC_ID}.md"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
mkdir -p "$RUN_DIR"

# Reporting must never fail. Several of these commands legitimately exit non-zero — spec-coverage does
# so exactly when there is something worth reporting — and a run that cannot explain itself is worse
# than a failed one.
set +e

COVERED="$(.claude/scripts/spec-coverage.py "$SPEC_ID" 2>&1 \
           | grep -oE '[0-9]+/[0-9]+ criteria covered' | head -1)"
[ -n "$COVERED" ] || COVERED="unknown"

if [ "$OUTCOME" = "TAMPERED" ]; then
  # Reporting a gate result here would be worse than reporting nothing: the gates read green BECAUSE
  # they were removed, which is the most misleading line the report could carry.
  GATES="not trustworthy — the gate definitions were modified by this run"
  COVERED="not trustworthy"
else
  GATES="$(echo '{}' | .claude/hooks/verify-gate.py >/dev/null 2>&1 && echo green || echo RED)"
fi

BASE="$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null || echo HEAD~1)"

{
  echo "# Run report — $SPEC_ID"
  echo
  echo "**Outcome:** $OUTCOME"
  echo "**Written:** $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "**Branch:** \`$BRANCH\`"
  echo "**Gates:** $GATES · **Criteria covered:** $COVERED"
  echo
  [ -n "$DETAIL" ] && { echo "$DETAIL"; echo; }
  echo "## Files changed"
  echo
  echo '```'
  git diff --stat "$BASE" 2>/dev/null | tail -30 || echo "(none)"
  echo '```'
  if [ -f BLOCKED.md ]; then
    echo
    echo "## Blocked"
    echo
    cat BLOCKED.md
  fi
} > "$REPORT"

echo "$REPORT"
