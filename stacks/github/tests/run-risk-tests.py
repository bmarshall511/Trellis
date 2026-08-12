#!/usr/bin/env python3
"""Tests the risk classifier. Path rules run against explicit file lists; content rules use real
git diffs, since a destructive migration is only destructive by its added lines."""
import json, os, subprocess, sys, tempfile
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
def diff_case(name, sql, want):
    d = tempfile.mkdtemp()
    try:
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d, check=True)
        for cmd in (["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", *cmd], cwd=d, check=True)
        os.makedirs(os.path.join(d, "supabase", "migrations"))
        open(os.path.join(d, "README.md"), "w").write("x\n")
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=d, check=True)
        subprocess.run(["git", "checkout", "-qb", "work"], cwd=d, check=True)
        open(os.path.join(d, "supabase", "migrations", "0001_x.sql"), "w").write(sql)
        subprocess.run(["git", "add", "-A"], cwd=d, check=True)
        subprocess.run(["git", "commit", "-qm", "migration"], cwd=d, check=True)
        out = subprocess.run([CLASSIFY, "--json"], cwd=d, capture_output=True, text=True, check=False)
        got = json.loads(out.stdout)["decision"]
        if got != want:
            fails.append(f"{name}: got {got}, wanted {want}")
    finally:
        subprocess.run(["rm", "-rf", d], check=False)

diff_case("additive migration", "create table posts (id uuid primary key, title text);\n", "auto")
diff_case("drop table", "drop table posts;\n", "needs-human")
diff_case("drop column", "alter table posts drop column title;\n", "needs-human")
diff_case("truncate", "truncate posts;\n", "needs-human")
diff_case("delete without where", "delete from posts;\n", "needs-human")
diff_case("delete with where", "delete from posts where id = '1';\n", "auto")
diff_case("not null without default", "alter table posts add column x text not null;\n", "needs-human")
diff_case("not null with default", "alter table posts add column x text not null default '';\n", "auto")

total = len(cases["auto"]) + len(cases["needsHuman"]) + 8
if fails:
    print(f"FAILING ({len(fails)}/{total}):")
    for f in fails: print("  " + f)
    sys.exit(1)
print(f"risk: all {total} cases correct ({len(cases['auto'])} auto, "
      f"{len(cases['needsHuman'])} needs-human, 8 content-based)")
