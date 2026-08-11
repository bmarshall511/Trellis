#!/usr/bin/env python3
"""Regression tests for the Trellis production guard.

Run: .claude/hooks/tests/run.py

Stack guard patterns only load when a project declares that stack, so the suite activates every stack
that ships a guard.json for the duration of the run, then restores whatever trellis.json was there
before. Without this, stack cases silently pass by never being loaded -- which is the failure mode this
whole file exists to prevent.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GUARD = os.path.join(HERE, "..", "guard-production.py")
CASES = os.path.join(HERE, "guard-cases.json")
CONFIG = os.path.join(REPO_ROOT, "trellis.json")

NULL_GATES = {"types": None, "lint": None, "test": None, "a11y": None, "perf": None}


def stacks_with_guards():
    stacks_dir = os.path.join(REPO_ROOT, "stacks")
    if not os.path.isdir(stacks_dir):
        return []
    return sorted(
        name for name in os.listdir(stacks_dir)
        if not name.startswith("_")
        and os.path.exists(os.path.join(stacks_dir, name, "guard.json"))
    )


def run_case(command):
    result = subprocess.run(
        [GUARD],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True, text=True,
    )
    return result.returncode


def main():
    cases = json.load(open(CASES))
    stacks = stacks_with_guards()

    # Activate every stack that ships guard patterns, preserving any existing config.
    backup = None
    if os.path.exists(CONFIG):
        backup = tempfile.NamedTemporaryFile(delete=False, suffix=".json").name
        shutil.copy2(CONFIG, backup)
    try:
        with open(CONFIG, "w") as fh:
            json.dump({"name": "guard-tests", "type": "service",
                       "stacks": stacks, "gates": NULL_GATES}, fh)

        failures = []
        for expected, key in ((2, "block"), (0, "allow")):
            for name, command in cases[key]:
                actual = run_case(command)
                if actual != expected:
                    failures.append("%s: %s (exit %d, wanted %d)" % (key, name, actual, expected))
    finally:
        if backup:
            shutil.move(backup, CONFIG)
        elif os.path.exists(CONFIG):
            os.remove(CONFIG)

    total = len(cases["block"]) + len(cases["allow"])
    if failures:
        print("FAILING (%d/%d):" % (len(failures), total))
        for failure in failures:
            print("  " + failure)
        return 1

    print("guard: all %d cases pass (%d blocked, %d allowed)"
          % (total, len(cases["block"]), len(cases["allow"])))
    print("       stacks active during run: %s" % (", ".join(stacks) or "none"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
