#!/usr/bin/env python3
"""Trellis spec linter.

Mechanically enforces the readiness checklist from the `spec-authoring` skill.

This exists because the checklist used to be prose. A checklist an agent may or may not run is not a
control — and "never assumes" is the most important claim Trellis makes, so it cannot rest on one.

A spec is only allowed to reach `ready` when every check here passes.

Run:
  spec-lint.py                  lint every spec
  spec-lint.py <path|id>        lint one
  spec-lint.py --ready-only     lint only specs claiming ready/building/verifying/done
"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SPECS_DIR = os.path.join(ROOT, "docs", "specs")

STATUSES = ("draft", "clarifying", "ready", "building", "verifying", "done", "blocked")
COMMITTED = ("ready", "building", "verifying", "done")

# EARS forms. A criterion outside these is ambiguous about when it applies.
EARS = re.compile(r"^(When|If|While|Where|The system shall)\b")

# Words that hide a decision. Matched as word-boundary stems so inflections are caught -- an earlier
# version listed "reasonable" and let "reasonably fast" straight through.
#
# Deliberately excludes common verbs that are usually legitimate in a precise criterion: "process",
# "support", "manage", and bare quantity words. Those produced false positives on criteria as exact as
# "continue processing" and "ignore files smaller than that many bytes". A linter that cries wolf gets
# switched off, and then it protects nothing.
VAGUE = [
    r"appropriat\w*", r"reasonab\w*", r"properly", r"suitab\w*", r"adequat\w*", r"sensib\w*",
    r"as needed", r"as necessary", r"etc\b", r"and so on", r"and more",
    r"handles?\b", r"handling", r"deal with",
    r"\bfast\b", r"\bslow\b", r"\bquick\w*", r"efficient\w*", r"performant", r"robust",
    r"scalab\w*", r"user-friendly", r"intuitive",
    r"should probably", r"ideally", r"if possible", r"where possible", r"try to",
    r"\btbd\b", r"\btbc\b", r"\btodo\b",
]
VAGUE_RE = [re.compile(pattern, re.I) for pattern in VAGUE]


def frontmatter_and_body(text):
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fields = {}
    for line in parts[1].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip("'\"")
    return fields, parts[2]


def section(body, name):
    match = re.search(r"^## %s\s*$\n(.*?)(?=^## |\Z)" % re.escape(name), body, re.M | re.S)
    return match.group(1).strip() if match else None


def criteria(body):
    text = section(body, "Acceptance criteria") or ""
    # Numbered items, each continuing until the next number or a blank line followed by a heading.
    return [" ".join(m.group(1).split())
            for m in re.finditer(r"^\d+\.\s+((?:.|\n(?!\s*\d+\.|\n))*)", text, re.M)]


def has_bullets(text):
    return bool(text and re.search(r"^\s*[-*]\s+\S", text, re.M))


def load_max_minutes():
    try:
        with open(os.path.join(ROOT, "trellis.json")) as fh:
            return (json.load(fh).get("standards") or {}).get("specMaxMinutes", 90)
    except Exception:
        return 90


def lint(path, max_minutes):
    text = open(path).read()
    fields, body = frontmatter_and_body(text)
    problems, notes = [], []

    status = fields.get("status", "")
    if status not in STATUSES:
        problems.append(f"status {status!r} is not one of: {', '.join(STATUSES)}")

    if not fields.get("id"):
        problems.append("no id in frontmatter")
    if not fields.get("title"):
        problems.append("no title in frontmatter")

    # Everything below only gates specs claiming to be implementable.
    gating = status in COMMITTED

    # --- open questions -----------------------------------------------------
    open_questions = section(body, "Open questions")
    if open_questions is None:
        problems.append("no '## Open questions' section")
    elif has_bullets(open_questions):
        count = len(re.findall(r"^\s*[-*]\s+\S", open_questions, re.M))
        (problems if gating else notes).append(
            f"{count} unresolved open question(s) — a spec cannot be ready while any remain")

    # --- acceptance criteria ------------------------------------------------
    crits = criteria(body)
    if not crits:
        problems.append("no numbered acceptance criteria")
    for index, crit in enumerate(crits, 1):
        if not EARS.match(crit):
            problems.append(
                f"AC-{index} is not in EARS form — start with When / If / While / Where / "
                f"'The system shall': {crit[:60]}…")
        for regex in VAGUE_RE:
            match = regex.search(crit)
            if not match:
                continue
            problems.append(f"AC-{index} contains vague wording '{match.group(0)}' — it hides a "
                            f"decision: {crit[:58]}…")
            break

    # --- scope --------------------------------------------------------------
    out_of_scope = section(body, "Out of scope")
    if out_of_scope is None:
        problems.append("no '## Out of scope' section")
    elif not has_bullets(out_of_scope):
        (problems if gating else notes).append(
            "'Out of scope' is empty — if nothing is out of scope, the boundary was never considered")

    if not section(body, "Why"):
        problems.append("no '## Why' section")

    # --- sizing -------------------------------------------------------------
    estimate = fields.get("estimate", "")
    if not estimate.isdigit() or int(estimate) <= 0:
        problems.append("estimate must be a positive number of minutes")
    elif int(estimate) > max_minutes:
        problems.append(f"estimate {estimate} exceeds specMaxMinutes ({max_minutes}) — split it")

    # --- user interface specifics -------------------------------------------
    surfaces = fields.get("surfaces", "")
    if "ui" in surfaces:
        states = section(body, "States")
        if not states:
            problems.append("surfaces includes 'ui' but there is no '## States' section")
        else:
            for required in ("Loading", "Empty", "Error", "Success"):
                match = re.search(r"\*\*%s\*\*\s*—\s*(.*)" % required, states)
                if not match:
                    problems.append(f"'{required}' state is not listed")
                elif not match.group(1).strip():
                    problems.append(f"'{required}' state is listed but not described")
        if gating and fields.get("mockup", "null") in ("null", "", "~"):
            problems.append("surfaces includes 'ui' but no approved mockup is recorded")

    # --- dependencies -------------------------------------------------------
    depends = fields.get("depends", "[]").strip("[]").strip()
    if depends and gating:
        for dep in [d.strip().strip("'\"") for d in depends.split(",") if d.strip()]:
            found = [f for f in os.listdir(SPECS_DIR) if f.startswith(dep)] \
                if os.path.isdir(SPECS_DIR) else []
            if not found:
                problems.append(f"depends on {dep}, which does not exist")
            else:
                dep_fields, _ = frontmatter_and_body(open(os.path.join(SPECS_DIR, found[0])).read())
                if dep_fields.get("status") != "done":
                    problems.append(f"depends on {dep}, which is '{dep_fields.get('status')}' not 'done'")

    return problems, notes, status, len(crits)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ready_only = "--ready-only" in sys.argv

    if not os.path.isdir(SPECS_DIR):
        print("No docs/specs/ directory.")
        return 0

    if args:
        paths = []
        for arg in args:
            if os.path.exists(arg):
                paths.append(arg)
            else:
                paths += [os.path.join(SPECS_DIR, f) for f in sorted(os.listdir(SPECS_DIR))
                          if f.startswith(arg) and f.endswith(".md")]
    else:
        paths = [os.path.join(SPECS_DIR, f) for f in sorted(os.listdir(SPECS_DIR))
                 if f.endswith(".md") and not f.startswith("_")]

    if not paths:
        print("No specs found.")
        return 0

    max_minutes = load_max_minutes()
    failed = 0
    for path in paths:
        problems, notes, status, count = lint(path, max_minutes)
        if ready_only and status not in COMMITTED:
            continue
        name = os.path.relpath(path, ROOT)
        if problems:
            failed += 1
            print(f"\n{name}  [{status}]  {count} criteria")
            for problem in problems:
                print(f"  ✗ {problem}")
            for note in notes:
                print(f"  · {note}")
        else:
            suffix = "" if not notes else f"  ({len(notes)} note)"
            print(f"{name}  [{status}]  {count} criteria  ✓{suffix}")
            for note in notes:
                print(f"  · {note}")

    if failed:
        print(f"\n{failed} spec(s) failed. A spec cannot be marked ready until it passes.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
