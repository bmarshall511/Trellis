#!/usr/bin/env python3
"""Trellis production guard — PreToolUse hook.

Blocks commands that could damage production or bypass quality gates.

This is the THIRD line of defence, and the weakest. A denylist can always be worked around by a
sufficiently creative command. It exists to catch mistakes, not to stop a determined attacker.

  1st line — production write credentials do not exist on this machine.
  2nd line — the production role has no write grants, enforced by the database itself.
  3rd line — this file.

Exit 0 allows the command. Exit 2 blocks it and returns the reason to the agent.
"""
import json
import os
import re
import sys

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HOOK_DIR, "..", ".."))

STACK_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")
ENV_PREFIX = re.compile(r"^(?:[A-Za-z_][A-Za-z0-9_]*=(?:\"[^\"]*\"|'[^']*'|\S*)\s+)+")

# Some commands exist to RECORD TEXT. Their message argument is prose a human wrote, not an instruction
# to a machine — so a commit message describing a dangerous command is not a dangerous command.
#
# Narrow on purpose. `psql -c "DROP TABLE users"` is also a quoted string, and there the quoted text IS
# the instruction. The distinction is the verb, not the quoting: these commands cannot execute their
# argument, so nothing inside it can be executed.
PROSE_COMMANDS = re.compile(
    r"^(?:git\s+(?:commit|tag|merge|revert|stash|notes)|"
    r"gh\s+(?:pr|issue|release)\s+\w+)\b", re.I)

PROSE_ARGS = re.compile(
    r"(?:-m|--message|--title|--body|--subject|--notes)(?:=|\s+)"
    r"(\"[^\"]*\"|'[^']*'|\S+)", re.I)

HEREDOC = re.compile(r"<<-?\s*'?(\w+)'?.*?^\1$", re.M | re.S)


def load_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return {}


def collect_rules():
    """Base patterns, plus patterns from the stack modules this project actually uses."""
    rules = list(load_json(os.path.join(REPO_ROOT, ".claude/hooks/guards/base.json")).get("deny", []))

    config = load_json(os.path.join(REPO_ROOT, "trellis.json"))
    for stack in config.get("stacks", []) or []:
        # Never let a config value become a path traversal.
        if not isinstance(stack, str) or not STACK_NAME.match(stack):
            continue
        extra = load_json(os.path.join(REPO_ROOT, "stacks", stack, "guard.json"))
        for rule in extra.get("deny", []) or []:
            rules.append({**rule, "stack": stack})
    return rules


def normalise(command):
    """Defeat the cheapest evasions before matching.

    Collapse line continuations and whitespace, then also test a copy with leading environment
    assignments removed -- `LEFTHOOK=0 git commit` is otherwise invisible to a command-name match.
    """
    # Remove prose before flattening, because a heredoc body is only identifiable while newlines exist.
    text = command
    if PROSE_COMMANDS.match(text.lstrip()):
        text = HEREDOC.sub(" ", text)
        text = PROSE_ARGS.sub(" ", text)

    flat = re.sub(r"\s+", " ", text.replace("\\\n", " ")).strip()
    return {flat, ENV_PREFIX.sub("", flat)}


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0  # Malformed input is not ours to adjudicate.

    if event.get("tool_name") != "Bash":
        return 0  # Only Bash carries arbitrary execution.

    command = (event.get("tool_input") or {}).get("command") or ""
    if not command.strip():
        return 0

    candidates = normalise(command)

    for rule in collect_rules():
        pattern = rule.get("pattern")
        if not pattern:
            continue
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            continue  # A broken pattern must not break the guard.
        if any(regex.search(text) for text in candidates):
            origin = " [{}]".format(rule["stack"]) if rule.get("stack") else ""
            sys.stderr.write(
                "BLOCKED by Trellis production guard{}: {}\n\n"
                "{}\n\n"
                "Command: {}\n\n"
                "If this is legitimate work, it needs a human to run it. Do not rephrase the command\n"
                "to get past this check. Say what you were trying to do and why, then stop.\n".format(
                    origin,
                    rule.get("id", "rule"),
                    rule.get("reason", "This command is not permitted."),
                    max(candidates, key=len)[:400],
                )
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
