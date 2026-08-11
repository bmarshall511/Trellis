#!/usr/bin/env python3
"""Trellis integrity check.

Verifies that the pieces of Trellis actually connect: that every hook a setting names exists and runs,
that every skill a command loads is real, that every guard pattern has a test, that every stack module
is complete.

Each piece can be correct on its own and the whole still be broken — a command that loads a skill which
was renamed is silently a no-op, and nothing about it looks wrong.

Run: .claude/scripts/check-integrity.py
"""
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
CLAUDE = os.path.join(ROOT, ".claude")

problems = []
notes = []


def fail(message):
    problems.append(message)


def note(message):
    notes.append(message)


def read(path):
    try:
        with open(path) as fh:
            return fh.read()
    except Exception:
        return ""


def load_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception as exc:
        fail(f"{os.path.relpath(path, ROOT)} is not valid JSON: {exc}")
        return None


def frontmatter(text):
    if not text.startswith("---"):
        return {}
    fields = {}
    for line in text.split("---", 2)[1].splitlines():
        if ":" in line and not line.startswith((" ", "\t", "#")):
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip().strip("'\"")
    return fields


def listdir(path):
    return sorted(os.listdir(path)) if os.path.isdir(path) else []


# ---------------------------------------------------------------- json validity
for dirpath, _dirnames, filenames in os.walk(ROOT):
    if ".git" in dirpath or "node_modules" in dirpath:
        continue
    for name in filenames:
        if name.endswith(".json"):
            load_json(os.path.join(dirpath, name))

# ---------------------------------------------------------------- skills
skills = {}
skills_dir = os.path.join(CLAUDE, "skills")
for name in listdir(skills_dir):
    path = os.path.join(skills_dir, name, "SKILL.md")
    if not os.path.exists(path):
        fail(f"skills/{name} has no SKILL.md")
        continue
    meta = frontmatter(read(path))
    declared = meta.get("name", "")
    if declared != name:
        fail(f"skills/{name} declares name '{declared}' — must match the directory")
    if not meta.get("description"):
        fail(f"skills/{name} has no description, so it will never trigger")
    elif len(meta["description"]) < 40:
        note(f"skills/{name} has a very short description; it may trigger unreliably")
    skills[name] = meta

if not skills:
    fail("no skills found")

# ---------------------------------------------------------------- agents
agents = {}
agents_dir = os.path.join(CLAUDE, "agents")
for name in listdir(agents_dir):
    if not name.endswith(".md"):
        continue
    meta = frontmatter(read(os.path.join(agents_dir, name)))
    stem = name[:-3]
    if meta.get("name") != stem:
        fail("agents/{} declares name '{}' — must match the filename".format(name, meta.get("name")))
    if not meta.get("description"):
        fail(f"agents/{name} has no description")
    agents[stem] = meta

# ---------------------------------------------------------------- commands
commands_dir = os.path.join(CLAUDE, "commands")
command_files = [n for n in listdir(commands_dir) if n.endswith(".md")]
if not command_files:
    fail("no commands found")

for name in command_files:
    text = read(os.path.join(commands_dir, name))
    if not frontmatter(text).get("description"):
        fail(f"commands/{name} has no description")

    # A command that names a skill which does not exist is silently a no-op.
    for referenced in re.findall(r"`([a-z][a-z0-9-]+)`\s+(?:and\s+`[a-z0-9-]+`\s+)?skills?\b", text):
        if referenced not in skills:
            fail(f"commands/{name} loads skill '{referenced}', which does not exist")
    for referenced in re.findall(r"[Ll]oad the `([a-z][a-z0-9-]+)`", text):
        if referenced not in skills:
            fail(f"commands/{name} loads skill '{referenced}', which does not exist")
    for referenced in re.findall(r"`([a-z][a-z0-9-]+)`\s+agent\b", text):
        if referenced not in agents:
            fail(f"commands/{name} uses agent '{referenced}', which does not exist")
    for referenced in re.findall(r"`?(\.claude/scripts/[a-z-]+\.py)`?", text):
        if not os.path.exists(os.path.join(ROOT, referenced)):
            fail(f"commands/{name} runs '{referenced}', which does not exist")

