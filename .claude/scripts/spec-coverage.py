#!/usr/bin/env python3
"""Trellis spec coverage mapper.

Produces the criterion-to-test mapping that `/spec-next` requires before a spec may be marked done.

This existed only as an instruction — "produce the mapping" — with nothing to produce it. An
instruction is not a control. Now the mapping is generated, and a spec with an uncovered criterion
fails mechanically.

Convention: a test covering acceptance criterion N of a spec references it in its name or body, as
`AC-N`, `ac<N>_`, or `SPEC-XXX AC-N`. That is the only coupling required, and it survives renaming
either side.

Run:
  spec-coverage.py <spec-id>    map one spec
  spec-coverage.py              map every spec that claims done or verifying
  spec-coverage.py --strict     exit non-zero if any criterion is uncovered
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from frontmatter import parse_and_body

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
SPECS_DIR = os.path.join(ROOT, "docs", "specs")

TEST_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".rb", ".go", ".rs", ".java", ".kt",
                   ".swift", ".php", ".cs", ".sql"}
TEST_HINTS = ("test", "spec", "_test", ".test.", ".spec.", "e2e")
SKIP_DIRS = {".git", "node_modules", "dist", "build", "out", ".next", "target", "vendor",
             "__pycache__", ".venv", "venv", "coverage", ".turbo", ".cache", ".claude", ".githooks",
             "stacks", "setup", "docs"}




def criteria(body):
    match = re.search(r"^## Acceptance criteria\s*$\n(.*?)(?=^## |\Z)", body, re.M | re.S)
    if not match:
        return []
    return [(int(m.group(1)), " ".join(m.group(2).split()))
            for m in re.finditer(r"^(\d+)\.\s+((?:.|\n(?!\s*\d+\.|\n))*)", match.group(1), re.M)]


def gate_scripts():
    """Commands in trellis.json's gates often point at scripts that assert criteria directly.
    A criterion checked by the a11y gate is verified -- it just is not in a test file."""
    try:
        with open(os.path.join(ROOT, "trellis.json")) as fh:
            gates = (json.load(fh).get("gates") or {})
    except Exception:
        return []
    found = []
    for command in gates.values():
        if not command:
            continue
        for token in re.findall(r"[\w./-]+\.(?:mjs|js|ts|py|sh)", command):
            path = os.path.join(ROOT, token)
            if os.path.exists(path):
                found.append(os.path.relpath(path, ROOT))
    # No transitive scanning. An earlier version followed file paths mentioned inside gate scripts
    # and picked up src/ files listed in a bundle-size array -- which meant a COMMENT in source code
    # could satisfy coverage. Source is the thing being verified, never the verification.
    return sorted(set(found))


def test_files():
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            if os.path.splitext(name)[1] not in TEST_EXTENSIONS:
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), ROOT)
            lowered = rel.lower()
            if any(hint in lowered for hint in TEST_HINTS):
                found.append(rel)
    return sorted(found)


def find_coverage(spec_id, number, files):
    """Return [(file, symbol)] for tests referencing this criterion."""
    # Underscore is a word character, so \b fails against `test_ac1_does_thing`. Bound on
    # letters/digits instead, and reject a following digit so AC-1 never matches ac12.
    patterns = [
        re.compile(r"(?<![a-z0-9])ac[_\- ]?%d(?!\d)" % number, re.I),
        re.compile(r"(?<![a-z0-9])%s[^\n]{0,20}ac[_\- ]?%d(?!\d)" % (re.escape(spec_id), number), re.I),
    ]
    hits = []
    for rel in files:
        try:
            with open(os.path.join(ROOT, rel), encoding="utf-8", errors="ignore") as fh:
                lines = fh.read().splitlines()
        except OSError:
            continue
        for index, line in enumerate(lines):
            if not any(p.search(line) for p in patterns):
                continue
            symbol = None
            definition = re.compile(r"(?:def|it|test|func|fn|Scenario)\s*[( ]?[\"']?([A-Za-z0-9_\- ]{3,})")
            # The matching line is usually the definition itself. If it is a `describe` header, the
            # test is BELOW it -- scanning backwards lands on the previous, unrelated test.
            for offset in [0, 1, 2, 3, 4, 5, -1, -2]:
                probe = index + offset
                if not 0 <= probe < len(lines):
                    continue
                m = definition.search(lines[probe])
                if m:
                    symbol = m.group(1).strip()
                    break
            hits.append((rel, symbol or f"line {index + 1}"))
            break  # one hit per file is enough to establish coverage
    return hits


def report(path, files, strict):
    text = open(path).read()
    fields, body = parse_and_body(text)
    spec_id = fields.get("id", os.path.basename(path))
    crits = criteria(body)

    print(f"\n{spec_id} — {fields.get('title', '')}  [{fields.get('status', '?')}]")
    if not crits:
        print("  no acceptance criteria found")
        return 1 if strict else 0

    uncovered = []
    for number, text_of in crits:
        hits = find_coverage(spec_id, number, files)
        short = text_of[:64] + ("…" if len(text_of) > 64 else "")
        if hits:
            print(f"  AC-{number:<3} ✓  {short}")
            for rel, symbol in hits[:3]:
                print(f"           {rel} :: {symbol}")
        else:
            uncovered.append(number)
            print(f"  AC-{number:<3} ✗  {short}")
            print("           NO TEST REFERENCES THIS CRITERION")

    covered = len(crits) - len(uncovered)
    print(f"\n  {covered}/{len(crits)} criteria covered")
    if uncovered:
        print(f"  Uncovered: {', '.join('AC-%d' % n for n in uncovered)}")
        print("  A spec is not done while any criterion has no test that would fail if it broke.")
        return 1
    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv

    if not os.path.isdir(SPECS_DIR):
        print("No docs/specs/ directory.")
        return 0

    all_specs = [os.path.join(SPECS_DIR, f) for f in sorted(os.listdir(SPECS_DIR))
                 if f.endswith(".md") and not f.startswith("_")]

    if args:
        paths = [p for p in all_specs if any(a in os.path.basename(p) for a in args)]
        if not paths:
            print(f"No spec matching {args}")
            return 1
    else:
        paths = []
        for path in all_specs:
            fields, _ = parse_and_body(open(path).read())
            if fields.get("status") in ("verifying", "done"):
                paths.append(path)
        if not paths:
            print("No specs are verifying or done.")
            return 0

    files = sorted(set(test_files()) | set(gate_scripts()))
    if not files:
        print("No test files found. Coverage cannot be established.")
        return 1

    failed = sum(report(path, files, strict) for path in paths)
    if failed:
        print(f"\n{failed} spec(s) have uncovered criteria.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
