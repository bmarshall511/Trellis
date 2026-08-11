#!/usr/bin/env python3
"""Validates trellis.json against trellis.schema.json.

Written by hand rather than with a schema library, because this must run on a freshly downloaded repo
before any package manager has been chosen. It checks what actually matters for Trellis rather than
implementing JSON Schema in full.

Run: .claude/scripts/validate-config.py [path]
"""
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

TYPES = ("app", "service", "cli", "library")
GATES = ("types", "lint", "test", "a11y", "perf")
UI_REQUIRED_GATES = ("a11y", "perf")
STACK_NAME = re.compile(r"[a-z0-9][a-z0-9-]*\Z")

errors = []
warnings = []


def error(message):
    errors.append(message)


def warn(message):
    warnings.append(message)


def validate(config):
    # ---- required top level ------------------------------------------------
    for key in ("name", "type", "gates"):
        if key not in config:
            error(f"missing required field: {key}")

    if "name" in config and not str(config["name"]).strip():
        error("name is empty")
    if str(config.get("name", "")).strip().upper() == "CHANGE ME":
        error("name is still the placeholder from setup/trellis.json")

    project_type = config.get("type")
    if project_type is not None and project_type not in TYPES:
        error("type must be one of {}, got {!r}".format(", ".join(TYPES), project_type))

    # ---- stacks ------------------------------------------------------------
    stacks = config.get("stacks", [])
    if not isinstance(stacks, list):
        error("stacks must be a list")
        stacks = []
    for stack in stacks:
        if not isinstance(stack, str) or not STACK_NAME.match(stack):
            error(f"invalid stack name {stack!r} — lowercase letters, digits and hyphens only")
            continue
        directory = os.path.join(ROOT, "stacks", stack)
        if not os.path.isdir(directory):
            error(f"stack {stack!r} is declared but stacks/{stack}/ does not exist")
            continue
        if not os.path.exists(os.path.join(directory, "SKILL.md")):
            error(f"stacks/{stack} has no SKILL.md")
        verified = os.path.join(directory, "VERIFIED")
        if not os.path.exists(verified):
            warn(f"stacks/{stack} has no VERIFIED file — its currency is unknown")
        else:
            with open(verified) as fh:
                text = fh.read()
            match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
            if not match:
                warn(f"stacks/{stack} VERIFIED has no date")

    # ---- gates -------------------------------------------------------------
    gates = config.get("gates")
    if gates is None:
        pass
    elif not isinstance(gates, dict):
        error("gates must be an object")
    else:
        for name in GATES:
            if name not in gates:
                error(f"gates.{name} is missing. Declare it as null if it does not apply — "
                      "absence must be a decision, not an oversight.")
            else:
                value = gates[name]
                if value is not None and (not isinstance(value, str) or not value.strip()):
                    error(f"gates.{name} must be a non-empty command string or null")
        for name in gates:
            if name not in GATES:
                error(f"unknown gate {name!r}")

        # A user interface cannot opt out of accessibility or performance.
        if project_type == "app":
            for name in UI_REQUIRED_GATES:
                if not gates.get(name):
                    error(f"type is 'app', so gates.{name} must be a real command — "
                          "a project with a user interface cannot declare it absent.")

        if not any(gates.get(n) for n in GATES):
            warn("no gates are active, so nothing is verified before work is called done")

    # ---- standards ---------------------------------------------------------
    standards = config.get("standards") or {}
    if not isinstance(standards, dict):
        error("standards must be an object")
    else:
        level = standards.get("accessibility")
        if level is not None and level not in ("AA", "AA+", "AAA"):
            error("standards.accessibility must be AA, AA+ or AAA")
        if level == "AA+" and not os.path.isdir(os.path.join(ROOT, "docs", "decisions")):
            warn("accessibility is 'AA+' but docs/decisions/ does not exist — "
                 "the AAA criteria being adopted must be written down somewhere")
        minutes = standards.get("specMaxMinutes")
        if minutes is not None:
            if not isinstance(minutes, int) or not 15 <= minutes <= 480:
                error("standards.specMaxMinutes must be an integer between 15 and 480")
            elif minutes > 120:
                warn("specMaxMinutes is %d. Unattended reliability falls off well before this; "
                     "specs this large are likely to block or half-finish." % minutes)

    # ---- production --------------------------------------------------------
    production = config.get("production") or {}
    if not isinstance(production, dict):
        error("production must be an object")
    else:
        if production.get("readAccess") and not production.get("credentialCommand"):
            error("production.readAccess is true but no credentialCommand is set. The credential must "
                  "come from a command, never a file or environment variable — an agent's shell "
                  "inherits the environment.")
        if production.get("readAccess"):
            warn("the agent can read production. That credential must be incapable of writing, "
                 "enforced by database grants rather than by instruction.")

    # ---- autonomy ----------------------------------------------------------
    autonomy = config.get("autonomy") or {}
    if not isinstance(autonomy, dict):
        error("autonomy must be an object")
    else:
        attempts = autonomy.get("maxRepairAttempts")
        if attempts is not None and (not isinstance(attempts, int) or not 0 <= attempts <= 5):
            error("autonomy.maxRepairAttempts must be an integer between 0 and 5")
        blocked = autonomy.get("onBlocked")
        if blocked is not None and blocked not in ("halt", "skip"):
            error("autonomy.onBlocked must be 'halt' or 'skip'")
        if autonomy.get("enabled") and not any((config.get("gates") or {}).get(n) for n in GATES):
            error("autonomy is enabled but no gates are declared. An unattended run with nothing to "
                  "verify against cannot know whether it succeeded.")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "trellis.json")
    if not os.path.exists(path):
        print(f"No trellis.json at {os.path.relpath(path, ROOT)}")
        print("Copy setup/trellis.json to the repo root once the project's stack is chosen.")
        return 0

    try:
        with open(path) as fh:
            config = json.load(fh)
    except Exception as exc:
        print(f"trellis.json is not valid JSON: {exc}", file=sys.stderr)
        return 1

    config = {k: v for k, v in config.items() if not k.startswith("$")}
    validate(config)

    if warnings:
        print("Warnings (%d):" % len(warnings))
        for message in warnings:
            print("  - " + message)
        print()

    if errors:
        print("Invalid (%d):" % len(errors), file=sys.stderr)
        for message in errors:
            print("  - " + message, file=sys.stderr)
        return 1

    print("trellis.json is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
