---
name: spec-authoring
description: Use when writing, refining, clarifying or reviewing a Trellis spec, when the user describes something they want built, or when a spec must be checked for readiness before an unattended run.
---

# Spec authoring

A spec is a contract that an unattended run must be able to satisfy **without asking a single question**.
Everything ambiguous is resolved here, while the user is present. This is the only phase where you
interrogate; implementation runs silent.

## Readiness checklist — verify before declaring a spec ready

**Run `.claude/scripts/spec-lint.py <id>`.** It enforces every mechanical check below, and the
pre-commit hook runs it too, so a failing spec cannot reach `ready`. The list is here so you know what
it checks and why — not so you can check it by eye.

- [ ] `Open questions` is empty
- [ ] Every acceptance criterion is in EARS form and observable from outside the system
- [ ] Every acceptance criterion is testable — you can name the test that would fail if it broke
- [ ] `estimate` is set and does not exceed `standards.specMaxMinutes` in `trellis.json`
- [ ] `depends` lists every spec that must land first, and none of them are unfinished
- [ ] `Out of scope` is non-empty — if nothing is out of scope, the boundary hasn't been thought about
- [ ] If `surfaces` includes `ui`: every state in `States` is filled in, and `mockup` points at an approved design
- [ ] No criterion contains "etc.", "and so on", "appropriate", "reasonable", "properly", "as needed", or "handle"
- [ ] Nothing in the spec requires a decision you have not been given

If any line fails, the status is `clarifying`, not `ready`.

## The interview

Your job is to find the decisions the implementation would otherwise have to invent. Ask about all of
these before declaring readiness. Ask in batches, not one at a time.

**Behaviour**
- What exactly happens on success? What does the user see next?
- What are the failure modes, and what happens for each?
- What are the boundaries — empty, one, many, very many, too many?
- What happens on a repeat action, a double submit, a stale page?

**Data**
- What is stored, and what is derived?
- What is required, what is optional, what is validated and how?
- What happens to existing data — is a migration needed?
- Who can see it, who can change it?

**Interface** *(when `surfaces` includes `ui`)*
- What does it look like while loading? With nothing in it? When it fails?
- What is the exact copy? Do not let copy be decided during implementation.
- What happens on a small screen?
- What is focused first, and what is the tab order?

**Edges**
- Permissions — what does an unauthorised user see?
- Concurrency — what if two people do this at once?
- Rate limits, abuse, cost

**Explicitly out of scope**
- What is a reasonable person going to assume is included that isn't?

## Writing acceptance criteria

Each criterion becomes at least one test. Write them so the test is obvious.

**Bad** — untestable, hides three decisions:
> The system shall handle invalid input appropriately.

**Good** — three criteria, three tests:
> 1. If the email field does not contain an `@`, then the system shall display "Enter a valid email address" beneath the field and shall not submit the form.
> 2. If the form is submitted while a submission is already in flight, then the system shall ignore the second submission.
> 3. When submission fails with a network error, the system shall keep the entered values and display "Something went wrong. Try again."

Notice the third criterion specifies the copy. If you don't, implementation will invent it.

## Sizing

`standards.specMaxMinutes` exists because an unattended run's reliability decays with length — the
probability of finishing correctly drops far faster than the time budget suggests. A spec that estimates
above the cap must be split, not attempted.

Split **vertically**, not by layer. Each spec should be independently shippable and independently
testable. "The database table" is not a spec; "a user can save a draft" is.

When splitting, set `depends` so the order is unambiguous, and make sure each piece still delivers
something observable.

## Status lifecycle

```
draft ──▶ clarifying ──▶ ready ──▶ building ──▶ verifying ──▶ done
                            ▲                        │
                            └──────── blocked ◀──────┘
```

- **draft** — being written
- **clarifying** — open questions outstanding; needs the user
- **ready** — passes the readiness checklist; an unattended run may pick it up
- **building** — implementation in progress
- **verifying** — implemented, gates running
- **done** — all gates green, every criterion has a passing test, merged
- **blocked** — a run stopped; `## Blocked` records the single specific question

Status is stored in frontmatter but must reflect reality. Never mark `done` on the strength of your own
assessment — `done` means the gates passed.

## When you are the one implementing

Read the spec fully before writing anything. If you find an ambiguity mid-implementation:

- **If a human is present**, stop and ask. That is the correct behaviour, not a failure.
- **If running unattended**, stop, set status to `blocked`, and write `## Blocked` containing exactly one
  clearly-stated question. Do not guess. Do not implement a "reasonable default" and note it. A blocked
  spec costs one morning decision; a guessed spec costs trust in the whole system.

## Anti-patterns

- Answering an open question in conversation and leaving it in `Open questions` — move it into the spec
- Acceptance criteria that describe implementation rather than behaviour
- A spec with no `Out of scope`
- Marking `ready` because the user seems impatient
- Splitting by layer, producing specs that can't be tested alone
- Copy invented during implementation
