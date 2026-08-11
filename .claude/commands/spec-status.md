---
description: Show every spec, its status, and what is ready to build next
allowed-tools: Bash(ls:*), Bash(grep:*), Bash(head:*), Bash(cat:*), Read, Glob, Grep
---

Report the state of every spec in `docs/specs/`.

Read the frontmatter of each spec file (ignore `_template.md`). Compute status from what is actually on
disk — never trust a stale frontmatter value alone:

- A spec claiming `done` whose acceptance criteria have no corresponding tests is **not** done. Flag it.
- A spec claiming `ready` that fails the readiness checklist is **not** ready. Flag it.
- A spec whose `depends` include anything unfinished is **blocked on dependencies**, whatever it claims.

Present as a table, ordered by id:

| Spec | Title | Status | Est | Blocked by | Notes |

Then, beneath it:

**Ready to build now** — specs that are `ready`, have all dependencies `done`, and (if `surfaces`
includes `ui`) have an approved mockup. This is what `/spec-next` would pick up, in order.

**Needs you** — specs in `clarifying` or `blocked`. For each blocked spec, quote the single question
from its `## Blocked` section verbatim. This is the list the user should act on.

**In flight** — anything `building` or `verifying`.

Finish with one line: total specs, how many done, and the estimated minutes remaining across everything
not yet done.

If `docs/specs/` contains no specs, say so and suggest `/spec-new`.
