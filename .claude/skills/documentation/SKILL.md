---
name: documentation
description: Use when writing a README, documenting a module or component, recording a decision, or deciding whether something needs explaining at all. Also when documentation has drifted from the code.
---

# Documentation

Write documentation that answers questions the code cannot. Everything else is a liability — it has to be
maintained, and when it stops being true it actively misleads.

## The test

Before writing anything, ask: **could a reader get this by reading the code?**

If yes, do not write it. A comment restating the line beneath it, a README listing the directory
structure, a prop table that duplicates the type definition — these go stale silently and are trusted
anyway. That is worse than their absence.

Write down what the code cannot say:

- **Why** it is like this — the constraint, the trade-off, the thing that was tried and failed
- **When** to use this rather than the alternative
- **What breaks** if you change it
- **What it assumes** that is not enforced anywhere

## Per file

Documentation lives next to what it describes. Separate documentation directories drift within weeks
because nothing prompts anyone to update them.

**Shared components and modules** need, in the file or beside it:
- One sentence on what it is for
- **When to use something else instead.** The most valuable line and the most often omitted — it is what
  stops the fourth near-duplicate being built
- Anything non-obvious about using it correctly

**Everything else** needs nothing, unless there is a why to record.

## Decision records

When a choice has consequences that outlive the conversation, write it down under `docs/decisions/`.
One file per decision, numbered.

```markdown
# 007 — Chose X over Y

**Date:** YYYY-MM-DD
**Status:** accepted        <!-- accepted | superseded by NNN -->

## Context
What made this a question.

## Decision
What was chosen.

## Alternatives
What else was considered, and the specific reason each lost.

## Consequences
What this makes easy. What this makes hard. What would have to change to revisit it.
```

**The Alternatives section is the point.** Without it, the same debate reopens every few months and
nobody can tell whether the original reasoning still holds. "We chose X" is nearly useless; "we chose X
because Y required Z, which was not true for us" tells a future reader exactly when to reconsider.

Record a decision when: a technology was chosen, a standard was deviated from, something was deliberately
not done, or a constraint shaped the design in a way the code does not explain.

Do not record: routine implementation choices, anything obvious from the code, or anything that will not
matter in three months.

## Keeping it true

**Documentation that lies is worse than none**, because it is trusted. A reader who finds no
documentation reads the code; a reader who finds wrong documentation acts on it.

So:

- Update documentation in the same change as the code. Never "later"
- If a name changes, change it everywhere. A stale name is a wrong name
- If you cannot keep something accurate, delete it rather than letting it rot
- When you find documentation that is wrong, fix it or remove it there and then — do not step around it

The generated map (`docs/map/`) is regenerated, never hand-edited. Its directory descriptions come from
each directory's `PURPOSE` file — those are hand-written and are the part worth maintaining.

## Writing it

- Say the thing. "This caches results for 5 minutes" beats "this method is responsible for handling the
  caching of results"
- Write for someone competent who lacks your context, not for a beginner and not for yourself
- Concrete over abstract. An example beats a paragraph
- State constraints as constraints: "must be called before X", not "should generally be called before X"
- No filler. "It should be noted that", "in order to", "simply", "just"

## Anti-patterns

- A README describing the directory structure, which the map already generates
- Comments restating the code
- Documenting what you plan to build
- "TODO: document this"
- A changelog nobody updates
- Commented-out code kept as documentation
- Documentation in a different place from the thing it documents
