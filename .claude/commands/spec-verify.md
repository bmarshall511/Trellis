---
description: Prove a spec is actually done — every criterion tested, every gate green
argument-hint: [spec id, or all]
---

Verify: **$ARGUMENTS** (default: every spec marked `done` or `verifying`).

This is an audit, not a build. Change nothing. Report what is true.

For each spec:

1. **Criterion coverage.** Run `.claude/scripts/spec-coverage.py <id>`, which produces the mapping.
   Then judge each covered criterion by hand:

   A criterion with no test is a failure. A test that exists but would still pass if the behaviour broke
   is also a failure — say so rather than counting it.

2. **Gates.** Run every gate in `trellis.json`. Report actual output, not a summary.

3. **Mockup**, if `surfaces` includes `ui`: run `.claude/scripts/mockup.py verify <id>` and compare the
   built screen against the approved design. Report any difference.

4. **Scope.** Did the change touch anything outside what the spec described, or anything matching
   `autonomy.requiresApproval`?

Finish with a verdict per spec: **verified**, or **not done** with the specific reason.

If a spec claims `done` and is not, say so plainly and correct its status. A spec marked done that isn't
is worse than one marked in-progress, because nobody looks at it again.
