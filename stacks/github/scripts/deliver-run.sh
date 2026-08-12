#!/usr/bin/env bash
# Delivers a completed unattended run: push, open a pull request, poll CI, fix what CI finds, merge,
# and sync the local default branch so the next spec starts from the merged state.
#
# Blocks until the work is on the default branch or something genuinely stops it, so a queue can move
# to the next spec knowing the previous one has actually landed.
#
# Requires autonomy.mayMerge and autonomy.mergeVia = "pull-request".
#
# Usage: deliver-run.sh <spec-id> [--dry-run]
#
# Environment:
#   TRELLIS_GH_BIN         gh binary (overridable for testing)
#   TRELLIS_CLAUDE_BIN     claude binary used for CI repair
#   TRELLIS_CHECK_TIMEOUT  seconds to wait for one CI cycle (default 1800)
#   TRELLIS_MERGE_TIMEOUT  seconds to wait for the merge to land (default 300)
set -uo pipefail

SPEC_ID="${1:-}"
DRY_RUN=false
[ "${2:-}" = "--dry-run" ] && DRY_RUN=true

STACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repository" >&2; exit 1; }
cd "$ROOT" || exit 1

GH="${TRELLIS_GH_BIN:-gh}"
CLAUDE_BIN="${TRELLIS_CLAUDE_BIN:-claude}"
CHECK_TIMEOUT="${TRELLIS_CHECK_TIMEOUT:-1800}"
MERGE_TIMEOUT="${TRELLIS_MERGE_TIMEOUT:-300}"

die() { echo "deliver-run: $*" >&2; exit 1; }
say() { echo "  $*"; }

[ -n "$SPEC_ID" ] || die "usage: deliver-run.sh <spec-id> [--dry-run]"
[ -f trellis.json ] || die "no trellis.json"
command -v "$GH" >/dev/null || die "gh is not installed"

read -r MAY_MERGE MERGE_VIA MAX_REPAIRS < <(python3 -c "
import json
a = (json.load(open('trellis.json')).get('autonomy') or {})
print(str(a.get('mayMerge', False)).lower(), a.get('mergeVia', 'local'), a.get('maxRepairAttempts', 2))
")

[ "$MAY_MERGE" = "true" ] || die "autonomy.mayMerge is not enabled"
[ "$MERGE_VIA" = "pull-request" ] || die "autonomy.mergeVia is '$MERGE_VIA', not 'pull-request'"

BRANCH="agent/${SPEC_ID}"
REPORT="docs/runs/${SPEC_ID}.md"
DEFAULT_BRANCH="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|origin/||')"
[ -n "$DEFAULT_BRANCH" ] || DEFAULT_BRANCH="main"

# Return to wherever the caller started, not to a branch this script decided on. Checking out the
# default branch on exit stranded people: the report lives on the agent branch, so a retry then died
# with "no run report" — a misleading message from a script that had just moved you off the branch
# holding it.
STARTING_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
restore_branch() {
  [ -n "$STARTING_BRANCH" ] || return 0
  [ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" = "$STARTING_BRANCH" ] && return 0
  git rev-parse --verify "$STARTING_BRANCH" >/dev/null 2>&1 && git checkout -q "$STARTING_BRANCH"
}

echo "Delivering $SPEC_ID via pull request -> $DEFAULT_BRANCH"

# ---------------------------------------------------------------- the run finished properly
git rev-parse --verify "$BRANCH" >/dev/null 2>&1 || die "no branch $BRANCH"

# The report may be committed on the agent branch, on the default branch, or sitting uncommitted in
# the working tree, depending on how the work was built. Look in all three rather than demanding the
# caller be standing in the right place.
REPORT_BODY=""
if [ -f "$REPORT" ]; then
  REPORT_BODY="$(cat "$REPORT")"
else
  for ref in "$BRANCH" "$DEFAULT_BRANCH"; do
    REPORT_BODY="$(git show "${ref}:${REPORT}" 2>/dev/null)" && [ -n "$REPORT_BODY" ] && break
    REPORT_BODY=""
  done
fi
[ -n "$REPORT_BODY" ] || die "no run report for $SPEC_ID. Looked in the working tree, on $BRANCH and on
$DEFAULT_BRANCH. Write one with: .claude/scripts/write-run-report.sh $SPEC_ID DONE"

OUTCOME="$(printf '%s\n' "$REPORT_BODY" | grep -m1 '^\*\*Outcome:\*\*' | sed 's/.*:\*\* //')"
case "$OUTCOME" in
  DONE)     say "run outcome: DONE" ;;
  TAMPERED) die "run outcome was TAMPERED. Nothing it produced is trustworthy." ;;
  *)        die "run outcome was ${OUTCOME:-unknown}, not DONE" ;;
esac

[ -z "$(git status --porcelain)" ] || die "working tree is dirty"

