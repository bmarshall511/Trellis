---
description: Build the next ready spec — implementation runs without questions
argument-hint: [optional spec id, otherwise the next ready one]
---

Implement a spec. Target: **$ARGUMENTS** (if empty, pick the lowest-id spec that is `ready`, has all
dependencies `done`, and has an approved mockup if `surfaces` includes `ui`).

Load the `spec-authoring` and `spec-implementation` skills.

## Before starting

1. Read `trellis.json` and load every module named in `stacks/`.
2. Read the spec in full. Read its mockup if it has one.
3. Re-run the readiness checklist. **If it fails, stop and report — do not implement an unready spec.**
4. Verify the approved mockup still matches its recorded hash. If it doesn't, approval is revoked; stop.
5. Set status to `building`.

## While building

- Work only within the spec's scope. `Out of scope` is binding.
- Every acceptance criterion gets at least one test that would fail if that criterion broke.
- If a human is present and something is ambiguous, **ask**. That is correct behaviour.
- If running unattended, do not ask and do not guess. Set status to `blocked`, write a `## Blocked`
  section containing exactly one specific question, and stop.

## Before claiming completion

Set status to `verifying`, then run every gate declared in `trellis.json`:

```
verify:types → verify:lint → verify:test → verify:a11y → verify:perf
```

Stop at the first failure and fix it. If a gate fails more than `autonomy.maxRepairAttempts` times, stop
and write `## Blocked` with the failing output.

Then verify the contract itself:

- [ ] Every acceptance criterion maps to a named test — list them, criterion by criterion
- [ ] All gates green
- [ ] If `surfaces` includes `ui`: the implementation matches the approved mockup
- [ ] Nothing outside the spec's scope was changed
- [ ] No file matching `autonomy.requiresApproval` was touched — if one was, the change needs a human

Only then set status to `done`.

**Never mark `done` on your own assessment.** `done` means the gates passed and every criterion has a
test. If you cannot show that list, the spec is not done.

## Report

Finish with: the spec id and title, each acceptance criterion and the test covering it, gate results,
files changed, and anything you noticed but deliberately did not do.
