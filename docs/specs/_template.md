---
id: SPEC-000
title: Short imperative title
status: draft          # draft | clarifying | ready | building | verifying | done | blocked
type: feature          # feature | fix | refactor | chore | design
surfaces: []           # ui | api | data | cli — drives which gates and whether a mockup is required
depends: []            # spec ids that must be done first
estimate: 0            # skilled-human minutes. Must not exceed standards.specMaxMinutes
created: YYYY-MM-DD
mockup: null           # path under docs/mockups/, once approved. Required when surfaces includes ui
---

## Why

One paragraph. What problem this solves and for whom. If this cannot be written without
hedging, the spec is not ready to be written yet.

## Acceptance criteria

Numbered, testable, and written in EARS form. Each one becomes at least one automated test.
A criterion that cannot be observed from outside the system is not a criterion — it is an
implementation note, and belongs in Notes.

| Form | Template |
|---|---|
| Always true | The system shall `<response>` |
| Triggered | When `<trigger>`, the system shall `<response>` |
| Conditional on state | While `<state>`, the system shall `<response>` |
| Error or edge case | If `<trigger>`, then the system shall `<response>` |
| Only when a feature is present | Where `<feature>`, the system shall `<response>` |

1. When ..., the system shall ...
2. If ..., then the system shall ...
3. While ..., the system shall ...

## States

Required when `surfaces` includes `ui`. Every one of these must be specified, or the
implementation will invent them.

- **Loading** —
- **Empty** —
- **Error** —
- **Success** —
- **Offline** — *(only if the project supports offline)*

## Out of scope

What this spec deliberately does not do. Prevents scope drift during an unattended run and
stops the reviewer flagging absences as defects.

-

## Notes

Implementation guidance, constraints, prior art, links. Not binding — the acceptance criteria
are the contract.

## Open questions

**This section must be empty before status can become `ready`.**

Every question here is something the implementation would otherwise have to guess. Resolve them
during authoring, then delete them. Do not answer them inline and leave them here — move the
answer into Why, Acceptance criteria, or Notes so it is binding.

-
