#!/usr/bin/env python3
"""Tests for the shared frontmatter parser."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from frontmatter import parse

CASES = [
    ("plain", "---\nstatus: ready\n---\nbody", {"status": "ready"}),
    ("trailing comment — the bug this file exists for",
     "---\nstatus: draft          # draft | clarifying | ready\n---\n", {"status": "draft"}),
    ("comment with colons",
     "---\nmockup: null   # path under docs/mockups/, once approved\n---\n", {"mockup": "null"}),
    ("numeric with comment",
     "---\nestimate: 0            # skilled-human minutes\n---\n", {"estimate": "0"}),
    ("list with comment",
     "---\nsurfaces: []           # ui | api | data | cli\n---\n", {"surfaces": "[]"}),
    ("hash inside a quoted value is content, not a comment",
     '---\ntitle: "Fix #42 in the parser"\n---\n', {"title": "Fix #42 in the parser"}),
    ("single quotes too", "---\ntitle: 'A # sign'\n---\n", {"title": "A # sign"}),
    ("a colour is not a comment", "---\naccent: #6f3c0c\n---\n", {"accent": "#6f3c0c"}),
    ("full-line comment ignored", "---\n# a note\nstatus: ready\n---\n", {"status": "ready"}),
    ("value containing a colon",
     "---\ntitle: Build: the thing\n---\n", {"title": "Build: the thing"}),
    ("no frontmatter", "just a body\n", {}),
    ("unterminated frontmatter", "---\nstatus: ready\n", {}),
    ("empty", "", {}),
    ("indented lines skipped", "---\nstatus: ready\n  nested: x\n---\n", {"status": "ready"}),
    ("whitespace tolerated", "---\n  \nstatus:   ready   \n---\n", {"status": "ready"}),
]

fails = []
for name, text, want in CASES:
    got = parse(text)
    if got != want:
        fails.append(f"{name}: got {got!r}, wanted {want!r}")

# The shipped template must parse to usable values — the whole point.
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
template = os.path.join(root, "docs", "specs", "_template.md")
if os.path.exists(template):
    fields = parse(open(template).read())
    for key, want in (("status", "draft"), ("type", "feature"), ("estimate", "0"),
                      ("mockup", "null"), ("surfaces", "[]")):
        if fields.get(key) != want:
            fails.append(f"shipped template: {key} = {fields.get(key)!r}, wanted {want!r}")

total = len(CASES) + 5
if fails:
    print(f"FAILING ({len(fails)}/{total}):")
    for f in fails:
        print("  " + f)
    sys.exit(1)
print(f"frontmatter: all {total} cases pass")
