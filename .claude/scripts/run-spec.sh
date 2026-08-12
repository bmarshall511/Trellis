#!/usr/bin/env bash
# Trellis unattended spec runner.
#
# Implements ONE spec with no human present, on its own branch, and ends in exactly one of two states:
#
#   done     every gate green and every acceptance criterion covered
#   blocked  a BLOCKED.md naming the single thing it could not resolve
#
# There is deliberately no third ending. "Mostly working" is the outcome this whole system exists to
# prevent, because it is the one that costs trust.
#
# Usage:
#   run-spec.sh <spec-id> [--dry-run]
#
# Environment:
#   TRELLIS_CLAUDE_BIN   command to invoke (default: claude). Overridable so the loop can be tested.
#   TRELLIS_MAX_REPAIRS  override autonomy.maxRepairAttempts
set -uo pipefail

SPEC_ID="${1:-}"
DRY_RUN=false
[[ "${2:-}" == "--dry-run" ]] && DRY_RUN=true

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1

CLAUDE_BIN="${TRELLIS_CLAUDE_BIN:-claude}"
RUN_DIR="docs/runs"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
STARTED_EPOCH="$(date +%s)"

die() { echo "run-spec: $*" >&2; exit 1; }
say() { echo "  $*"; }

[[ -n "$SPEC_ID" ]] || die "usage: run-spec.sh <spec-id> [--dry-run]"

SPEC_FILE="$(ls docs/specs/${SPEC_ID}*.md 2>/dev/null | head -1)"
[[ -n "$SPEC_FILE" ]] || die "no spec matching '$SPEC_ID' in docs/specs/"

BRANCH="agent/${SPEC_ID}"
REPORT="${RUN_DIR}/${SPEC_ID}.md"
mkdir -p "$RUN_DIR"

# ---------------------------------------------------------------- preflight
# Everything here is a reason NOT to start. A run that begins from a broken baseline cannot tell its
# own failures from ones it inherited, and will spend its repair budget on someone else's problem.
echo "Preflight for $SPEC_ID"

[[ -f trellis.json ]] || die "no trellis.json — the project is not set up"
.claude/scripts/validate-config.py >/dev/null || die "trellis.json is invalid"
say "config valid"

if [[ -n "$(git status --porcelain)" ]]; then
  die "working tree is dirty. An unattended run must start from a clean baseline, or its diff is not its own."
fi
say "working tree clean"

.claude/scripts/spec-lint.py "$SPEC_ID" >/dev/null \
  || die "spec fails the readiness checklist. Run .claude/scripts/spec-lint.py $SPEC_ID"
say "spec is ready"

if grep -qE '^surfaces:.*\bui\b' "$SPEC_FILE"; then
  .claude/scripts/mockup.py verify "$SPEC_ID" >/dev/null \
    || die "spec has a UI surface but its mockup is unapproved or stale"
  say "mockup approved"
fi

# A red gate before we start means we cannot attribute a red gate afterwards.
BASELINE_OK=true
if ! echo '{}' | .claude/hooks/verify-gate.py >/dev/null 2>&1; then
  BASELINE_OK=false
fi
$BASELINE_OK || die "gates are already failing on a clean tree. Fix the baseline before running unattended."
say "baseline gates green"

# Fingerprint everything the run must not touch. The autonomy profile denies writing to these, but a
# denial is a control we should verify held rather than assume — and this catches tampering explicitly
# rather than leaving it to be noticed incidentally by some later check.
guard_fingerprint() {
  find .claude/hooks .claude/scripts .githooks trellis.json .claude/settings.json \
       .claude/profiles -type f 2>/dev/null | sort | xargs shasum -a 256 2>/dev/null | shasum -a 256
}
GUARDS_BEFORE="$(guard_fingerprint)"

MAX_REPAIRS="${TRELLIS_MAX_REPAIRS:-$(python3 -c "
import json
print((json.load(open('trellis.json')).get('autonomy') or {}).get('maxRepairAttempts', 2))
" 2>/dev/null || echo 2)}"
say "repair budget: $MAX_REPAIRS"

if $DRY_RUN; then
  echo "Dry run — preflight passed, stopping before launch."
  exit 0
fi

# ---------------------------------------------------------------- isolate
git rev-parse --verify "$BRANCH" >/dev/null 2>&1 && die "branch $BRANCH already exists — a previous run left it behind"
git checkout -q -b "$BRANCH" || die "could not create branch $BRANCH"
say "on branch $BRANCH"

