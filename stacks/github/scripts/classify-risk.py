#!/usr/bin/env python3
"""Decides whether a change may merge without a human.

Reads risk-policy.json and classifies a diff. The question is never "is this change correct" — the
gates answer that. It is "if this change is wrong, how bad is it, and can it be undone".

Fails closed in every direction that matters: an unreadable policy, an unreadable diff, or an error
during classification all produce `needs-human`. The cost of a false positive is one morning
decision; the cost of a false negative is an unreviewed change to production.

Usage:
  classify-risk.py [base]           classify the diff from base (default: the merge base with main)
  classify-risk.py --files a b c    classify an explicit list of paths
  classify-risk.py --json           machine-readable output

Exit: 0 may auto-merge · 1 needs a human · 2 could not classify (treated as needs-human)
"""
import fnmatch
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
POLICY_FILE = os.path.join(SCRIPT_DIR, "..", "risk-policy.json")


def repo_root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=10, check=False)
        return out.stdout.strip() or os.getcwd()
    except Exception:
        return os.getcwd()


ROOT = repo_root()


def load_policy():
    with open(POLICY_FILE) as fh:
        policy = json.load(fh)
    if not isinstance(policy.get("rules"), list):
        raise ValueError("policy has no rules array")
    return policy


def git(*args):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                         timeout=60, check=False)
    return out.stdout if out.returncode == 0 else ""


def default_base():
    for candidate in ("main", "master"):
        base = git("merge-base", "HEAD", candidate).strip()
        if base:
            return base
    return "HEAD~1"


def changed_files(base):
    listing = git("diff", "--name-only", f"{base}...HEAD")
    return [p for p in listing.splitlines() if p.strip()]


def added_lines(base, path):
    """Only ADDED lines. A destructive statement being deleted is not a destructive change."""
    diff = git("diff", "-U0", f"{base}...HEAD", "--", path)
    return "\n".join(line[1:] for line in diff.splitlines()
                     if line.startswith("+") and not line.startswith("+++"))


def matches(path, patterns):
    """fnmatch, with ** treated as spanning directories."""
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
        # fnmatch does not special-case **; approximate by also trying the pattern anchored anywhere.
        if "**/" in pattern and fnmatch.fnmatch(path, pattern.replace("**/", "", 1)):
            return True
        if pattern.startswith("**") and fnmatch.fnmatch(os.path.basename(path), pattern.lstrip("*/")):
            return True
    return False


def classify(files, policy, content_for):
    """Return (decision, findings). First matching rule wins, so order in the policy is meaningful."""
    findings = []
    for path in sorted(files):
        for rule in policy["rules"]:
            if not matches(path, rule.get("paths", [])):
                continue
            patterns = rule.get("contentPatterns")
            if patterns:
                content = content_for(path)
                hit = next((p for p in patterns if re.search(p, content)), None)
                if not hit:
                    continue  # this rule needs content evidence and found none; try the next rule
                findings.append((path, rule["id"], rule["decision"], rule["reason"], hit))
            else:
                findings.append((path, rule["id"], rule["decision"], rule["reason"], None))
            break
        else:
            findings.append((path, "default", policy.get("defaultDecision", "auto"),
                             "No rule matched.", None))
    decision = "needs-human" if any(f[2] == "needs-human" for f in findings) else "auto"
    return decision, findings


def main():
    as_json = "--json" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    try:
        policy = load_policy()
    except Exception as exc:
        # Fail closed: no policy means no automatic merging.
        message = f"could not read risk policy: {exc}"
        print(json.dumps({"decision": "needs-human", "error": message}) if as_json
              else f"needs-human — {message}", file=sys.stderr)
        return 2

    try:
        if "--files" in sys.argv:
            files = args
            content_for = lambda path: ""  # noqa: E731 — no diff available for an explicit list
            base = None
        else:
            base = args[0] if args else default_base()
            files = changed_files(base)
            content_for = lambda path: added_lines(base, path)  # noqa: E731

        if not files:
            print(json.dumps({"decision": "auto", "files": []}) if as_json
                  else "auto — no files changed")
            return 0

        decision, findings = classify(files, policy, content_for)
    except Exception as exc:
        message = f"classification failed: {exc}"
        print(json.dumps({"decision": "needs-human", "error": message}) if as_json
              else f"needs-human — {message}", file=sys.stderr)
        return 2

    if as_json:
        print(json.dumps({
            "decision": decision,
            "base": base,
            "files": [{"path": p, "rule": r, "decision": d, "reason": why,
                       "matched": hit} for p, r, d, why, hit in findings],
        }, indent=2))
    else:
        print(f"{decision} — {len(files)} file(s) changed\n")
        blocking = [f for f in findings if f[2] == "needs-human"]
        for path, rule, _, why, hit in blocking:
            print(f"  needs-human  {path}")
            print(f"               [{rule}] {why}")
            if hit:
                print(f"               matched: {hit}")
        if not blocking:
            print("  every changed file is auto-mergeable under the current policy")

    return 0 if decision == "auto" else 1


if __name__ == "__main__":
    sys.exit(main())
