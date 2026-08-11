---
description: Regenerate the project map that agents read instead of the whole codebase
allowed-tools: Bash(.claude/scripts/build-map.py:*), Read, Glob, Grep, Edit, Write
---

Run `.claude/scripts/build-map.py`.

If it reports directories without a description, write a `PURPOSE` file for each — one line saying what
lives there and why. That single line is what makes the map worth reading; without it the map is only a
file listing.

Then report what changed since the last map, and flag anything that looks wrong — a directory whose
contents no longer match its stated purpose, or an area that has grown large enough to split.
