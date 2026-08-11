---
description: Write a session handoff you can paste into a fresh session
---

Write a handoff capturing everything needed to continue this work elsewhere.

Run `.claude/hooks/write-handoff.py` to capture the state that can be read from disk, then edit
`docs/handoff/LATEST.md` and fill in the two sections it leaves blank — the ones only you can write:

**What I was doing** — the goal in one sentence; what is finished and verified; what is half-done and
precisely where you stopped; **what you tried that did not work**, so it is not retried; and any decision
made in conversation that is not yet written to a file.

**Next step** — the single next action, specific enough to begin without re-reading everything.

Be concrete. "Continuing the work" helps nobody. Assume the reader has none of your context and cannot
ask you anything.

Then show the user the copy-pastable prompt from the bottom of the file.
