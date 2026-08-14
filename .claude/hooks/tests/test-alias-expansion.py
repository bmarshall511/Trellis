#!/usr/bin/env python3
"""Tests that an npm-style alias is judged by what it actually runs.

`npm run db:deploy` tells the guard nothing. The command lives in package.json, which is a file, and
this hook inspects commands — so every rule was being asked to police a name the project chose rather
than an act. A real project runs almost everything through these aliases, which made it the widest
hole in the guard: not a rule matching the wrong thing, but a whole command never seen at all.

This needs its own file because it needs a package.json to resolve against, and Trellis has none —
there is no application here. The main suite runs against this repo, so the case cannot live there.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FAILS = []


def check(condition, label):
    print(("  PASS  " if condition else "  FAIL  ") + label)
    if not condition:
        FAILS.append(label)


def build_project(scripts, stacks=()):
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, ".claude", "hooks", "guards"))
    shutil.copy(os.path.join(REPO, ".claude/hooks/guard-production.py"),
                os.path.join(root, ".claude/hooks/guard-production.py"))
    shutil.copy(os.path.join(REPO, ".claude/hooks/guards/base.json"),
                os.path.join(root, ".claude/hooks/guards/base.json"))
    os.makedirs(os.path.join(root, "stacks"), exist_ok=True)
    for stack in stacks:
        shutil.copytree(os.path.join(REPO, "stacks", stack), os.path.join(root, "stacks", stack))
    with open(os.path.join(root, "trellis.json"), "w") as fh:
        json.dump({"name": "t", "type": "app", "stacks": list(stacks)}, fh)
    with open(os.path.join(root, "package.json"), "w") as fh:
        json.dump({"name": "t", "scripts": scripts}, fh)
    return root


def judge(root, command):
    """Run the real hook, exactly as Claude Code would. Returns the blocking rule id, or None."""
    proc = subprocess.run(
        [sys.executable, os.path.join(root, ".claude/hooks/guard-production.py")],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True, text=True, cwd=root,
        env={**os.environ, "CLAUDE_PROJECT_DIR": root})
    if proc.returncode != 2:
        return None
    match = re.search(r"guard(?:\s*\[[^\]]*\])?: (\S+)", proc.stderr)
    return match.group(1) if match else "blocked"


SCRIPTS = {
    "dev": "next dev",
    "build": "next build",
    "db:seed": "tsx prisma/seed.ts",
    "db:deploy": "prisma migrate deploy && npm run db:seed",
    "db:nuke": "psql -h db.example.com -c \"TRUNCATE users;\"",
    "release": "bash scripts/deploy-prod.sh",
    "loop-a": "npm run loop-b",
    "loop-b": "npm run loop-a",
}

root = build_project(SCRIPTS, stacks=("prisma",))

# The alias hides a remote database client. Before this, the guard saw four harmless words.
check(judge(root, "npm run db:nuke") is not None,
      "an alias hiding a remote psql is caught")
check(judge(root, "pnpm db:nuke") is not None, "pnpm, whose run keyword is optional, is caught")
check(judge(root, "yarn db:nuke") is not None, "yarn is caught")
check(judge(root, "bun run db:nuke") is not None, "bun is caught")

# Nested: db:deploy runs a prisma command AND another alias.
check(judge(root, "npm run db:deploy") == "prisma-migrate-deploy",
      "a nested alias is followed to the prisma command inside it")

check(judge(root, "npm run release") == "production-script",
      "an alias hiding a production deploy script is caught")

# The exception has to survive alias expansion too: the target is stated, so it is allowed.
check(judge(root, "DATABASE_URL=postgresql://u@localhost:5432/dev npm run db:deploy") is None,
      "stating a localhost target still exempts the command behind an alias")

# Ordinary aliases must stay ordinary, or every project blocks on `npm run build`.
for alias in ("npm run dev", "npm run build", "npm run db:seed", "npm test"):
    check(judge(root, alias) is None, "ordinary alias runs freely: %s" % alias)

# A cycle must terminate. Two aliases pointing at each other is a typo, not an attack, and the guard
# hanging is worse than either.
check(judge(root, "npm run loop-a") is None, "mutually recursive aliases terminate rather than hang")

# A project with no package.json must behave exactly as before.
bare = build_project({})
os.unlink(os.path.join(bare, "package.json"))
check(judge(bare, "npm run anything") is None, "no package.json is not an error")
check(judge(bare, "psql -h db.example.com -c 'select 1'") is not None,
      "and the ordinary rules still apply there")

shutil.rmtree(root, ignore_errors=True)
shutil.rmtree(bare, ignore_errors=True)

print()
if FAILS:
    print("%d case(s) wrong" % len(FAILS))
    sys.exit(1)
print("alias expansion: all 14 cases correct")
