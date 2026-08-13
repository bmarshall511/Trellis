#!/usr/bin/env python3
"""Tests the risk classifier. Path rules run against explicit file lists; content rules use real
git diffs, since a destructive migration is only destructive by its added lines."""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CLASSIFY = os.path.join(HERE, "..", "scripts", "classify-risk.py")
cases = json.load(open(os.path.join(HERE, "risk-cases.json")))
fails = []

def decide(files):
    out = subprocess.run([CLASSIFY, "--files", *files, "--json"],
                         capture_output=True, text=True, check=False)
    try:
        return json.loads(out.stdout)["decision"]
    except Exception:
        return f"error({out.returncode})"

for want, key in (("auto", "auto"), ("needs-human", "needsHuman")):
    for name, files in cases[key]:
        got = decide(files)
        if got != want:
            fails.append(f"{name}: got {got}, wanted {want}")

# --- content rules need a real diff -----------------------------------------
def diff_file(name, path, content, want, before=None):
    """Classify a real diff. `before` seeds the file on the base commit, so the diff is an edit
    rather than an addition — which is what a scripts-only change to package.json actually is."""
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d, check=True)
        for cmd in (["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", *cmd], cwd=d, check=True)
        full = os.path.join(d, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        open(os.path.join(d, "README.md"), "w").write("x\n")
        if before is not None:
            open(full, "w").write(before)
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=d, check=True)
        subprocess.run(["git", "checkout", "-qb", "work"], cwd=d, check=True)
        open(full, "w").write(content)
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        subprocess.run(["git", "commit", "-qm", "change"], cwd=d, check=True)
        out = subprocess.run([CLASSIFY, "--json"], cwd=d, capture_output=True, text=True, check=False)
        got = json.loads(out.stdout)["decision"]
        if got != want:
            fails.append(f"{name}: got {got}, wanted {want}")
    finally:
        subprocess.run(["rm", "-rf", d], check=False)


def diff_case(name, sql, want):
    diff_file(name, "supabase/migrations/0001_x.sql", sql, want)

diff_case("additive migration", "create table posts (id uuid primary key, title text);\n", "auto")
diff_case("drop table", "drop table posts;\n", "needs-human")
diff_case("drop column", "alter table posts drop column title;\n", "needs-human")
diff_case("truncate", "truncate posts;\n", "needs-human")
diff_case("delete without where", "delete from posts;\n", "needs-human")
diff_case("delete with where", "delete from posts where id = '1';\n", "auto")
diff_case("not null without default", "alter table posts add column x text not null;\n", "needs-human")
diff_case("not null with default", "alter table posts add column x text not null default '';\n", "auto")

# A table being created has no rows, so NOT NULL on it cannot fail and locks nothing. Matching the
# words anywhere held three consecutive specs for review over ordinary column definitions.
diff_case("create table with not null columns",
          "create table posts (id uuid primary key, title text not null);\n", "auto")
diff_case("create table then alter add not null",
          "create table posts (id uuid primary key);\n"
          "alter table posts add column title text not null;\n", "needs-human")

# A manifest holds scripts and metadata as well as dependencies. Editing a script was being held as
# though it added a package — the value is what separates them: a version range or a shell command.
PKG_BEFORE = '{\n  "name": "x",\n  "scripts": {\n    "test": "vitest"\n  }\n}\n'
diff_file("package.json scripts only", "package.json",
          '{\n  "name": "x",\n  "scripts": {\n    "test": "vitest",\n    "build": "next build"\n  }\n}\n',
          "auto", before=PKG_BEFORE)
diff_file("package.json adds a caret dependency", "package.json",
          '{\n  "name": "x",\n  "dependencies": {\n    "lodash": "^4.17.21"\n  }\n}\n',
          "needs-human", before=PKG_BEFORE)
diff_file("package.json adds an exact-version dependency", "package.json",
          '{\n  "name": "x",\n  "dependencies": {\n    "next": "15.0.0"\n  }\n}\n',
          "needs-human", before=PKG_BEFORE)
diff_file("package.json metadata only", "package.json",
          '{\n  "name": "x",\n  "license": "MIT",\n  "scripts": {\n    "test": "vitest"\n  }\n}\n',
          "auto", before=PKG_BEFORE)
# The lockfile rule is the one that does the real work: package managers write both files together,
# so anything actually installed is caught here even if the manifest shape is unfamiliar.
diff_file("lockfile touched at all", "package-lock.json",
          '{"lockfileVersion": 3, "packages": {}}\n', "needs-human")
diff_file("go.mod require line", "go.mod",
          "module x\n\nrequire github.com/pkg/errors v0.9.1\n", "needs-human")
diff_file("Gemfile gem line", "Gemfile", "source 'https://rubygems.org'\ngem 'rails', '~> 7.0'\n",
          "needs-human")
diff_file("pyproject dependency", "pyproject.toml",
          '[project]\nname = "x"\ndependencies = ["requests>=2.31"]\n', "needs-human")

CONTENT_CASES = 20  # keep in step with the diff_case/diff_file calls above
total = len(cases["auto"]) + len(cases["needsHuman"]) + CONTENT_CASES
if fails:
    print(f"FAILING ({len(fails)}/{total}):")
    for f in fails:
        print("  " + f)
    sys.exit(1)
print(f"risk: all {total} cases correct ({len(cases['auto'])} auto, "
      f"{len(cases['needsHuman'])} needs-human, {CONTENT_CASES} content-based)")