SPEC_TITLE="$(grep -m1 '^title:' docs/specs/${SPEC_ID}*.md | sed 's/title: *//')"

# ---------------------------------------------------------------- verify locally first
# CI will check too. Opening a pull request on work that fails locally wastes a CI cycle learning
# something already knowable in seconds.
git checkout -q "$BRANCH" || die "could not switch to $BRANCH"

echo '{}' | .claude/hooks/verify-gate.py >/dev/null 2>&1 \
  || { restore_branch; die "gates fail on the branch"; }
say "gates green locally"

.claude/scripts/spec-coverage.py "$SPEC_ID" >/dev/null 2>&1 \
  || { restore_branch; die "acceptance criteria are uncovered"; }
say "every criterion covered"

BASE_SHA="$(git merge-base HEAD "$DEFAULT_BRANCH")"
RISK="auto"
"$STACK_DIR/scripts/classify-risk.py" "$BASE_SHA" >/dev/null 2>&1 || RISK="needs-human"
say "risk: $RISK"

if $DRY_RUN; then
  restore_branch
  echo "Dry run - would push, open a pull request, and $([ "$RISK" = auto ] && echo 'merge when green' || echo 'stop for review')."
  exit 0
fi

# ---------------------------------------------------------------- open the pull request
git push -q --set-upstream origin "$BRANCH" 2>/dev/null || die "push failed"
say "pushed $BRANCH"

TITLE="$SPEC_ID: $SPEC_TITLE"
BODY="$REPORT_BODY

---