finish() {
  # Reporting must never fail. Several commands here legitimately exit non-zero — spec-coverage does
  # so precisely when there is something to report — and with `set -e` active during adjudication an
  # unguarded one kills the script before it writes anything. A run that cannot explain itself is
  # worse than a failed run.
  set +e
  local outcome="$1" detail="${2:-}"
  local elapsed=$(( $(date +%s) - STARTED_EPOCH ))
  local covered gates
  covered="$(.claude/scripts/spec-coverage.py "$SPEC_ID" 2>&1 \
             | grep -oE '[0-9]+/[0-9]+ criteria covered' | head -1)"
  [[ -n "$covered" ]] || covered="unknown"
  if [[ "$outcome" == "TAMPERED" ]]; then
    # Reporting a gate result here would be worse than reporting nothing: the gates read green
    # BECAUSE they were removed, which is the most misleading line the report could carry.
    gates="not trustworthy — the gate definitions were modified by this run"
    covered="not trustworthy"
  else
    gates="$(echo '{}' | .claude/hooks/verify-gate.py >/dev/null 2>&1 && echo 'green' || echo 'RED')"
  fi

  {
    echo "# Run report — $SPEC_ID"
    echo
    echo "**Outcome:** $outcome"
    echo "**Started:** $STARTED_AT · **Elapsed:** ${elapsed}s"
    echo "**Branch:** \`$BRANCH\`"
    echo "**Gates:** $gates · **Criteria covered:** $covered"
    echo
    if [[ -n "$detail" ]]; then echo "$detail"; echo; fi
    echo "## Files changed"
    echo
    echo '```'
    git diff --stat "$(git merge-base HEAD main 2>/dev/null || echo HEAD~1)" 2>/dev/null | tail -30 || echo "(none)"
    echo '```'
    if [[ -f BLOCKED.md ]]; then
      echo
      echo "## Blocked"
      echo
      cat BLOCKED.md
    fi
  } > "$REPORT"

  .claude/scripts/notify.sh "$outcome" "$SPEC_ID" "$REPORT" >/dev/null 2>&1
  echo
  echo "$outcome — report at $REPORT"
  set -e
}

# ---------------------------------------------------------------- run
PROMPT="Implement $SPEC_ID.

Read docs/specs/$(basename "$SPEC_FILE") in full, then implement it.

You are running UNATTENDED. No human will answer anything. There are exactly two acceptable endings:

1. Every gate in trellis.json passes AND every acceptance criterion has a test that would fail if that
   criterion broke. Verify with .claude/scripts/spec-coverage.py $SPEC_ID before you finish.

2. You cannot proceed without a decision you have not been given. Write BLOCKED.md containing exactly
   one clearly-stated question and stop. Do not guess. Do not implement a 'reasonable default' and note
   it — a blocked spec costs one morning decision; a guessed one costs trust in every future run.

Work only within the spec's scope. 'Out of scope' is binding. Do not add dependencies — if the spec
needs one, that is a BLOCKED. Do not modify anything under .claude/, .githooks/ or trellis.json.

Commit your work in logical commits as you go."

set +e
"$CLAUDE_BIN" -p "$PROMPT" \
  --setting-sources project \
  --settings .claude/profiles/autonomy.settings.json \
  --permission-mode dontAsk \
  > "${RUN_DIR}/${SPEC_ID}.log" 2>&1
CLAUDE_EXIT=$?
set -e

# ---------------------------------------------------------------- adjudicate
# The agent's own exit code is not evidence. Judge by the gates and the coverage, which it cannot fake.

# Checked first, and ahead of everything else: if the guardrails moved, no later result means anything.
# A run that can edit its own gates has no gates, so a green result would be evidence of nothing.
if [[ "$(guard_fingerprint)" != "$GUARDS_BEFORE" ]]; then
  finish "TAMPERED" "Guardrail files changed during the run — hooks, gate scripts, or trellis.json.
Every other result from this run is meaningless, because the thing that judges the run was modified by
the run. The branch is left in place for inspection. Do not merge it."
  exit 1
fi

if [[ -f BLOCKED.md ]]; then
  finish "BLOCKED" "The run stopped and asked a question rather than guessing. That is correct behaviour."
  exit 2
fi

if [[ $CLAUDE_EXIT -ne 0 ]]; then
  finish "FAILED" "The agent exited $CLAUDE_EXIT without writing BLOCKED.md. See ${RUN_DIR}/${SPEC_ID}.log."
  exit 1
fi

if ! echo '{}' | .claude/hooks/verify-gate.py >/dev/null 2>&1; then
  finish "FAILED" "Gates are red and no BLOCKED.md was written. The run claimed completion it could not support."
  exit 1
fi

if ! .claude/scripts/spec-coverage.py "$SPEC_ID" >/dev/null 2>&1; then
  finish "FAILED" "Gates pass but acceptance criteria are uncovered. Green tests on untested promises."
  exit 1
fi

finish "DONE" "All gates green and every acceptance criterion covered."
exit 0
