---
name: feedback-and-performance
description: Use when building anything a user interacts with — forms, buttons, navigation, data loading, uploads. Also when something feels slow, when adding a loading state, or when reviewing whether an interface responds immediately to input.
---

# Feedback and performance

## The rule

**Every interaction acknowledges itself within 100ms — always, without exception.**

Not "usually". Not "when it's slow". A button that does nothing visible for 300ms reads as broken, and the
user clicks it again. The acknowledgement is not optional garnish; it is part of the interaction.

This is the difference between an interface that feels native and one that feels like a web page.

## The timing budget

These come from how human attention works, not from any framework.

| Elapsed | The user perceives | You must have shown |
|---|---|---|
| **< 100ms** | Instant. Direct manipulation | The result, or acknowledgement that it started |
| **100ms – 1s** | Responsive, but a machine did something | A pending state — disabled control, spinner in place |
| **1s – 10s** | Waiting | Skeleton or progress. Keep the surrounding page usable |
| **> 10s** | Abandoned | Real progress with an estimate, and a way to cancel |

The number that matters most is the first one. Everything after it is damage control.

## Choosing the right feedback

**Under ~300ms** — show nothing extra. A spinner that flashes for 150ms is worse than no spinner; it reads
as a glitch. Where a delay is unavoidable but brief, hold the spinner back behind a short delay so fast
responses never flash.

**Loading content that will have a known shape** — use a skeleton matching the real layout. Not a generic
grey box: matching the actual structure means nothing moves when content arrives.

**A skeleton that does not match the final layout is worse than a spinner**, because it promises a shape
and then breaks it. If you cannot predict the layout, use a spinner.

**An action the user initiated** — the feedback belongs *on the control they touched*. Disable it, show the
pending state inside it, keep its size fixed so nothing jumps. Never put a page-level overlay over an
action that affects one row.

**Something you are confident will succeed** — show the result immediately and reconcile when the server
answers. If it fails, restore the previous state and say clearly what happened. Never silently revert; the
user will believe it worked.

**Never** use a full-page blocking spinner for anything that isn't a full-page navigation. It throws away
everything already on screen and makes a fast app feel slow.

## The states — all four, every time

Anything that loads data has four states. Specify and build all of them. The ones that get skipped are
the ones users hit on their worst day.

- **Loading** — a skeleton of the real shape, or a spinner if the shape is unknown
- **Empty** — explains why it's empty and what to do about it. "No results" is not an empty state; "No
  invoices yet — they'll appear here once you send one" is
- **Error** — says what went wrong in plain language and offers a way forward. Never a raw error code
- **Success** — the content

Add **offline** if the project supports it.

An interface that only handles the success case is unfinished, regardless of whether it passes its tests.

## Layout stability

Nothing may move after it appears. Content jumping while a user is reading — or worse, as they reach for a
button — is one of the most damaging things an interface can do.

- Reserve space for anything that loads in: images, ads, embeds, async content
- Give images explicit dimensions so the space exists before the file arrives
- Size skeletons to the content they replace
- Never insert content above what the user is currently looking at

## Making it actually fast

Feedback masks latency. It does not remove it. Both matter.

**Do not optimise without measuring.** Measure, change one thing, measure again. If the change did not
beat the noise, revert it — a neutral result is a revert, not a keep. Speculative optimisation makes code
harder to read in exchange for nothing.

**The usual causes, roughly in order of how often they are the answer:**

1. **Sequential requests that could be parallel.** Three 200ms calls in a chain is 600ms; together it is
   200ms. This is the most common real cause of a slow page.
2. **Fetching inside a loop.** One query per row. Fetch the set.
3. **Shipping code nobody runs yet.** Load what the first screen needs; defer the rest.
4. **Unoptimised images.** Usually the largest thing on any page by a wide margin.
5. **Missing database indexes.** A query that scans a whole table is fine at a hundred rows and fatal at a
   hundred thousand.
6. **Blocking the main thread.** Long synchronous work makes the whole interface unresponsive, including
   the feedback you added.

**Perceived speed beats measured speed.** Loading the visible part first and the rest after will feel
faster than loading everything at once, even when the total is identical.

## Reviewing your own work

Before considering an interactive feature done:

- [ ] Every control that triggers work shows a pending state within 100ms
- [ ] Every control that can be pressed twice is protected against it
- [ ] All four states exist and were tested, not just written
- [ ] Nothing shifts position as content arrives
- [ ] Errors say what happened and what to do
- [ ] It was tried on a slow connection, not just a fast one
- [ ] Nothing is fetched in a loop
- [ ] Nothing waits for a request that could have run in parallel

## Anti-patterns

- A form that submits with no visible change until the page reloads
- A spinner covering the entire page for a single-row action
- A skeleton that doesn't match the shape of what arrives
- Optimistic updates that silently revert on failure
- "Loading..." as an empty state
- Disabling a button without explaining why it is disabled
- Optimising something that was never measured
