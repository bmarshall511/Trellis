---
name: testing
description: Use when writing tests, deciding what to test, reviewing test coverage, or verifying that a spec's acceptance criteria are actually covered. Also when a test is failing and the fix is unclear.
---

# Testing

## The contract

**Every acceptance criterion in a spec maps to at least one test that would fail if that criterion broke.**

That is the whole rule. Not a coverage percentage — coverage measures which lines ran, not which
behaviour is guaranteed. A suite at 95% coverage that asserts nothing meaningful is worse than one at 60%
that pins every promise the spec makes, because the first one lies to you.

Before marking any spec done, write the mapping out explicitly:

```
AC-1  When submitted with a valid email, the system shall create the account
      → auth/register.test.ts "creates an account for a valid email"

AC-2  If the email is already registered, then the system shall show
      "That email is already in use" and not create a second account
      → auth/register.test.ts "rejects a duplicate email"
      → e2e/register.spec.ts "shows the duplicate message inline"
```

If you cannot produce that list, the spec is not done — regardless of how green the suite looks.

## Choosing the level

The level is chosen per criterion, not per spec. Pick the **cheapest level that would actually catch the
failure**.

| Level | Use for | Avoid for |
|---|---|---|
| **Unit** | Logic with branches — validation, calculation, parsing, state transitions | Anything whose value is in the wiring between parts |
| **Component** | A piece of UI in each of its states, including keyboard and screen-reader behaviour | Multi-step flows that cross pages |
| **Integration** | A real boundary — the database, an API contract, permissions | Things a unit test proves more cheaply |
| **End-to-end** | Journeys a user actually performs, start to finish | Every permutation. E2E is for the path, not the matrix |

The common failure is testing everything end-to-end. It feels thorough and produces a slow, flaky suite
that people start skipping — at which point you have no tests at all. Test the *journey* end-to-end and
the *permutations* underneath it.

The opposite failure is unit-testing everything with the boundaries mocked, which proves each piece works
alone and nothing works together.

## What must always be tested

- **The happy path** for every acceptance criterion
- **Every error case the spec names** — if the spec says what happens when it fails, that behaviour is a promise
- **Boundaries** — zero, one, many, and past whatever limit exists
- **Permissions** — that someone who should not see it, cannot. Test the denial, not just the grant
- **The states**, for anything with a UI — loading, empty, error, success. All four, every time

## What not to test

- Framework behaviour. The framework has its own tests
- Private implementation detail. Test what the spec promises, so a refactor doesn't break the suite
- Generated code, unless the generator is yours
- Mock behaviour. A test that only asserts a mock was called proves the mock exists

## Writing tests an agent can maintain

**Name tests after the behaviour, not the function.** `"rejects a duplicate email"` survives a rename;
`"test register 2"` tells a future reader nothing.

**Reference the criterion.** Tag or name tests so the spec-to-test mapping can be recovered mechanically
rather than by reading everything.

**One reason to fail per test.** A test asserting six things fails ambiguously and gets deleted rather
than fixed.

**Set up through the public interface where you can.** Tests that construct state by reaching into
internals break on every refactor and stop being maintained.

**Make failure messages say what was expected.** You will read them at 3am with no context.

## Flakiness

A flaky test is worse than no test, because it teaches everyone to ignore a red build.

When a test fails intermittently, **find the cause** — it is almost always a real race in the code, a
fixed wait instead of a wait-for-condition, shared state between tests, or dependence on ordering. All
four are bugs, in the test or the thing being tested.

Never fix flakiness by adding a retry or a longer sleep. If you genuinely cannot resolve it now, quarantine
the test explicitly, record why, and treat it as a defect — not as done.

## Test data

Every test creates what it needs and cleans up after itself. Tests that depend on a shared fixture built
by an earlier test fail in isolation and fail when parallelised.

Use factories with sensible defaults so a test states only the fields it cares about. A test cluttered
with irrelevant setup hides what it is actually asserting.

**A test suite must never be able to run against production.** Assert the target environment in setup
and abort if it is wrong. This is not paranoia — the destination is one environment variable away, and
the failure is unrecoverable.

## When a test fails

1. **Read the failure.** The message usually says what is wrong.
2. **Reproduce it in isolation** before changing anything.
3. **Decide which is wrong — the test or the code.** Say which, explicitly.
4. **Fix the cause.** Never adjust an assertion to match broken output. Never delete a failing test to get
   a green build. Never mark a spec done with a test skipped.

If a test is genuinely wrong, fixing it is legitimate — but say so out loud and explain why, because
"the test was wrong" is also what it looks like when someone is quietly weakening the suite.
