#!/usr/bin/env bash
# Merges a completed unattended run into the default branch.
#
# This is the ONLY way anything reaches the default branch automatically. Ad-hoc `git push origin main`
# stays blocked by the guard — deliberately. The point was never that merging is dangerous; it is that
# merging *without the checks below* is dangerous, and a blanket block is a crude way of ensuring they
# happen.
#
# So this is a narrow, auditable door rather than an open one. Everything it checks is checked again
# here, on the branch as it will actually be merged, because the run that produced it is not a witness
# to its own correctness.
#
# Requires autonomy.mayMerge in trellis.json. Pushes only if autonomy.pushAfterMerge is also set, so a
# run can integrate locally overnight while you decide when anything leaves the machine.
#
# Usage: merge-run.sh <spec-id> [--dry-run]
set -uo pipefail

SPEC_ID="${1:-}"
DRY_RUN=false
[[ "${2:-}" == "--dry-run" ]] && DRY_RUN=true

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT" || exit 1

die() { echo "merge-run: $*" >&2; exit 1; }
say() { echo "  $*"; }

[[ -n "$SPEC_ID" ]] || die "usage: merge-run.sh <spec-id> [--dry-run]"
[[ -f trellis.json ]] || die "no trellis.json"

read -r MAY_MERGE PUSH_AFTER < <(python3 -c "
import json
a = (json.load(open('trellis.json')).get('autonomy') or {})
print(str(a.get('mayMerge', False)).lower(), str(a.get('pushAfterMerge', False)).lower())
")

[[ "$MAY_MERGE" == "true" ]] || die "autonomy.mayMerge is not enabled in trellis.json. Nothing merges automatically until it is."

# Accepts agent/<id> and agent/<id>-<description>. Four scripts hardcoded the first form while the
# second is what people type, so a finished build failed at the last step naming a branch nobody made.
BRANCH="$(.claude/scripts/spec-branch.sh "$SPEC_ID")" || exit 1
REPORT="docs/runs/${SPEC_ID}.md"
DEFAULT_BRANCH="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|origin/||')"
[[ -n "$DEFAULT_BRANCH" ]] || DEFAULT_BRANCH="$(git rev-parse --verify main >/dev/null 2>&1 && echo main || echo master)"

echo "Merge check for $SPEC_ID → $DEFAULT_BRANCH"

# ---------------------------------------------------------------- the run finished properly
git rev-parse --verify "$BRANCH" >/dev/null 2>&1 || die "no branch $BRANCH"
[[ -f "$REPORT" ]] || die "no run report at $REPORT — only completed runs merge"

OUTCOME="$(grep -m1 '^\*\*Outcome:\*\*' "$REPORT" | sed 's/.*:\*\* //')"
case "$OUTCOME" in
  DONE)     say "run outcome: DONE" ;;
  TAMPERED) die "run outcome was TAMPERED. Nothing it produced is trustworthy. Inspect the branch by hand." ;;
  *)        die "run outcome was ${OUTCOME:-unknown}, not DONE" ;;
esac

# ---------------------------------------------------------------- nothing changed underneath
[[ -z "$(git status --porcelain)" ]] || die "working tree is dirty — commit or stash before merging"
say "working tree clean"

# ---------------------------------------------------------------- re-verify ON the branch
# The run reported green. That report was written by the run. Check again here, on exactly what would
# be merged, because a report is a claim and this is the last moment it costs nothing to test it.
git checkout -q "$BRANCH" || die "could not switch to $BRANCH"

echo '{}' | .claude/hooks/verify-gate.py >/dev/null 2>&1 || {
  git checkout -q "$DEFAULT_BRANCH"
  die "gates fail on the branch. The run's report said otherwise; the gates win."
}
say "gates green on the branch"

.claude/scripts/spec-coverage.py "$SPEC_ID" >/dev/null 2>&1 || {
  git checkout -q "$DEFAULT_BRANCH"
  die "acceptance criteria are uncovered on the branch"
}
say "every criterion covered"

# ---------------------------------------------------------------- risk
# If a host stack ships a classifier, it decides. Absent one, fail closed: a project with no way to
# judge risk does not get automatic merging.
CLASSIFIER=""
for candidate in stacks/*/scripts/classify-risk.py; do
  [[ -x "$candidate" ]] && CLASSIFIER="$candidate" && break
done

if [[ -z "$CLASSIFIER" ]]; then
  git checkout -q "$DEFAULT_BRANCH"
  die "no risk classifier found in any active stack module. Without one there is nothing deciding what
is safe to merge unreviewed, so nothing is."
fi

if ! "$CLASSIFIER" "$(git merge-base HEAD "$DEFAULT_BRANCH")" >/dev/null 2>&1; then
  echo
  "$CLASSIFIER" "$(git merge-base HEAD "$DEFAULT_BRANCH")" 2>&1 | sed 's/^/  /'
  git checkout -q "$DEFAULT_BRANCH"
  echo
  die "risk classifier says this needs a human. Branch $BRANCH is left in place for you to review."
fi
say "risk: auto-mergeable"

if $DRY_RUN; then
  git checkout -q "$DEFAULT_BRANCH"
  echo "Dry run — every check passed. Would merge $BRANCH into $DEFAULT_BRANCH."
  exit 0
fi

# ---------------------------------------------------------------- merge
git checkout -q "$DEFAULT_BRANCH" || die "could not switch to $DEFAULT_BRANCH"

# --no-ff keeps the run's work identifiable as a unit, so reverting it is one commit rather than an
# archaeology exercise. That matters more than a tidy history when something lands at 3am.
if ! git merge --no-ff --no-edit -m "Merge $SPEC_ID (unattended run)" "$BRANCH" >/dev/null 2>&1; then
  git merge --abort 2>/dev/null
  die "merge conflicted. $BRANCH is intact; resolve it by hand."
fi
say "merged $BRANCH into $DEFAULT_BRANCH"

# One last check, on the merge result itself. A clean merge of two green branches can still be broken.
if ! echo '{}' | .claude/hooks/verify-gate.py >/dev/null 2>&1; then
  git reset -q --hard HEAD~1
  die "gates fail AFTER merging, though both sides were green. Merge reverted; $BRANCH is intact.
This is a semantic conflict — the kind git cannot see."
fi
say "gates green after merge"

if [[ "$PUSH_AFTER" == "true" ]]; then
  git push -q origin "$DEFAULT_BRANCH" || die "merged locally but the push failed. $DEFAULT_BRANCH is ahead of origin."
  say "pushed $DEFAULT_BRANCH"
else
  say "not pushed — autonomy.pushAfterMerge is off"
fi

git branch -q -d "$BRANCH" 2>/dev/null && say "deleted $BRANCH"
echo
echo "MERGED — $SPEC_ID is on $DEFAULT_BRANCH"
