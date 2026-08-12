"""Minimal YAML frontmatter reader, shared by every Trellis script that needs one.

This exists because there were six copies of it, each with the same bug: none stripped trailing
comments, so a spec copied from the shipped template read its status as

    'draft          # draft | clarifying | ready | building | verifying | done | blocked'

and failed lint. Every spec made from the template failed until someone deleted the comments that were
there to help them.

One authoritative copy, because the answer to "when this changes, must every copy change together?"
was yes.

Deliberately not a YAML library: this must run on a freshly downloaded repo before any package manager
has been chosen. It handles `key: value` and nothing more, which is all Trellis's frontmatter uses.
"""
import re

__all__ = ["parse", "parse_and_body", "parse_file", "split"]

# A YAML comment needs whitespace before the '#', or must start the line. `#fdfbf7` is a colour.
_COMMENT = re.compile(r"\s+#.*$")


def _strip_comment(value):
    """Remove a trailing comment, unless the value is quoted — a '#' inside quotes is content."""
    value = value.strip()
    if value[:1] in ("'", '"'):
        quote = value[0]
        end = value.find(quote, 1)
        if end != -1:
            return value[1:end]
        return value[1:]
    return _COMMENT.sub("", value).strip()


def split(text):
    """Return (frontmatter_text, body). Both empty-safe; body is the whole text when there is none."""
    if not text.startswith("---"):
        return "", text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return "", text
    return parts[1], parts[2]


def parse(text):
    """Parse frontmatter from a full document. Returns a dict of strings."""
    front, _ = split(text)
    fields = {}
    for line in front.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith((" ", "\t")):
            continue  # nested value; Trellis's frontmatter is flat
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = _strip_comment(value)
    return fields


def parse_and_body(text):
    """Return (fields, body) — the common case for anything that reads a spec."""
    return parse(text), split(text)[1]


def parse_file(path):
    """Parse frontmatter from a file. Returns {} rather than raising — callers are hooks and gates
    that must not crash on a malformed file."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            return parse(handle.read())
    except OSError:
        return {}
