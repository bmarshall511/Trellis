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
    r"^\s*(?:git\s+(?:commit|tag|merge|revert|stash|notes)|"
    r"gh\s+(?:pr|issue|release)\s+\w+)\b", re.I)

# `git add -A && git commit -m "..."` is one of the most common shapes there is. Anchoring prose
# detection to the start of the whole command missed it, so each segment is judged on its own.
#
# A newline separates commands as surely as `;` does, and leaving it out meant a multi-line block
# was judged as a single long segment — so text on one line could complete a pattern begun on
# another. Every separator list here has now been wrong once by omitting the newline.
SEGMENT = re.compile(r"(\s*(?:&&|\|\||;|\||\n)\s*)")

# A message containing a command substitution is not prose. The shell evaluates `$(...)` and backticks
# BEFORE git ever sees the argument, so stripping the quotes would hide a command that genuinely runs.
# The earlier comment claimed these commands "cannot execute their argument" — true of git, false of
# the shell that invokes it.
SUBSTITUTION = re.compile(r"\$\(|`|\$\{[^}]*[|;&]")

PROSE_ARGS = re.compile(
    r"(?:-m|--message|--title|--body|--subject|--notes)(?:=|\s+)"
    r"(\"[^\"]*\"|'[^']*'|\S+)", re.I)

HEREDOC = re.compile(r"<<-?\s*'?(\w+)'?.*?^\1$", re.M | re.S)

# A heredoc redirected INTO A FILE is data being written, not commands being run. `cat > x.sh <<EOF`
# writes text; nothing in that text executes. Piping one to an interpreter — `bash <<EOF` — does
# execute, and is left alone.
#
# The separator list here omitted the newline, which is how a heredoc is almost always written: on
# its own line, after earlier commands. So `cd x` followed by `cat > f <<EOF` was not recognised as
# writing a file, and the text being written was scanned as though it were commands — a commit
# message describing a blocked flag read as an attempt to use one.
HEREDOC_TO_FILE = re.compile(
    r"(?:^|[|;&\n]\s*)(?:cat|tee|printf|echo)?\s*>{1,2}\s*[\w./~$-]+\s*<<-?\s*'?\w+'?")

# The same, for a heredoc feeding a command that exists to record prose — `git commit -F - <<EOF`.
# Anchored to a separator so it is the command receiving the body, not a mention of one inside it.
HEREDOC_TO_PROSE = re.compile(
    r"(?:^|[|;&\n]\s*)(?:git\s+(?:commit|tag|merge|revert|stash|notes)|"
    r"gh\s+(?:pr|issue|release)\s+\w+)\b[^\n]*<<-?\s*'?\w+'?", re.I)


# `npm run db:deploy` tells the guard nothing. The dangerous command lives in package.json, which is
# a file, and this hook inspects commands. Every rule here was being asked to police a name chosen by
# the project rather than an act — the same defect as matching `revoke`, but hiding a whole command
# rather than a word. A real project runs almost everything through these aliases.
#
# So an alias is resolved to what it actually runs, and that text is judged too. Nested aliases are
# followed, because `db:deploy` is routinely `prisma migrate deploy && npm run db:seed`.
PKG_SCRIPT = re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+(?:run\s+|run-script\s+|exec\s+)?([\w:.@/-]+)")
MAX_ALIAS_DEPTH = 4


def load_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return {}


def expand_package_scripts(text):
    """Every command an npm-style alias in `text` would actually run, aliases followed.

    Returns bodies only, never the original. A body is judged exactly as a typed command would be,
    so a script that runs `psql -h prod` is caught whether it is typed or hidden behind `npm run`.
    """
    scripts = (load_json(os.path.join(REPO_ROOT, "package.json")).get("scripts") or {})
    if not isinstance(scripts, dict) or not scripts:
        return []

    found, seen, frontier = [], set(), [text]
    for _ in range(MAX_ALIAS_DEPTH):
        nxt = []
        for chunk in frontier:
            for name in PKG_SCRIPT.findall(chunk):
                body = scripts.get(name)
                # `seen` guards against `a: npm run b` / `b: npm run a`, which would otherwise spin.
                if isinstance(body, str) and name not in seen:
                    seen.add(name)
                    found.append(re.sub(r"\s+", " ", body).strip())
                    nxt.append(body)
        if not nxt:
            break
        frontier = nxt
    return found


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
    def strip_prose(segment):
        """Remove message text from a segment whose command exists to record prose."""
        if not PROSE_COMMANDS.match(segment):
            return segment
        segment = HEREDOC.sub(" ", segment)

        def replace(match):
            # Keep anything the shell would execute; only literal text is safe to discard.
            return " " if not SUBSTITUTION.search(match.group(1)) else match.group(0)

        return PROSE_ARGS.sub(replace, segment)

    # Heredoc bodies may contain &&, ; or newlines, so they must be handled before splitting on
    # separators — a body torn away from the command it feeds is judged as commands of its own.
    #
    # What makes a body data is the command receiving it: one that writes a file, or one that exists
    # to record prose. Both are matched wherever they appear, not only at the start, because
    # `git add -A && git commit -F - <<EOF` is the ordinary shape. An interpreter reading a heredoc
    # — `bash <<EOF`, `python3 - <<EOF` — is left alone, because that body really does execute.
    text = command.replace("\\\n", " ")
    if HEREDOC.search(text) and (HEREDOC_TO_FILE.search(text) or HEREDOC_TO_PROSE.search(text)):
        text = HEREDOC.sub(" ", text)
    text = "".join(part if SEGMENT.fullmatch(part) else strip_prose(part)
                   for part in SEGMENT.split(text))

    flat = re.sub(r"\s+", " ", text).strip()
    candidates = {flat, ENV_PREFIX.sub("", flat)}
    candidates.update(expand_package_scripts(flat))
    return candidates


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

        # `unless` is tested against the command as typed, never against the normalised candidates.
        # That distinction is the whole point. Some tools decide what they will destroy from an
        # environment variable — Prisma reads DATABASE_URL and has no --local flag — so the only way
        # to make the target visible is to state it in the command. But normalise() also produces a
        # variant with leading assignments stripped, which exists to catch `LEFTHOOK=0 git commit`,
        # and that variant deletes exactly the evidence being offered. No deny pattern can express
        # "safe when the environment says localhost" while that stripped variant is also being
        # matched, so the exception is evaluated separately, on the original text.
        exception = rule.get("unless")
        if exception:
            try:
                if re.search(exception, command, re.IGNORECASE):
                    continue
            except re.error:
                pass  # A broken exception fails closed: the rule still applies.

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
