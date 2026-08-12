---
description: Deliver finished spec work — PR, CI, merge — through the sanctioned path
argument-hint: [spec id, or blank for the current branch]
---

Deliver: **$ARGUMENTS** (blank: infer the spec id from the current `agent/<id>` branch).

Use this when a spec is finished and needs to reach the default branch — including work built with
`/spec-next`, which produces the same branch and report an unattended run does.

## Do not do this by hand

There is one sanctioned path, and it is a script:

| `autonomy.mergeVia` | Command |
|---|---|
| `pull-request` | `stacks/github/scripts/deliver-run.sh <spec-id>` |
| `local` | `.claude/scripts/merge-run.sh <spec-id>` |

**Never `gh pr create` or `gh pr merge` yourself.** Not because merging is forbidden — it isn't, the
scripts do it — but because doing it manually skips every check that makes the merge defensible: the
gates re-run on the branch, the coverage re-check, the risk classifier, and for pull requests the CI
wait and the repair loop.

A pull request opened by hand also produces one nobody will merge automatically, because the branch
and report the delivery script looks for were never created.

## If something is missing

**No run report** (`docs/runs/<id>.md`): the work was built without one. Write it:

```bash
.claude/scripts/write-run-report.sh <spec-id> DONE
```

Only after confirming the gates pass and coverage is complete — the report states those as fact, so
writing it against red gates is writing something untrue.

**Not on `agent/<id>`**: the delivery script looks for that branch specifically. Rename with
`git branch -m agent/<spec-id>`, or move the commits onto a correctly named branch.

**`autonomy.mayMerge` not set**: nothing delivers automatically. Say so, and stop — do not merge by
hand as a substitute.

## What each outcome means

| Exit | Meaning |
|---|---|
| 0 | Merged, and local default branch fast-forwarded — ready for the next spec |
| 1 | CI failed past the repair budget, timed out, or the merge was refused. The PR is open |
| 3 | The risk classifier says a human must review. The PR is open, labelled, and will not self-merge |

For 3, tell the user which rule fired and why, quoting the classifier. That is a decision for them,
not a problem to solve.
