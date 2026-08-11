---
description: Design a screen or the project's visual foundations, for your review and approval
argument-hint: <spec-id, or "foundations">
---

Produce a mockup for: **$ARGUMENTS**

Load the `mockups` skill and follow it. Load `accessibility` for the contrast rules.

**If the argument is `foundations`** (or no foundations exist yet at `docs/mockups/_foundations/`):
produce **three genuinely different directions** — differing in typography, density, and use of colour,
not three colourways of one idea. Present them together. Then help the user *merge* the parts they like
rather than picking one whole. Check every colour pair against the project's contrast target while
choosing, not after.

**Otherwise**: read the spec first. Build **one** direction under `docs/mockups/<SPEC-ID>/`, using the
approved foundation tokens — never arbitrary values. Include every state the spec lists (loading, empty,
error, success) and both mobile and desktop widths. Use realistic content, never lorem ipsum.

Then show the user what you built, say specifically what you want feedback on, and iterate.

When — and only when — the user says they approve:

```
.claude/scripts/mockup.py approve <SPEC-ID>
```

Never run that yourself on your own judgement. Record the mockup path in the spec's frontmatter.
