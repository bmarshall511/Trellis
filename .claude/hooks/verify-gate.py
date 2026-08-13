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
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gates import GateBusy, declared_gates, run_gates

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HOOK_DIR, "..", ".."))
STATE_FILE = os.path.join(REPO_ROOT, ".claude", ".verify-state.json")

DEFAULT_MAX_CONSECUTIVE = 3


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

    declared = declared_gates(config)
    if not declared:
        return 0

    state = read_state()
    max_consecutive = (
        (config.get("autonomy") or {}).get("maxRepairAttempts", DEFAULT_MAX_CONSECUTIVE - 1) + 1
    )

    # Serialised: gates bind ports and name containers, and the delivery script runs them too. Two at
    # once produces connection errors that read as product bugs rather than as contention.
    #
    # The wait is deliberately short for a hook. Waiting out a full delivery — half an hour, most of
    # it spent on CI — is indistinguishable from a hang, and pointless: whatever holds the lock is
    # already running the gates this hook wants to run. Long enough to sit out a gate run that is
    # nearly done, then say so plainly.
    try:
        run_result = run_gates(
            REPO_ROOT, declared,
            lock_timeout=int(os.environ.get("TRELLIS_GATE_TIMEOUT", "240")))
    except GateBusy as busy:
        sys.stderr.write(
            "Trellis: could not run the gates — %s\n\nThis turn is NOT verified. Do not report the "
            "work as complete. If a delivery is running, wait for it to finish and check its log "
            "rather than re-running the gates.\n" % busy)
        return 2

    ok, name, output = run_result
    if ok:
        write_state({"consecutive_blocks": 0})
        return 0

    command = dict(declared).get(name, name)
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


if __name__ == "__main__":
    sys.exit(main())
