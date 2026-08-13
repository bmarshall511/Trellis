#!/usr/bin/env python3
"""Trellis verification gate — Stop hook.

Stops the agent from ending its turn while any quality gate is failing. This is what turns
"Claude says it's done" into "Claude proved it's done".

Gates come from trellis.json and run in cheapest-first order, stopping at the first failure so a
type error doesn't wait behind a five-minute test suite.

A loop guard caps consecutive blocks. Without it, a genuinely unfixable failure burns tokens forever.
After the cap the turn is allowed to end, with the remaining failures reported verbatim rather than
summarised — a paraphrased error is a lost error.

Exit 0 lets the turn end. Exit 2 blocks it and returns the failing output to the agent.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gatelock import GateBusy, gate_lock  # noqa: E402

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HOOK_DIR, "..", ".."))
STATE_FILE = os.path.join(REPO_ROOT, ".claude", ".verify-state.json")

# Cheapest first. A type error should surface in seconds, not after the test suite.
GATE_ORDER = ["types", "lint", "test", "a11y", "perf"]
DEFAULT_MAX_CONSECUTIVE = 3
TIMEOUT_SECONDS = 900


def load_config():
    try:
        with open(os.path.join(REPO_ROOT, "trellis.json")) as fh:
            return json.load(fh)
    except Exception:
        return None


def read_state():
    try:
        with open(STATE_FILE) as fh:
            return json.load(fh)
    except Exception:
        return {"consecutive_blocks": 0}


def write_state(state):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as fh:
            json.dump(state, fh)
    except Exception:
        pass  # State is an optimisation, not a correctness requirement.


def run_gate(name, command):
    """Return (ok, combined_output). A gate must exit non-zero on failure."""
    try:
        # shell=True is the design: gate commands come from trellis.json as shell strings so a
        # project can express any pipeline. They are the project's own config, not external input.
        proc = subprocess.run(  # noqa: S602
            command, shell=True, cwd=REPO_ROOT, capture_output=True,
            text=True, timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, "gate '%s' exceeded %ds and was killed" % (name, TIMEOUT_SECONDS)
    except Exception as exc:
        return False, f"gate '{name}' could not run: {exc}"
    if proc.returncode == 0:
        return True, ""
    return False, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main():  # noqa: PLR0911 — each early return is a distinct "do not block" condition
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0

    # If a Stop hook already blocked this turn, Claude Code re-invokes us. Don't recurse forever.
    if event.get("stop_hook_active"):
        return 0

    config = load_config()
    if config is None:
        return 0  # No trellis.json yet — nothing to verify against. Not an error.

    gates = config.get("gates") or {}
    declared = [(n, gates[n]) for n in GATE_ORDER if gates.get(n)]
    if not declared:
        return 0

    state = read_state()
    max_consecutive = (
        (config.get("autonomy") or {}).get("maxRepairAttempts", DEFAULT_MAX_CONSECUTIVE - 1) + 1
    )

    # Serialised: gates bind ports and name containers, and the delivery script runs them too. Two at
    # once produces connection errors that read as product bugs rather than as contention.
    try:
        lock = gate_lock(REPO_ROOT, owner="verify-gate", timeout=1200)
        lock.__enter__()
    except GateBusy as busy:
        sys.stderr.write(
            "Trellis: could not run the gates — %s\n\nThis turn is NOT verified. Do not report the "
            "work as complete.\n" % busy)
        return 2

    try:
        return run_declared(declared, state, max_consecutive)
    finally:
        lock.__exit__()


def run_declared(declared, state, max_consecutive):
    for name, command in declared:
        ok, output = run_gate(name, command)
        if ok:
            continue

        blocks = state.get("consecutive_blocks", 0) + 1
        write_state({"consecutive_blocks": blocks, "last_failed_gate": name})

        if blocks > max_consecutive:
            write_state({"consecutive_blocks": 0})
            sys.stderr.write(
                "Trellis: gate '%s' has failed %d times in a row. Letting the turn end so this\n"
                "does not loop indefinitely.\n\nThis work is NOT complete. Do not report it as done.\n"
                "Report the failure to the user and stop.\n\n--- %s output ---\n%s\n"
                % (name, blocks, name, output[:4000])
            )
            return 0

        sys.stderr.write(
            "Trellis: the '%s' gate is failing, so this work is not complete.\n\n"
            "Fix the failures below, then finish. Do not mark the spec done, do not summarise this\n"
            "as a success, and do not disable or weaken the gate. If the gate itself is wrong, say so\n"
            "and stop rather than working around it.\n\n"
            "Attempt %d of %d before this stops blocking.\n\n--- %s: %s ---\n%s\n"
            % (name, blocks, max_consecutive, name, command, output[:6000])
        )
        return 2

    write_state({"consecutive_blocks": 0})
    return 0


if __name__ == "__main__":
    sys.exit(main())
