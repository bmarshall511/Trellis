"""Running the gates a project declares. The only place that does it.

There were two copies of this: the Stop hook and the pre-push hook. They agreed on the order and on
stopping at the first failure, so the duplication looked harmless. It was not — when the gate lock
arrived, only one copy took it, and delivery pushes right after verifying, so a full locked cycle was
followed immediately by a full unlocked one. That is the exact window the lock existed to close, and
it stayed open for three failed deliveries.

The property that fixes it is not "remember to take the lock in both places". It is that there is one
place. A second gate runner cannot forget the lock if a second gate runner does not exist.

Verified-commit stamp
---------------------
Delivery runs the gates, then pushes, which runs them again on the same commit seconds later. That is
duplicated work — around two minutes on a project with a11y and perf gates — and it is what put two
full cycles back to back.

So a successful run records what it proved: the commit, the gate commands it ran, and when. pre-push
skips only when all of that still holds and the tree is clean. Every uncertainty runs the gates:
no stamp, unreadable stamp, different commit, edited gate commands, dirty tree, or old.

This is not a security control and must not be read as one. It is a cache, and a writable one — the
same class as the loop-guard state beside it. `--no-verify` stays blocked by the guard because it
skips gates that never ran; this skips gates that just ran and passed on this exact tree. The thing
that cannot be forged locally is CI, and delivery still waits for it.
"""
import hashlib
import json
import os
import subprocess
import time

from gatelock import GateBusy, gate_lock

__all__ = ["GATE_ORDER", "GateBusy", "declared_gates", "run_gates", "stamp_is_valid"]

# Cheapest first. A type error should surface in seconds, not after the test suite.
GATE_ORDER = ["types", "lint", "test", "a11y", "perf"]
TIMEOUT_SECONDS = 900
STAMP_NAME = ".claude/.gates-verified.json"
STAMP_MAX_AGE = 900  # a stamp older than one gate run is not describing the tree in front of you


def declared_gates(config):
    """The gates this project declares, in run order. A gate set to null is declared absent."""
    gates = (config or {}).get("gates") or {}
    return [(name, gates[name]) for name in GATE_ORDER if gates.get(name)]


def _fingerprint(declared):
    """Identifies the gate commands, so editing one invalidates a stamp taken under the old set."""
    return hashlib.sha256(json.dumps(declared, sort_keys=True).encode()).hexdigest()


def _git(root, *args):
    try:
        proc = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def _tree_is_clean(root):
    """Clean apart from Trellis's own runtime state, which is always moving while gates run.

    The stamp is written while the lock is held, so the lock file is on disk when this is asked —
    and it made every tree dirty, so no stamp was ever written. Filtering here rather than relying
    on .gitignore, because the entry reaches a project only when it next updates, and something
    that silently stops working until then is worse than the duplicated work it was meant to save.
    """
    # --untracked-files=all matters: git collapses a wholly-untracked directory into a single
    # `?? .claude/` entry, which no per-file filter can recognise as runtime state.
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status is None:
        return False  # git failed: unknown is not clean
    for line in status.splitlines():
        path = line[3:].strip().strip('"')
        if not path:
            continue
        if not path.startswith(".claude/."):
            return False
    return True


def _write_stamp(root, declared):
    head = _git(root, "rev-parse", "HEAD")
    if not head or not _tree_is_clean(root):
        return  # nothing worth recording about a tree that is still moving
    path = os.path.join(root, STAMP_NAME)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)  # a fresh project has no .claude/ yet
        with open(path, "w") as handle:
            json.dump({"sha": head, "gates": _fingerprint(declared), "at": time.time()}, handle)
    except OSError:
        pass  # the stamp is an optimisation; failing to write one costs time, not correctness


def stamp_is_valid(root, declared):
    """True only if these exact gates already passed on exactly this tree, recently.

    Every branch returns False on doubt. The cost of a wrong False is running the gates again; the
    cost of a wrong True is pushing something unverified.
    """
    try:
        with open(os.path.join(root, STAMP_NAME)) as handle:
            stamp = json.load(handle)
    except Exception:
        return False
    if stamp.get("gates") != _fingerprint(declared):
        return False
    if not isinstance(stamp.get("at"), (int, float)) or time.time() - stamp["at"] > STAMP_MAX_AGE:
        return False
    head = _git(root, "rev-parse", "HEAD")
    if not head or stamp.get("sha") != head:
        return False
    return _tree_is_clean(root)


def _run_one(root, name, command, stream):
    """Return (ok, combined_output). A gate must exit non-zero on failure."""
    try:
        # shell=True is the design: gate commands come from trellis.json as shell strings so a
        # project can express any pipeline. They are the project's own config, not external input.
        proc = subprocess.run(  # noqa: S602
            command, shell=True, cwd=root, text=True, timeout=TIMEOUT_SECONDS,
            capture_output=not stream,
        )
    except subprocess.TimeoutExpired:
        return False, "gate '%s' exceeded %ds and was killed" % (name, TIMEOUT_SECONDS)
    except Exception as exc:
        return False, "gate '%s' could not run: %s" % (name, exc)
    if proc.returncode == 0:
        return True, ""
    if stream:
        return False, ""  # already on the terminal; capturing it too would print it twice
    return False, ((proc.stdout or "") + (proc.stderr or "")).strip()


def run_gates(root, declared, stream=False, lock_timeout=240, announce=None):
    """Run the declared gates under the lock, stopping at the first failure.

    Returns (ok, failed_gate_name, output). Raises GateBusy if another gate run holds the lock —
    callers decide whether that is fatal, because it means something else is doing this work.
    """
    with gate_lock(root, owner="gates", timeout=lock_timeout):
        for name, command in declared:
            if announce:
                announce(name, command)
            ok, output = _run_one(root, name, command, stream)
            if not ok:
                return False, name, output
        _write_stamp(root, declared)
        return True, None, ""
