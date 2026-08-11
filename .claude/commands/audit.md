---
description: Audit the project against the Trellis standards
argument-hint: [all | a11y | security | performance | specs | map]
---

Audit: **$ARGUMENTS** (default: all)

Report what is true. Change nothing — fixes are a separate, reviewable piece of work.

Run the relevant sections:

**specs** — every spec's real status. Use the `spec-auditor` agent on anything `ready` that has not been
built, and the `coverage-auditor` agent on anything claiming `done`. A spec marked done that is not is
the finding that matters most, because nobody looks at it again.

**a11y** — run the `a11y` gate, then the manual pass that automation cannot do: keyboard-only operation,
focus order and visibility, contrast in every variant including disabled, zoom to 400%, and whether
announced content matches what is on screen. Load the `accessibility` skill. Automated results are the
floor, not the verdict — say which findings came from the scanner and which from actually looking.

**security** — load the `security` skill and work its checklist. Concentrate on authorisation checked at
the point of data access, denial cases tested, input validated at the boundary, and secrets absent from
the diff and the test fixtures.

**performance** — load `feedback-and-performance`. Every interaction acknowledged within 100ms, all four
states present, nothing shifting as content loads, no fetching in a loop, nothing sequential that could
be parallel. Run the `perf` gate if declared.

**map** — `.claude/scripts/build-map.py --check`. If stale, regenerate and report what changed. Flag any
directory without a `PURPOSE`, and any whose contents no longer match what it claims to be.

## Reporting

Group by severity, not by category — someone reading this wants to know what to do first.

- **Broken** — not working, or a real vulnerability
- **Below standard** — works, but does not meet what Trellis requires
- **Drift** — documentation, map or specs no longer matching reality

For each: where it is, why it matters, and what fixing it involves. If a section is clean, say so in one
line rather than padding it.

Finish with the three things worth doing first.
