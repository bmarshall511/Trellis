---
name: stack-selection
description: Use at the start of a new project, when trellis.json does not exist yet, or when the user asks what to build something with. Recommends technologies based on that project's actual requirements rather than defaults.
---

# Choosing a stack

Trellis has no default stack. A project's technology is a **recommendation you make for that project**,
based on what it actually needs — not a template you apply.

Your job is to ask enough to make a real recommendation, explain the trade-off in one line each, and let
the user decide.

## Never do this

- Assume a stack because it is popular, or because the last project used it
- Start scaffolding before the user has agreed to the choices
- Present a stack as settled fact rather than a recommendation
- Recommend something you cannot justify from a stated requirement
- Add a technology "for later" — every dependency is a permanent maintenance cost

If you catch yourself writing `package.json` before the user has said yes, stop.

## What to ask

Ask these before recommending anything. Batch them — do not interrogate one line at a time.

**What is it**
- What does this do, for whom, and what does success look like?
- Is there a user interface, an API, a command line tool, or a library? (This sets `type` in `trellis.json`.)
- Roughly how many users, and are they public or authenticated?

**What it must handle**
- Does data need to persist? Relational, document, or files?
- Does anything need to happen in real time?
- Does it work offline?
- Does it send email, take payments, handle uploads, run scheduled work?
- Does it need to be found by search engines?

**Constraints**
- What is the budget, monthly? Free tier only is a legitimate and common answer.
- Where does it need to run? Any hosting already in place?
- Anything the user already knows or already runs that would be cheaper to reuse?
- Any compliance or data-residency requirement?

**Longevity**
- Is this a throwaway experiment or something maintained for years?
- Will anyone else work on it?

## How to recommend

Give **one recommendation per layer**, with a one-line reason tied to something the user said, plus the
main alternative and when it would win. Not a survey — a decision they can accept or push back on.

```
Framework   <choice>    because <requirement they stated>
                        alternative: <x>, better if <condition>
Database    ...
Hosting     ...
Testing     ...
```

Then state the total monthly cost at the scale they described, and what the first thing to break will be
as it grows.

### Weighting

1. **Requirements they stated.** Offline support, SEO, real-time, and budget eliminate more options than
   anything else. Start there.
2. **Boring beats novel.** For anything maintained longer than a few months, prefer technology with a long
   support history and a large body of existing answers. An agent writes better code in a well-documented
   ecosystem, and you are the one who will maintain it.
3. **Fewer pieces.** Every additional service is another failure mode, another bill, another set of
   credentials. Reach for one that does two jobs adequately over two that each do one job well, unless a
   stated requirement demands otherwise.
4. **Free tiers are a real constraint**, not a preference to design around. Check the actual limits and
   name the threshold where each breaks.

### Where cost actually bites

Ask about volume before recommending anything usage-priced. The failures that hurt are not monthly fees —
they are per-unit quotas that stop working mid-month. Image transformations, function invocations,
bandwidth, build minutes, monthly active users, email per day. For anything usage-priced, say what the
free allowance is and roughly what usage exhausts it.

## Once decided

1. Write `trellis.json` — validate it against `trellis.schema.json`.
2. For each chosen technology, check whether `stacks/<name>/` exists.
   - **It exists:** load it. It holds current, verified knowledge for that technology.
   - **It does not:** say so. Offer to create it with `/stack-add <name>`. Until then you are working from
     general knowledge, which may be out of date — verify anything version-specific before relying on it.
3. Wire up the gate commands so `verify` actually runs. **A project is not set up until every declared
   gate runs and passes on an empty project.** Prove it before writing application code.
4. Record the choices and their reasons in `docs/decisions/`. In six months the reason matters more than
   the choice.

## Recording the decision

Write one file per significant choice, named `docs/decisions/NNN-short-title.md`:

```markdown
# 001 — <the choice>

**Date:** YYYY-MM-DD
**Status:** accepted

## Context
What the project needs that made this a question.

## Decision
What was chosen.

## Alternatives
What else was considered, and the specific reason it lost.

## Consequences
What this makes easy. What this makes hard. What would have to be true to revisit it.
```

The Alternatives section is the valuable one. It stops the same debate being reopened, and it tells a
future reader whether the original reasoning still holds.
