---
description: Run ready specs unattended — implements, verifies, reports, halts on the first blocker
argument-hint: [spec-id, or blank for the whole ready queue]
---

Run: **$ARGUMENTS** (blank runs every ready spec in dependency order)

This is the unattended path. Do not do the work yourself in this session — invoke the runner, which
launches a separate agent under a locked-down profile:

```bash
.claude/scripts/run-spec.sh <spec-id>        # one spec
.claude/scripts/run-queue.sh --limit 3       # the queue, halting on the first blocker
```

Add `--dry-run` to run preflight only. Preflight refuses to start on a dirty tree, an unready spec, an
unapproved mockup, or already-failing gates — a run that begins from a broken baseline cannot tell its
own failures from inherited ones.

Each run ends in exactly one of:

| | |
|---|---|
| `DONE` | every gate green, every criterion covered |
| `BLOCKED` | stopped and wrote one specific question — correct behaviour, not a failure |
| `FAILED` | claimed completion the evidence does not support |
| `TAMPERED` | guardrail files changed during the run; nothing it produced can be trusted |

Reports land in `docs/runs/`. Branches are local and **unpushed** — the runner cannot publish or merge.

Afterwards, report to the user: outcome per spec, and for anything blocked, the question verbatim. Do
not summarise a `FAILED` as partial progress.