# ---------------------------------------------------------------- settings & hooks
settings = load_json(os.path.join(CLAUDE, "settings.json")) or {}
for event, groups in (settings.get("hooks") or {}).items():
    for group in groups:
        for hook in group.get("hooks", []):
            command = hook.get("command", "")
            rel = command.replace("$CLAUDE_PROJECT_DIR/", "")
            path = os.path.join(ROOT, rel)
            if not os.path.exists(path):
                fail(f"settings.json {event} hook points at '{rel}', which does not exist")
            elif not os.access(path, os.X_OK):
                fail(f"{rel} is not executable — the {event} hook will fail silently")

# ---------------------------------------------------------------- guards have tests
cases_path = os.path.join(CLAUDE, "hooks/tests/guard-cases.json")
cases = load_json(cases_path) or {"block": [], "allow": []}
# Test each command separately. Joining them into one string breaks any pattern using a negative
# lookahead -- `UPDATE ... SET` without `WHERE` would match some later command's `WHERE` and report a
# missing test that exists.
case_commands = [c for _, c in cases.get("block", []) + cases.get("allow", [])]

guard_files = [os.path.join(CLAUDE, "hooks/guards/base.json")]
stacks_dir = os.path.join(ROOT, "stacks")
for name in listdir(stacks_dir):
    if name.startswith("_") or not os.path.isdir(os.path.join(stacks_dir, name)):
        continue
    guard = os.path.join(stacks_dir, name, "guard.json")
    if os.path.exists(guard):
        guard_files.append(guard)

for guard_path in guard_files:
    data = load_json(guard_path) or {}
    for rule in data.get("deny", []):
        pattern = rule.get("pattern")
        rule_id = rule.get("id", "?")
        if not pattern:
            fail(f"{os.path.relpath(guard_path, ROOT)} rule '{rule_id}' has no pattern")
            continue
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            fail(f"{os.path.relpath(guard_path, ROOT)} rule '{rule_id}' has an invalid regex: {exc}")
            continue
        if not any(regex.search(command) for command in case_commands):
            fail(f"guard rule '{rule_id}' ({os.path.relpath(guard_path, ROOT)}) has no test case "
                 "— an untested guard is not a guard")

# ---------------------------------------------------------------- stack modules
for name in listdir(stacks_dir):
    directory = os.path.join(stacks_dir, name)
    if not os.path.isdir(directory) or name.startswith("_"):
        continue
    if not os.path.exists(os.path.join(directory, "SKILL.md")):
        fail(f"stacks/{name} has no SKILL.md")
    verified = os.path.join(directory, "VERIFIED")
    if not os.path.exists(verified):
        fail(f"stacks/{name} has no VERIFIED file — its currency is unknown")
    elif not re.search(r"\d{4}-\d{2}-\d{2}", read(verified)):
        fail(f"stacks/{name} VERIFIED has no date")
    extractor = os.path.join(directory, "extract-map.py")
    if os.path.exists(extractor) and not os.access(extractor, os.X_OK):
        note(f"stacks/{name}/extract-map.py is not executable")

# ---------------------------------------------------------------- docs scaffolding
for required in ("docs/specs/_template.md", "trellis.schema.json", "README.md", "stacks/README.md"):
    if not os.path.exists(os.path.join(ROOT, required)):
        fail(f"{required} is missing")

for area in ("docs", "stacks", "setup", ".claude"):
    path = os.path.join(ROOT, area)
    if os.path.isdir(path) and not os.path.exists(os.path.join(path, "PURPOSE")):
        note(f"{area} has no PURPOSE file, so the map cannot describe it")

# ---------------------------------------------------------------- guard suite runs
try:
    result = subprocess.run([os.path.join(CLAUDE, "hooks/tests/run.py")],
                            capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        fail("guard test suite is failing:\n    " + result.stdout.strip().replace("\n", "\n    "))
except Exception as exc:
    fail(f"could not run the guard test suite: {exc}")

# ---------------------------------------------------------------- report
print("Trellis integrity check")
print("  %d skills, %d agents, %d commands, %d stack modules"
      % (len(skills), len(agents), len(command_files),
         len([n for n in listdir(stacks_dir)
              if os.path.isdir(os.path.join(stacks_dir, n)) and not n.startswith("_")])))

if notes:
    print("\nNotes (%d):" % len(notes))
    for message in notes:
        print("  - " + message)

if problems:
    print("\nPROBLEMS (%d):" % len(problems))
    for message in problems:
        print("  - " + message)
    sys.exit(1)

print("\nAll references resolve. No problems.")
