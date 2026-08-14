#!/usr/bin/env bash
# Publishes a completed unattended run as a pull request.
#
# Deliberately NOT part of the run. The runner produces a local branch and stops; publishing is a
# separate step, so the agent never holds the ability to put anything in front of CI or a reviewer.
# The commands this uses are on the agent's deny list.
#
# Usage: publish-run.sh <spec-id> [--draft]
set -uo pipefail
SPEC_ID="${1:-}"; DRAFT=""
[[ "${2:-}" == "--draft" ]] && DRAFT="--draft"
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT" || exit 1
STACK="$(dirname "$(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")")/github"

die() { echo "publish-run: $*" >&2; exit 1; }
[[ -n "$SPEC_ID" ]] || die "usage: publish-run.sh <spec-id> [--draft]"
command -v gh >/dev/null || die "gh is not installed"

# Accepts agent/<id> and agent/<id>-<description>. Four scripts hardcoded the first form while the
# second is what people type, so a finished build failed at the last step naming a branch nobody made.
BRANCH="$(.claude/scripts/spec-branch.sh "$SPEC_ID")" || exit 1
REPORT="docs/runs/${SPEC_ID}.md"
git rev-parse --verify "$BRANCH" >/dev/null 2>&1 || die "no branch $BRANCH — has the run happened?"
[[ -f "$REPORT" ]] || die "no run report at $REPORT"

OUTCOME="$(grep -m1 '^\*\*Outcome:\*\*' "$REPORT" | sed 's/.*:\*\* //')"
case "$OUTCOME" in
  DONE) ;;
  TAMPERED) die "run was TAMPERED. Nothing it produced is trustworthy — inspect the branch, do not publish it." ;;
  *) die "run outcome was $OUTCOME, not DONE. Publish only completed runs." ;;
esac

git checkout -q "$BRANCH" || die "could not switch to $BRANCH"

# Classify before publishing, so the label is on the pull request from the moment it exists rather
# than arriving after someone has already looked at it.
RISK_JSON="$("$STACK/scripts/classify-risk.py" --json 2>/dev/null)"
RISK="$(printf '%s' "$RISK_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["decision"])' 2>/dev/null || echo needs-human)"
REASONS="$(printf '%s' "$RISK_JSON" | python3 -c '
import json,sys
d=json.load(sys.stdin)
for f in d.get("files", []):
    if f["decision"] == "needs-human":
        print(f"- `{f[\"path\"]}` — [{f[\"rule\"]}] {f[\"reason\"]}")
' 2>/dev/null)"

BODY="$(cat "$REPORT")

---

## Risk classification

**$RISK**
${REASONS:-Every changed file is auto-mergeable under the current policy.}

Policy: \`stacks/github/risk-policy.json\`. Re-run with \`stacks/github/scripts/classify-risk.py\`.

---

Produced by an unattended Trellis run. The verdict above came from the gates and the coverage mapper,
not from the agent's own account of what it did."

git push -q --set-upstream origin "$BRANCH" || die "push failed"

LABELS="agent-run"
[[ "$RISK" == "needs-human" ]] && LABELS="$LABELS,needs-human"

gh pr create --title "$SPEC_ID: $(grep -m1 '^title:' docs/specs/${SPEC_ID}*.md | sed 's/title: //')" \
  --body "$BODY" --label "$LABELS" $DRAFT || die "could not create the pull request"

echo
echo "Published. Risk: $RISK"
if [[ "$RISK" == "needs-human" ]]; then
  echo "Labelled needs-human — auto-merge will not apply. Review it yourself."
else
  echo "Auto-mergeable once checks pass. Enable with: gh pr merge --auto --squash"
fi
