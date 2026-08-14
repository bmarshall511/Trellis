---
description: Build the next ready spec — same branch, report and delivery as an unattended run
argument-hint: [optional spec id, otherwise the next ready one]
---

Implement a spec. Target: **$ARGUMENTS** (if empty, pick the lowest-id spec that is `ready`, has all
dependencies `done`, and has an approved mockup if `surfaces` includes `ui`).

Load the `spec-authoring`, `testing` and `clean-code` skills.

**This produces exactly the same artifacts as an unattended run** — the `agent/<spec-id>` branch and
the run report — so the work can be delivered by the same path. Interactive and unattended differ only
in whether you may ask questions, never in what they leave behind. A spec built without these cannot
be delivered by the automation, and nothing would tell you until you tried.

## Before starting

1. Read `trellis.json` and load every module named in `stacks/`.
2. Read the spec in full. Read its mockup if it has one.
3. Run `.claude/scripts/spec-lint.py <id>`. **If it fails, stop and report — do not implement an unready spec.**
4. Verify the approved mockup still matches its recorded hash. If it doesn't, approval is revoked; stop.
5. **Create the branch:** `git checkout -b agent/<spec-id>` from a clean default branch. A
   description may follow the id — `agent/SPEC-024-revoke-an-invite-link` delivers the same as
   `agent/SPEC-024` — but only one branch per spec id may exist, or delivery cannot tell which
   holds the work.
6. Set status to `building`.

## While building

- Work only within the spec's scope. `Out of scope` is binding.
- Every acceptance criterion gets at least one test that would fail if that criterion broke.
- A human is present here, so **ask** when something is ambiguous. That is the difference between this
  and an unattended run, and it is the right thing to do.
- Commit in logical commits as you go.

## Before claiming completion

Set status to `verifying`, then run every gate declared in `trellis.json`, stopping at the first failure:

```
types → lint → test → a11y → perf
```

Then verify the contract:

- [ ] `.claude/scripts/spec-coverage.py <id>` shows every criterion covered
- [ ] All gates green
- [ ] If `surfaces` includes `ui`: the implementation matches the approved mockup
- [ ] Nothing outside the spec's scope was changed

Only then set status to `done`.

**Never mark `done` on your own assessment.** `done` means the gates passed and every criterion has a
test. If you cannot show that list, the spec is not done.

## Then deliver it

```bash
.claude/scripts/write-run-report.sh <spec-id> DONE
```

Then, if `autonomy.mayMerge` is set in `trellis.json`:

| `mergeVia` | Run |
|---|---|
| `pull-request` | `stacks/github/scripts/deliver-run.sh <spec-id>` |
| `local` | `.claude/scripts/merge-run.sh <spec-id>` |

Run `deliver-run.sh` in the background, writing to a log, and poll it — it waits for CI, which takes
longer than a foreground command is allowed to run, and being killed mid-flight leaves the branch
pushed and the pull request open:

```bash
mkdir -p docs/runs && stacks/github/scripts/deliver-run.sh <spec-id> > docs/runs/<spec-id>-deliver.log 2>&1 &
```

Do not end the turn until that log reports a result.

**Run the script. Do not open a pull request or merge by hand.** Those scripts re-run the gates on the
branch, re-check coverage, ask the risk classifier, and — for pull requests — wait for CI and fix what
it finds. Doing any of it manually skips every one of those checks, and produces a pull request nobody
will merge automatically because the report and branch it looks for were never made.

If `mayMerge` is not set, stop here and tell the user the branch is ready.

## Report

Finish with: the spec id and title, each acceptance criterion and the test covering it, gate results,
the delivery outcome, files changed, and anything you noticed but deliberately did not do.
