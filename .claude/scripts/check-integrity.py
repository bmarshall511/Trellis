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

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from frontmatter import parse

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
    meta = parse(read(path))
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
    meta = parse(read(os.path.join(agents_dir, name)))
    stem = name[:-3]
    if meta.get("name") != stem:
        fail("agents/{} declares name '{}' — must match the filename".format(name, meta.get("name")))
    if not meta.get("description"):
        fail(f"agents/{name} has no description")
    agents[stem] = meta

# Words that appear in backticks on a skill/agent line but are VALUES, not names — spec statuses,
# gate names, project types. Drawn from real registries rather than guessed: the statuses are asserted
# below to match spec-lint.py, and the gates and types come from trellis.schema.json.
SPEC_STATUSES = ("draft", "clarifying", "ready", "building", "verifying", "done", "blocked")


def vocabulary():
    words = set(SPEC_STATUSES)
    schema = load_json(os.path.join(ROOT, "trellis.schema.json")) or {}
    props = (schema.get("properties") or {})
    words.update((props.get("type") or {}).get("enum") or [])
    words.update(((props.get("gates") or {}).get("properties") or {}).keys())
    return words


# ---------------------------------------------------------------- commands
VOCABULARY = vocabulary()
commands_dir = os.path.join(CLAUDE, "commands")
command_files = [n for n in listdir(commands_dir) if n.endswith(".md")]
if not command_files:
    fail("no commands found")

for name in command_files:
    text = read(os.path.join(commands_dir, name))
    if not parse(text).get("description"):
        fail(f"commands/{name} has no description")

    # A command that names a skill which does not exist is silently a no-op.
    #
    # Do NOT try to parse the sentence. An earlier version matched "load the `x` and `y` skills" with
    # an optional group for the second name -- which CONSUMED it without capturing it, so the checker
    # verified one of two and reported success. That shipped a dangling reference.
    #
    # Instead: on any line that mentions a skill or an agent, check EVERY backticked kebab-case token
    # on that line. Grammar varies; the tokens do not.
    for raw_line in text.splitlines():
        mentions_skill = re.search(r"\bskills?\b", raw_line, re.I)
        mentions_agent = re.search(r"\bagents?\b", raw_line, re.I)
        if not (mentions_skill or mentions_agent):
            continue
        for token in re.findall(r"`([a-z][a-z0-9-]{2,})`", raw_line):
            if token in VOCABULARY:
                continue
            if mentions_skill and token in skills:
                continue
            if mentions_agent and token in agents:
                continue
            if token in skills or token in agents:
                continue
            kind = "skill" if mentions_skill else "agent"
            known = sorted(skills if mentions_skill else agents)
            fail("commands/%s references %s '%s', which does not exist. Known: %s"
                 % (name, kind, token, ", ".join(known)))

    for referenced in re.findall(r"`?(\.claude/scripts/[a-z-]+\.py)`?", text):
        if not os.path.exists(os.path.join(ROOT, referenced)):
            fail("commands/%s runs '%s', which does not exist" % (name, referenced))

# The exclusion list must not drift from the lifecycle it claims to mirror.
_lint_source = read(os.path.join(CLAUDE, "scripts", "spec-lint.py"))
_declared = re.search(r"^STATUSES = \(([^)]*)\)", _lint_source, re.M)
if _declared:
    _lint_statuses = tuple(re.findall(r'"([a-z-]+)"', _declared.group(1)))
    if _lint_statuses != SPEC_STATUSES:
        fail("check-integrity's SPEC_STATUSES has drifted from spec-lint.py's STATUSES: %s vs %s"
             % (list(SPEC_STATUSES), list(_lint_statuses)))

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

# ---------------------------------------------------------------- shell portability
# macOS ships bash 3.2 and always will — bash went GPLv3 in 2007 and Apple has not shipped a newer
# one since. Every script here must run on it. `mapfile` broke trellis-update.sh on the very machine
# Trellis was written on.
BASH4_ONLY = {
    "mapfile": "bash 4+; use a `while IFS= read -r` loop",
    "readarray": "bash 4+; use a `while IFS= read -r` loop",
    "declare -A": "bash 4+ associative arrays; use parallel arrays or python",
    "${!": "bash 4+ indirect expansion in some forms; verify on bash 3.2",
}
for _dirpath, _dirnames, _filenames in os.walk(ROOT):
    if any(part in _dirpath for part in (".git", "node_modules")):
        continue
    for _name in _filenames:
        _full = os.path.join(_dirpath, _name)
        _rel = os.path.relpath(_full, ROOT)
        if not (_name.endswith(".sh") or _rel.startswith(".githooks/")):
            continue
        _text = read(_full)
        if not _text.startswith("#!"):
            continue
        # Comments explaining why a feature is avoided must not be mistaken for using it.
        _code = "\n".join(line for line in _text.splitlines()
                           if not line.lstrip().startswith("#"))
        for _feature, _why in BASH4_ONLY.items():
            if _feature in _code:
                fail("%s uses `%s` — %s" % (_rel, _feature, _why))

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

# ---------------------------------------------------------------- ownership manifest
# Every framework file must be covered, or trellis-update.sh silently fails to ship it. That is not
# hypothetical: a hand-written list omitted .claude/lib/frontmatter.py and left downstream projects
# with an integrity check that died on import.
_owned = [p.rstrip("/") for p in _paths.get("owned", [])] if (_paths := load_json(
    os.path.join(CLAUDE, "framework-paths.json")) or {}) else []
if _owned:
    _tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                              text=True, check=False).stdout.split()
    _prefixes = (".claude/", ".githooks/", "stacks/", "setup/")
    _singles = ("trellis.schema.json", ".gitattributes")
    for _file in _tracked:
        if not (_file.startswith(_prefixes) or _file in _singles):
            continue
        if not any(_file == o or _file.startswith(o + "/") for o in _owned):
            fail("%s is a framework file but no entry in framework-paths.json covers it — "
                 "trellis-update.sh would not ship it" % _file)

# ---------------------------------------------------------------- generated files
# The list and .gitattributes must agree, or a generated file gains a conflict nobody expects.
_generated = _paths.get("generated", [])
_attributes = read(os.path.join(ROOT, ".gitattributes"))
for _path in _generated:
    if _path not in _attributes:
        fail("%s is listed as generated but has no .gitattributes entry — it will conflict on every "
             "concurrent branch" % _path)
for _line in _attributes.splitlines():
    if "merge=trellis-generated" in _line:
        _declared = _line.split()[0]
        if _declared not in _generated:
            fail("%s has a .gitattributes merge entry but is not listed in framework-paths.json"
                 % _declared)

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
