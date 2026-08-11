---
name: component-design
description: Use when creating a reusable UI component, deciding whether something should be shared, adding a prop to an existing component, or reviewing whether a component is too specific or too general.
---

# Component design

The goal is a small set of components that compose into anything, not a large set that each do one screen.

## Before creating anything

**Look for what already exists.** Check the component inventory in `docs/map/` and the existing component
directory. Duplicated components are the single biggest cause of an interface drifting out of consistency
— two buttons that are 90% the same guarantee that a change lands in one of them.

If something close exists, extend it or compose with it. Only create a new one when the behaviour is
genuinely different, not when the styling is.

**Build it specific first.** Write it where it is used. When a second place needs it, look at what the two
uses actually share. When a third arrives, extract. Generalising from one use produces a component shaped
by a single screen's accident.

## When to share

Share when the same **behaviour and meaning** appear in several places.

Do not share because two things look alike. A card in a settings list and a card in a marketing page may
be visually identical today and diverge the moment either is designed further — and then you have a
component with a `variant` prop that nothing can safely change.

The test: *if this changes, must every use change with it?* If yes, share it. If no, they are different
things that currently resemble each other.

## Prop design

**Props describe intent, not appearance.** `variant="danger"` survives a redesign; `color="red"` becomes a
lie the moment danger stops being red.

**Every prop is a permanent commitment.** It must be documented, tested in each of its states, and
supported forever. A component with fifteen props is usually several components that were never separated.

**Watch for the boolean pile-up.** Three booleans is eight combinations, most of which nobody intended and
none of which are tested. When you reach for a third, the component is doing too much — split it, or accept
composition instead.

**Prefer composition to configuration.** Passing content in is more flexible than a prop for every possible
arrangement, and it doesn't grow the API each time a new case appears.

**Give sensible defaults** so the common case is short, and make the required props genuinely required.

## The states — build all of them

A component that fetches or submits has four states, and all four are part of the component, not an
afterthought for whoever uses it:

- **Loading** — matching the shape of the real content
- **Empty** — explaining why, and what to do
- **Error** — in plain language, with a way forward
- **Success** — the content

Each one gets its own story or example so it can be seen and reviewed in isolation. A component whose
error state has never been looked at has an error state that does not work.

## Accessibility is part of the component

Build it in once, here, so every use inherits it. This is the main reason shared components are worth
having at all.

- Correct semantic element underneath
- Keyboard operation complete for what it is
- Focus visible and managed
- Labels and state exposed programmatically, not only visually
- Contrast checked in every variant, including disabled and hover

A shared component with an accessibility bug ships that bug everywhere at once — which is also why fixing
it once fixes it everywhere.

## Styling

**Use the project's design tokens.** Never a raw colour, spacing value or font size in a component. A
hard-coded value is invisible to theming and will be missed in every future change.

If a token does not exist for what you need, that is a design decision — add the token deliberately, do not
hard-code around it.

**Let the parent control layout.** A component should size itself to its content and not impose outer
margins. Margins that belong to the component fight every layout it is placed in.

## Documenting

Each shared component needs, next to the code:

- What it is for, in one sentence
- **When to use it, and when to use something else instead.** This is the most valuable line, and the
  most often omitted — it is what stops the fourth near-duplicate being created
- Every prop, its type, whether it is required, and its default
- An example of each state and each variant

That documentation is what an agent reads to decide whether to reuse or rebuild. Missing it guarantees
rebuilding.

## Review before calling it done

- [ ] Nothing similar already existed
- [ ] The props describe intent, not appearance
- [ ] No prop exists for a case that hasn't happened yet
- [ ] All four states built and visible in isolation
- [ ] Keyboard operable end to end
- [ ] No hard-coded colours, spacing or sizes
- [ ] No outer margins baked in
- [ ] "When to use something else" is written down

## Anti-patterns

- A component named after where it is used rather than what it is
- A `variant` prop with a value used exactly once
- Extracting a shared component from a single use
- A shared component that reaches into global state, so it only works in one place
- Copying a component to change one thing
- A component that takes a config object describing an entire screen
