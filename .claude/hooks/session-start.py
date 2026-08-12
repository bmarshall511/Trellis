#!/usr/bin/env python3
"""Trellis session start.

Loads the project's identity into context once, cheaply, so the agent does not rediscover it by
reading the codebase. Also runs tripwires — conditions that mean the session should not proceed
normally, checked at the only moment anyone reliably reads a warning.

Everything printed to stdout becomes session context. Keep it short: this text is paid for on every
single request for the life of the session, and it sits in the cached prefix, so churn here is
expensive twice over.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from frontmatter import parse_file

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HOOK_DIR, "..", ".."))

# Never grow without a reason — see the docstring.
MAX_SPECS_LISTED = 8


def load_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def git(*args):
    try:
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                             text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""




def tripwires(config):
    """Conditions that should stop a session being treated as normal."""
    found = []

    # Git will not activate a repo's own hooks on clone -- that would be remote code execution. So
    # this is one command per clone, and it is the difference between the gates running and not.
    if (os.path.isdir(os.path.join(REPO_ROOT, ".githooks"))
            and git("config", "core.hooksPath") != ".githooks"):
            found.append(
                "Git hooks are NOT active. Secret scanning and the gates will not run on commit. "
                "Fix with: git config core.hooksPath .githooks"
            )

    # The merge driver for generated files needs registering per clone, same as hooksPath. Without it,
    # every concurrent branch conflicts on the map — which is about to be normal once runs create their
    # own branches.
    if os.path.exists(os.path.join(REPO_ROOT, ".gitattributes")) and not git(
            "config", "--get", "merge.trellis-generated.driver"):
        found.append(
            "The merge driver for generated files is not registered, so concurrent branches will "
            "conflict on docs/map/OVERVIEW.md. Fix with: git config merge.trellis-generated.driver "
            "'.claude/scripts/merge-generated.sh %A %O %B %P'"
        )

    # Secrets that would be readable by anything running here.
    for name in (".env", ".env.local", ".env.production"):
        if os.path.exists(os.path.join(REPO_ROOT, name)):
            found.append(
                f"{name} exists in the repo. Confirm it is gitignored and holds no production "
                "credentials — an agent's shell inherits this environment."
            )

    # Production write credentials must not be reachable from this machine at all.
    for var in ("DATABASE_URL", "PROD_DATABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
        value = os.environ.get(var, "")
        if value and not any(h in value for h in ("localhost", "127.0.0.1", "::1")):
            found.append(
                f"{var} is set in this environment and does not point at localhost. Production write "
                "credentials must not exist on the development machine."
            )

    # Untracked files that look like keys.
    for line in git("status", "--porcelain", "--untracked-files=all").splitlines():
        path = line[3:].strip()
        if path.endswith((".pem", ".key", ".p12", ".keystore")):
            found.append(f"Untracked credential file: {path}")

    if config and (config.get("production") or {}).get("readAccess"):
        found.append(
            "This project grants the agent read-only production access. That credential must be "
            "incapable of writing — enforced by database grants, not by instruction."
        )

    return found


def main():
    config = load_json(os.path.join(REPO_ROOT, "trellis.json"))
    lines = []

    if config is None:
        lines.append("## Trellis")
        lines.append("")
        lines.append("No `trellis.json` yet — this project has not been set up.")
        lines.append("")
        lines.append(
            "Before building anything: ask what is being built, recommend a stack for those "
            "requirements, and write `trellis.json` (see `trellis.schema.json`). Do not assume a "
            "stack. Do not scaffold an application before the user has agreed to one."
        )
    else:
        gates = config.get("gates") or {}
        active = [n for n in ("types", "lint", "test", "a11y", "perf") if gates.get(n)]
        absent = [n for n in ("types", "lint", "test", "a11y", "perf") if n in gates and not gates.get(n)]

        lines.append("## {}".format(config.get("name", "Trellis project")))
        if config.get("description"):
            lines.append("")
            lines.append(config["description"])
        lines.append("")
        lines.append("- Type: **{}**{}".format(
            config.get("type", "?"),
            "" if config.get("type") == "app" else "  (no mockups, no a11y/perf gates)",
        ))
        stacks = config.get("stacks") or []
        lines.append("- Stacks: %s" % (", ".join(f"`{s}`" for s in stacks) if stacks else "none"))
        lines.append("- Gates active: %s" % (", ".join(active) if active else "none"))
        if absent:
            lines.append("- Gates declared absent: {}".format(", ".join(absent)))

        for stack in stacks:
            path = os.path.join(REPO_ROOT, "stacks", stack, "SKILL.md")
            if not os.path.exists(path):
                lines.append(f"- ⚠ `stacks/{stack}/` is declared but missing.")

    # Specs needing a human, and what is ready to build.
    specs_dir = os.path.join(REPO_ROOT, "docs", "specs")
    if os.path.isdir(specs_dir):
        needs, ready = [], []
        for name in sorted(os.listdir(specs_dir)):
            if not name.endswith(".md") or name.startswith("_"):
                continue
            meta = parse_file(os.path.join(specs_dir, name))
            status, title = meta.get("status", ""), meta.get("title", name)
            entry = "{} — {}".format(meta.get("id", name), title)
            if status in ("blocked", "clarifying"):
                needs.append(f"{entry} ({status})")
            elif status == "ready":
                ready.append(entry)
        if needs:
            lines.append("")
            lines.append("**Specs needing you:** {}".format("; ".join(needs[:MAX_SPECS_LISTED])))
        if ready:
            lines.append("")
            lines.append("**Ready to build:** {}".format("; ".join(ready[:MAX_SPECS_LISTED])))

    # Uncommitted work from a previous session is worth knowing about immediately -- but on a fresh
    # clone everything is untracked and there is no branch yet, which is noise at exactly the moment
    # the reader needs clarity.
    has_commits = bool(git("rev-parse", "--verify", "HEAD"))
    dirty = git("status", "--porcelain")
    if not has_commits:
        lines.append("")
        lines.append("Fresh repository — no commits yet.")
    elif dirty:
        branch = git("rev-parse", "--abbrev-ref", "HEAD") or "detached"
        lines.append("")
        lines.append("**Uncommitted changes** (%d files) on `%s`." % (len(dirty.splitlines()), branch))

    warnings = tripwires(config)
    if warnings:
        lines.append("")
        lines.append("### ⚠ Check before proceeding")
        for warning in warnings:
            lines.append(f"- {warning}")

    handoff = os.path.join(REPO_ROOT, "docs", "handoff", "LATEST.md")
    if os.path.exists(handoff):
        lines.append("")
        lines.append("A handoff from a previous session exists at `docs/handoff/LATEST.md`. "
                     "Read it before starting work.")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
