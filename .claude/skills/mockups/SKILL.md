---
name: mockups
description: Use before implementing anything with a user interface, when the user asks to see a design, when generating design options to choose between, or when establishing a project's visual foundations.
---

# Mockups

Nothing with a user interface gets implemented before its design has been seen and approved. Design
decided during implementation is design nobody reviewed.

Approval is recorded by `.claude/scripts/mockup.py`, which hashes what the reviewer actually saw: the
mockup files, and **everything under `docs/mockups/_foundations/`** — tokens, brand assets, fonts,
icons. Change any of it and the approval is void. This is deliberate: an approval you can quietly
invalidate is not a gate.

So anything a mockup renders against belongs in `_foundations/`. An asset kept elsewhere is outside
the lock, and can be swapped underneath an approved design without anything noticing.

## Two tiers

**Foundations** — once per project, before any screen. Colour ramps, type scale, spacing, radius,
elevation, motion, and the base controls. Reviewed as a single page showing every token and primitive
together.

Foundations **become the implementation**. They are the theme and the base components, not a picture of
them.

**Screens** — per spec. Built from the already-approved foundations.

Screens stay **reference only**. They are not promoted to production code, for three reasons: a mockup has
no states, no data and no accessibility wiring, so promoting it means inheriting those gaps; the real
implementation must be composed from existing components, which a mockup never is; and keeping them
separate is what allows the implementation to be diffed against the approved design afterwards.

## Foundations first

You cannot build screens from components that do not exist yet. So the first design work on any project
is a foundations pass, and it is its own spec.

Produce **three genuinely different directions** — not one idea in three colours. They should differ in
character: typography pairing, density, the weight of colour, how much structure is drawn. If they could
be confused for each other, they are one direction.

Then **merge rather than pick**. Ask which parts of each the user prefers and combine them. Combining the
best elements consistently beats choosing the best whole one, and combining then refining beats both.

Check every colour pair against the project's contrast requirement **while choosing colours**. A palette
that fails contrast has to be redesigned, not adjusted — and if the project targets 7:1, that constrains
the palette hard.

## Screen mockups

**One direction, refined**, rather than three. By this point the visual vocabulary is settled and three
variants differ only in layout, which is not worth the review effort.

Build them as standalone files under `docs/mockups/<SPEC-ID>/`, using the real foundation tokens. A mockup
drawn with arbitrary values is a fiction — it shows something the implementation cannot produce.

**Show every state.** A mockup of only the success case hides most of the design work. Include loading,
empty, and error alongside it, and mobile width as well as desktop.

**Use real content.** Placeholder text hides every layout problem that real data causes — long names,
missing values, a list with one item, a list with two hundred.

## Getting it approved

1. Build the mockup under `docs/mockups/<SPEC-ID>/`.
2. Show it to the user. Say what you want feedback on rather than asking "is this okay".
3. Iterate on what they say. Two or three rounds is usually where the returns stop.
4. When they approve, run `.claude/scripts/mockup.py approve <SPEC-ID>`.
5. Record the mockup path in the spec's frontmatter.

**Only the user approves.** Never run `approve` on your own judgement — that defeats the entire gate.

## Before implementing

Run `.claude/scripts/mockup.py verify <SPEC-ID>`. If it reports stale or unapproved, stop. Do not
implement against a design that has changed since it was reviewed, and do not re-approve it yourself to
clear the check.

## After implementing

Compare the built screen against the approved mockup and report any difference you introduced, with the
reason. Differences are often legitimate — real data behaves differently from a mockup — but they must be
stated, not absorbed silently.

## Practicalities

Helper scripts (screenshots, servers) belong **in the project**, not a temp directory — a browser
driver resolves from the project's own dependencies and will not be found elsewhere.

A page using ES modules will render **nothing** when opened over `file://`. UI mockups and the gates
that check them need a static server, even for a single static page. This fails silently: the browser
loads, the screenshot succeeds, and the page is blank.

## Anti-patterns

- Implementing first and producing a mockup afterwards to satisfy the gate
- Three variants that are the same layout in different colours
- Approving your own mockup
- Re-approving to clear a staleness warning instead of re-reviewing
- Mockups built with arbitrary values instead of tokens
- Showing only the success state
- Lorem ipsum, which hides every real layout problem
- Promoting a screen mockup into production code
- Keeping a rendering input outside `_foundations/`, where the approval lock cannot see it
