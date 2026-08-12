#!/usr/bin/env python3
"""Trellis handoff writer — PreCompact hook.

Fires just before context is compacted. Captures everything about the current state that can be
determined from disk, and instructs the agent to add the part only it knows: what it was actually
doing and why.

The split matters. A hook cannot see the conversation, so it must not pretend to summarise it —
it records the facts, and asks for the narrative. Anything else produces a confident handoff that
is quietly wrong.

The result is a file the user can paste into a fresh session and lose nothing.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from datetime import datetime, timezone

from frontmatter import parse_file

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HOOK_DIR, "..", ".."))
HANDOFF_DIR = os.path.join(REPO_ROOT, "docs", "handoff")


def git(*args, default=""):
    try:
        out = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True,
                             text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else default
    except Exception:
        return default


def project_name(config):
    """trellis.json, then the git remote, then the directory. The directory is the worst of the three:
    it is whatever the repo was cloned into, which is often not the project's name at all."""
    if config.get("name"):
        return config["name"]
    remote = git("config", "--get", "remote.origin.url")
    if remote:
        return os.path.basename(remote.rstrip("/")).removesuffix(".git")
    return os.path.basename(REPO_ROOT)


def load_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return {}




def in_flight_specs():
    specs_dir = os.path.join(REPO_ROOT, "docs", "specs")
    if not os.path.isdir(specs_dir):
        return []
    out = []
    for name in sorted(os.listdir(specs_dir)):
        if not name.endswith(".md") or name.startswith("_"):
            continue
        meta = parse_file(os.path.join(specs_dir, name))
        if meta.get("status") in ("building", "verifying", "blocked", "clarifying"):
            out.append((meta.get("id", name), meta.get("title", ""), meta.get("status", ""),
                        os.path.join("docs/specs", name)))
    return out


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}

    now = datetime.now(timezone.utc)
    config = load_json(os.path.join(REPO_ROOT, "trellis.json"))
    branch = git("rev-parse", "--abbrev-ref", "HEAD", default="unknown")
    status = git("status", "--porcelain")
    changed = [line[3:].strip() for line in status.splitlines()] if status else []
    commits = git("log", "--oneline", "-10", "--no-decorate")
    specs = in_flight_specs()

    doc = []
    doc.append("# Session handoff")
    doc.append("")
    manual = event.get("trigger") == "manual"
    doc.append("Written {} at {}.".format(
        "on request" if manual else "automatically, just before context was compacted",
        now.strftime("%Y-%m-%d %H:%M UTC")))
    doc.append("")
    doc.append("---")
    doc.append("")

    # ---- the part only the agent knows -------------------------------------
    doc.append("## What I was doing")
    doc.append("")
    doc.append("<!-- AGENT: replace this section before the session ends. Cover:")
    doc.append("     - the goal in one sentence")
    doc.append("     - what is finished and verified")
    doc.append("     - what is half-done, and precisely where you stopped")
    doc.append("     - anything you tried that did NOT work, so it is not retried")
    doc.append("     - any decision made in conversation that is not yet written to a file")
    doc.append("     Be concrete. 'Continuing the work' helps nobody. -->")
    doc.append("")
    doc.append("_Not yet filled in._")
    doc.append("")
    doc.append("## Next step")
    doc.append("")
    doc.append("<!-- AGENT: the single next action, specific enough to start without re-reading -->")
    doc.append("")
    doc.append("_Not yet filled in._")
    doc.append("")
    doc.append("---")
    doc.append("")

    # ---- the part the hook knows --------------------------------------------
    doc.append("## State at handoff")
    doc.append("")
    if config:
        doc.append("**Project:** {} ({})".format(config.get("name", "?"), config.get("type", "?")))
        stacks = config.get("stacks") or []
        doc.append("**Stacks:** %s" % (", ".join(stacks) if stacks else "none"))
        doc.append("")
    doc.append(f"**Branch:** `{branch}`")
    doc.append("")

    if specs:
        doc.append("**Specs in flight:**")
        doc.append("")
        doc.append("| Spec | Title | Status | File |")
        doc.append("|---|---|---|---|")
        for sid, title, sstatus, path in specs:
            doc.append(f"| {sid} | {title} | {sstatus} | `{path}` |")
        doc.append("")

    if changed:
        doc.append("**Uncommitted files (%d):**" % len(changed))
        doc.append("")
        for path in changed[:40]:
            doc.append(f"- `{path}`")
        if len(changed) > 40:
            doc.append("- _...and %d more_" % (len(changed) - 40))
        doc.append("")
    else:
        doc.append("**Working tree is clean.**")
        doc.append("")

    if commits:
        doc.append("**Recent commits:**")
        doc.append("")
        doc.append("```")
        doc.append(commits)
        doc.append("```")
        doc.append("")

    # ---- the copy-pastable prompt -------------------------------------------
    doc.append("---")
    doc.append("")
    doc.append("## Paste this into a new session")
    doc.append("")
    doc.append("```")
    doc.append(f"Continuing work on {project_name(config)}.")
    doc.append("")
    doc.append("Read docs/handoff/LATEST.md first — it has the full state of where I left off.")
    if specs:
        doc.append("Then read the in-flight specs it lists.")
    doc.append("")
    doc.append(f"Branch: {branch}")
    if specs:
        doc.append(f"Active spec: {specs[0][0]} — {specs[0][1]} ({specs[0][2]})")
    doc.append("")
    doc.append("Do not start anything new until you have confirmed with me what state the")
    doc.append("in-flight work is actually in.")
    doc.append("```")
    doc.append("")

    try:
        os.makedirs(HANDOFF_DIR, exist_ok=True)
        stamped = os.path.join(HANDOFF_DIR, "handoff-{}.md".format(now.strftime("%Y%m%d-%H%M%S")))
        with open(stamped, "w") as fh:
            fh.write("\n".join(doc))
        latest = os.path.join(HANDOFF_DIR, "LATEST.md")
        with open(latest, "w") as fh:
            fh.write("\n".join(doc))
    except Exception as exc:
        sys.stderr.write(f"Trellis: could not write handoff: {exc}\n")
        return 0

    # PreCompact stdout reaches the agent while it still has full context — the only
    # moment it can fill in the narrative.
    print(
        "Trellis wrote a handoff to docs/handoff/LATEST.md, but the two most important sections "
        "are empty because a hook cannot see this conversation.\n\n"
        "Before you do anything else, edit docs/handoff/LATEST.md and fill in 'What I was doing' "
        "and 'Next step'. Include what you tried that did not work, and any decision made in "
        "conversation that is not yet written to a file. Be specific — this is the only record "
        "that survives compaction."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
