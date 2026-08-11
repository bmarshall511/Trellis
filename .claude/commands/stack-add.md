---
description: Research a technology and add it as a stack module
argument-hint: <name> [--refresh]
---

Add or refresh the stack module for: **$ARGUMENTS**

Read `stacks/README.md` for the format first.

## Research it properly

**Do not write this from memory.** Every serious error found while building Trellis came from trusting
recalled knowledge: a package that had been deprecated, a config key that had moved and silently did
nothing, pricing wrong by two orders of magnitude, a CLI flag ignored on older versions.

Check against primary sources — the official documentation, the package registry, the vendor's own
pricing page, the repository's releases. Note the date on anything you rely on.

Find specifically:

- **Version traps** — config that does nothing in the wrong place, options that moved, packages replaced
- **Quota cliffs** — the number where a free tier stops working, and what happens when it does: a hard
  stop, silent degradation, or an unexpected bill
- **Correct patterns** where the obvious approach is wrong
- **Deprecations**, and what replaced them
- **Destructive commands** the tooling makes possible
- **The gate commands** this stack contributes

## Write it

1. `cp -r stacks/_template stacks/<name>` (skip if refreshing)
2. `SKILL.md` — only what is specific and non-obvious. General practice lives in the core skills;
   repeating it costs context in every session and teaches nothing
3. `guard.json` — patterns for anything destructive, **each with a test case added to
   `.claude/hooks/tests/guard-cases.json`**, both a blocking case and the safe form that must still be
   allowed. Then run `.claude/hooks/tests/run.py`. A guard pattern with no test is not a guard
4. `VERIFIED` — today's date and exactly what you checked. Be honest about what you did *not* verify
5. `setup/` — any config files that would be broken sitting in an empty repo

## If refreshing

Show what changed since the last verification, especially anything now deprecated or repriced. Those
findings are the entire point of refreshing — surface them rather than quietly editing the file.
