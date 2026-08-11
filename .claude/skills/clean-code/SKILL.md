---
name: clean-code
description: Use when writing or reviewing any code, when deciding whether to extract a shared abstraction, when a file is growing large, or when the same logic appears in more than one place.
---

# Clean code

The measure is not elegance. It is whether the next person — often you, six months on, with none of
today's context — can read it, change it safely, and know they didn't break something.

## Duplication

**Three occurrences, then extract.** Not two.

Two similar pieces of code are frequently coincidence. They look alike today and diverge next week,
because they answer to different requirements. Extract at two and you get an abstraction with a boolean
parameter, then two, then a shape nobody can follow that serves neither caller well.

The wrong abstraction costs more than the duplication it replaced, because duplication is easy to delete
and a bad abstraction is load-bearing.

**Duplicated *knowledge* is different from duplicated *text*.** A tax rate, a validation rule, a status
name — one authoritative definition, always, from the first occurrence. Two functions that happen to have
the same five lines but answer to different rules are not duplication.

Ask: *when this changes, must every copy change together?* Yes means it is one thing. No means it is two
things that currently look alike.

## Naming

Naming is the highest-leverage thing in this document. Most unreadable code is well-structured code with
names that lie.

- Name what it *is*, not what it does internally. `activeSubscribers`, not `filterUsersLoop`
- Say the unit: `timeoutMs`, `priceInCents`, `maxRetries`
- Booleans read as assertions: `isExpired`, `hasAccess`, `shouldRetry`
- No abbreviations except genuinely universal ones. `res` could be response, result, resource, or reserved
- A long clear name beats a short cryptic one every time
- Never let a name become inaccurate. A renamed concept must be renamed everywhere — a stale name is worse
  than no name, because it is trusted

## Functions

**One reason to exist.** If you cannot name a function without "and", it is doing two things.

**Keep the levels of abstraction consistent.** A function that orchestrates three high-level steps should
not also contain string parsing. Mixed levels are what makes code exhausting to read.

**Return early.** Handle the edge cases and get out. Deeply nested conditionals hide the main path.

**Prefer arguments to hidden state.** A function whose result depends only on what it was given can be
tested, moved, and reasoned about. One that reads ambient state cannot.

**Boolean parameters are a smell.** `render(true)` tells the reader nothing. It usually means two
functions wearing a trench coat.

## Comments

Code says *what*. Comments say *why*.

Write a comment when the reason is not visible from the code: a non-obvious constraint, a workaround for
a specific bug, a deliberate choice that looks wrong, an ordering that matters.

Do not write a comment that restates the line beneath it. Do not leave commented-out code — that is what
version control is for. Do not write a comment that will go stale; if it must be true, assert it in a test.

The best comment is usually a better name.

## Structure

**Group by feature, not by kind.** Everything belonging to one capability lives together. Directories named
after technical layers force you to open five folders to understand one thing, and they make it impossible
to see what a change touches.

**Dependencies point one way.** When a feature imports from another feature which imports back, neither
can be understood, tested, or removed alone. Push shared things down into something both depend on.

**Keep the public surface small.** Export what callers need. Everything else stays private so it can be
changed without an audit.

## Errors

**Fail loudly and early.** An error swallowed silently becomes a bug report about wrong data six weeks
later, with nothing to go on.

**Handle it where you can do something about it.** Catching an error only to log and rethrow adds noise.
Catch it where there is a decision to make.

**Error messages are for whoever reads them at 3am.** Include what was being attempted and with what.
"Request failed" is useless. Never expose internals to end users, and never hide them from logs.

**Never catch everything and continue.** A bare catch-all around a block hides the failure you most need
to see.

## Changing existing code

**Match what is already there.** Consistency beats your preference. A file written in one style and edited
in another is harder to read than either style alone.

**Separate refactoring from behaviour change.** Do one or the other in a change, never both — otherwise a
reviewer cannot tell which edits were meant to alter behaviour, and neither can you.

**Leave it a little better.** Fix the name you had to decipher. Do not rewrite the module while you are
there — an unrelated large refactor buried in a small change is how regressions ship.

**Delete dead code.** Unreferenced functions, unused flags, commented-out blocks, TODOs from years ago.
It is all in version control. Every line kept "just in case" is a line someone has to read and wonder about.

## Reviewing your own work before calling it done

- [ ] Would someone with no context understand this?
- [ ] Does every name still mean what it says?
- [ ] Is anything here duplicated *knowledge* rather than duplicated text?
- [ ] Is there an abstraction extracted from only two cases?
- [ ] Are the errors handled where something can be done about them?
- [ ] Is there anything left in that is not being used?
- [ ] Does this match the surrounding code?
