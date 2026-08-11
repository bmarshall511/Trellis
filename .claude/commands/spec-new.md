---
description: Write a new spec — interviews you until nothing is ambiguous
argument-hint: [what you want to build]
---

Write a new Trellis spec for: **$ARGUMENTS**

Load the `spec-authoring` skill and follow it.

1. Read `trellis.json` for the project type, active stacks and `standards.specMaxMinutes`.
2. Find the highest existing spec id in `docs/specs/` and use the next one.
3. Copy `docs/specs/_template.md` to `docs/specs/SPEC-<id>-<kebab-title>.md`.
4. **Interview the user.** Work through every category in the skill's interview section. Ask in batches.
   Do not move on while anything is unresolved — this is the one phase where interrogation is the job.
5. Fill the spec in as answers arrive. Keep `Open questions` populated with anything outstanding so the
   state is always visible.
6. When `Open questions` is empty, run the readiness checklist from the skill **explicitly**, line by
   line, and show the user the result.
7. Set status to `ready` only if every line passes; otherwise leave it `clarifying` and say what's missing.
8. If `surfaces` includes `ui`, tell the user a mockup is required before this can be built, and offer
   to run `/mockup <id>`.

Do not estimate optimistically. If the estimate exceeds `standards.specMaxMinutes`, split the spec
vertically and set `depends` — say so rather than shrinking the estimate to fit.