**Risk:** $RISK, per \`stacks/github/risk-policy.json\`

Produced by an unattended Trellis run. The verdict above came from the gates and the coverage mapper,
not from the agent's account of what it did."

# gh pr create fails outright on a label the repository does not have, and no repository has these
# until something makes them. That killed the first delivery in a fresh repo AFTER the branch had
# been pushed — the worst moment to discover a missing prerequisite.
ensure_label() {
  "$GH" label create "$1" --color "$2" --description "$3" --force >/dev/null 2>&1 || true
}
ensure_label "agent-run"   "0e8a16" "Opened by an unattended Trellis run"
ensure_label "needs-human" "d93f0b" "Risk classifier requires review before merge"

LABELS="agent-run"
[ "$RISK" = "needs-human" ] && LABELS="$LABELS,needs-human"

PR_URL="$("$GH" pr create --base "$DEFAULT_BRANCH" --head "$BRANCH" \
  --title "$TITLE" --body "$BODY" --label "$LABELS" 2>&1 | tail -1)"
case "$PR_URL" in
  http*) ;;
  *)
    # Retry without labels. A missing label is a repository-configuration detail; it should not sink
    # a delivery whose gates, coverage and risk have all passed.
    say "pull request creation failed, retrying without labels"
    PR_URL="$("$GH" pr create --base "$DEFAULT_BRANCH" --head "$BRANCH" \
      --title "$TITLE" --body "$BODY" 2>&1 | tail -1)" ;;
esac
case "$PR_URL" in
  http*) say "opened $PR_URL" ;;
  *) restore_branch; die "could not create the pull request: $PR_URL" ;;
esac

if [ "$RISK" = "needs-human" ]; then
  restore_branch
  .claude/scripts/notify.sh "NEEDS-HUMAN" "$SPEC_ID" "$PR_URL" >/dev/null 2>&1
  echo
  echo "NEEDS-HUMAN - $PR_URL is open and will not merge itself."
  exit 3
fi

# ---------------------------------------------------------------- poll CI, fixing what it finds
# Polling rather than `gh pr merge --auto`, deliberately: --auto requires auto-merge to be enabled on
# the repository, which varies by plan and settings. Polling works everywhere, and it means this
# script knows the outcome instead of delegating it to something it cannot observe.
poll_checks() {
  local deadline=$(( $(date +%s) + CHECK_TIMEOUT ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    local state
    state="$("$GH" pr checks "$PR_URL" --json state,name 2>/dev/null | python3 -c "
import json, sys
try:
    checks = json.load(sys.stdin)
except Exception:
    print('pending'); raise SystemExit
if not checks:
    print('none'); raise SystemExit
states = [c.get('state', '') for c in checks]
bad = ('FAILURE', 'ERROR', 'CANCELLED', 'TIMED_OUT', 'ACTION_REQUIRED')
ok = ('SUCCESS', 'SKIPPED', 'NEUTRAL')
print('failed' if any(s in bad for s in states)
      else 'passed' if all(s in ok for s in states) else 'pending')
" 2>/dev/null || echo pending)"
    case "$state" in
      passed|failed|none) echo "$state"; return ;;
      *) sleep 15 ;;
    esac
  done
  echo timeout
}

ATTEMPT=0
while :; do
  say "polling checks (attempt $((ATTEMPT + 1)), timeout ${CHECK_TIMEOUT}s)..."
  STATE="$(poll_checks)"

  case "$STATE" in
    passed) say "checks passed"; break ;;
    none)
      # No checks configured means nothing verifies this on the server. The local gates already
      # passed, but say so rather than letting silence read as success.
      say "no checks configured on this repository - merging on local gates alone"
      break ;;
    timeout)
      .claude/scripts/notify.sh "CI-TIMEOUT" "$SPEC_ID" "$PR_URL" >/dev/null 2>&1
      restore_branch
      echo; echo "CI did not finish within ${CHECK_TIMEOUT}s - $PR_URL left open."
      exit 1 ;;
  esac

  # ---- CI failed: fix it -------------------------------------------------
  ATTEMPT=$((ATTEMPT + 1))
  if [ "$ATTEMPT" -gt "$MAX_REPAIRS" ]; then
    .claude/scripts/notify.sh "CI-FAILED" "$SPEC_ID" "$PR_URL" >/dev/null 2>&1
    restore_branch
    echo
    echo "CI still failing after $MAX_REPAIRS repair attempt(s) - $PR_URL left open for you."
    exit 1
  fi

  say "CI failed - repair attempt $ATTEMPT of $MAX_REPAIRS"

  FAILING="$("$GH" run view --log-failed 2>/dev/null | tail -200)"
  [ -n "$FAILING" ] || FAILING="$("$GH" pr checks "$PR_URL" 2>/dev/null | tail -40)"

  "$CLAUDE_BIN" -p "CI is failing on the pull request for $SPEC_ID.

Failing output:

$FAILING

Fix the cause on this branch, then commit. Constraints:

- Fix the CODE, never the check. Weakening or skipping a test to make CI pass is the one outcome
  worse than a red build, because it removes the thing that would have told you next time.
- Stay inside the spec's scope. If the fix needs something the spec does not cover, stop and write
  BLOCKED.md with the single question instead of widening the change.
- Do not touch anything under .claude/, .githooks/ or .github/workflows/.
- Do not add dependencies.

Run the local gates before committing." \
    --setting-sources project \
    --settings .claude/profiles/autonomy.settings.json \
    --permission-mode dontAsk \
    >> "docs/runs/${SPEC_ID}.log" 2>&1

  if [ -f BLOCKED.md ]; then
    .claude/scripts/notify.sh "BLOCKED" "$SPEC_ID" "$PR_URL" >/dev/null 2>&1
    restore_branch
    echo; echo "BLOCKED during CI repair - $PR_URL left open. See BLOCKED.md."
    exit 3
  fi

  if ! echo '{}' | .claude/hooks/verify-gate.py >/dev/null 2>&1; then
    say "repair did not make the local gates pass"
    continue
  fi

  git push -q origin "$BRANCH" 2>/dev/null || {
    restore_branch
    die "could not push the repair"
  }
  say "pushed repair, re-polling"
  sleep 10   # let the new run register before polling again
done

# ---------------------------------------------------------------- merge
"$GH" pr merge "$PR_URL" --squash --delete-branch >/dev/null 2>&1 || {
  .claude/scripts/notify.sh "MERGE-REFUSED" "$SPEC_ID" "$PR_URL" >/dev/null 2>&1
  restore_branch
  die "checks passed but the merge was refused - often branch protection. See $PR_URL"
}

# `gh pr merge` returning zero is not the same as the merge existing.
MERGED=false
DEADLINE=$(( $(date +%s) + MERGE_TIMEOUT ))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  [ "$("$GH" pr view "$PR_URL" --json state -q .state 2>/dev/null)" = "MERGED" ] && { MERGED=true; break; }
  sleep 5
done

git checkout -q "$DEFAULT_BRANCH"
$MERGED || die "merge requested but the pull request does not show as merged - check $PR_URL"
say "merged"

# ---------------------------------------------------------------- sync for the next spec
# Fetch and fast-forward separately, so "already up to date" is a success rather than an error, and
# so a genuine divergence is reported as itself rather than as a failed pull.
git fetch -q origin "$DEFAULT_BRANCH" 2>/dev/null \
  || die "merged, but could not fetch $DEFAULT_BRANCH. Sync before the next spec."
if ! git merge -q --ff-only "origin/$DEFAULT_BRANCH" 2>/dev/null; then
  git rev-parse HEAD | grep -q "$(git rev-parse "origin/$DEFAULT_BRANCH")" \
    || die "merged, but local $DEFAULT_BRANCH has diverged from origin and cannot fast-forward.
Resolve before running the next spec, or it will build on the wrong base."
fi
git branch -q -D "$BRANCH" 2>/dev/null && say "deleted local $BRANCH"
say "local $DEFAULT_BRANCH now at $(git rev-parse --short HEAD)"

echo
echo "DELIVERED - $SPEC_ID merged via $PR_URL"
