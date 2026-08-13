#!/usr/bin/env python3
"""Tests for the gate lock.

The bug it prevents does not look like contention: two gate runs binding the same port produce
connection errors that read as a broken product. So the lock is worth testing properly.
"""
import os
import subprocess
import sys
import tempfile
import time

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, LIB)
from gatelock import HELD_ENV, LOCK_NAME, GateBusy, gate_lock  # noqa: E402

FAILS = []


def check(condition, label):
    print(("  PASS  " if condition else "  FAIL  ") + label)
    if not condition:
        FAILS.append(label)


root = tempfile.mkdtemp()
lock_path = os.path.join(root, LOCK_NAME)


def in_process(body, env=None):
    """Run a snippet in a separate interpreter. Returns (exit code, stdout+stderr).

    Cross-process is the only honest way to test this. The first version of these tests acquired
    twice inside one interpreter, which the lock has no trouble with — and so they passed while the
    delivery script's lock was reclaimable in two seconds by anything that asked.
    """
    environment = dict(os.environ)
    if env is not None:
        environment.update(env)
        for key, value in env.items():
            if value is None:
                environment.pop(key, None)
    proc = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, %r)\n%s" % (LIB, body)],
        capture_output=True, text=True, env=environment)
    return proc.returncode, proc.stdout + proc.stderr


def wait_for_lock(deadline=5):
    stop = time.time() + deadline
    while time.time() < stop:
        if os.path.exists(lock_path):
            return True
        time.sleep(0.05)
    return False


# A live holder in another process must refuse this one. This is the pairing that matters — the Stop
# hook against delivery — and it is the one the original tests never exercised.
holder = subprocess.Popen(
    [sys.executable, "-c",
     "import sys, time; sys.path.insert(0, %r)\n"
     "from gatelock import gate_lock\n"
     "with gate_lock(%r, owner='other-process', timeout=0):\n"
     "    print('held', flush=True); time.sleep(30)\n" % (LIB, root)],
    stdout=subprocess.PIPE, text=True)
check(wait_for_lock(), "a holder in another process writes the lock")

refused = False
try:
    with gate_lock(root, owner="mine", timeout=0):
        pass
except GateBusy:
    refused = True
check(refused, "a live holder in another process refuses this one")

# A process that acquires and exits is the misuse that made the first version useless: the lock is
# stale the instant it is written. Nothing can distinguish that from a crash, so the test's job is
# to state plainly what such a lock is worth.
holder.kill()
holder.wait()
code, _ = in_process(
    "from gatelock import gate_lock\n"
    "gate_lock(%r, owner='exits-immediately', timeout=0).__enter__()\n" % root)
reclaimed_from_dead_acquirer = False
try:
    with gate_lock(root, owner="anyone", timeout=4):
        reclaimed_from_dead_acquirer = True
except GateBusy:
    pass
check(reclaimed_from_dead_acquirer,
      "a lock taken by a process that then exits protects nothing (so never take one that way)")

# Reentrancy, and its limit. Delivery invokes the Stop hook, which locks too — without this the
# parent waits on its own child for the full timeout and then reports the gates as red.
with gate_lock(root, owner="outer", timeout=0):
    code, out = in_process(
        "from gatelock import GateBusy, gate_lock\n"
        "try:\n"
        "    with gate_lock(%r, owner='child', timeout=0):\n"
        "        print('acquired')\n"
        "except GateBusy:\n"
        "    print('refused')\n" % root)
    check("acquired" in out, "a child of the holder acquires reentrantly instead of deadlocking")

    # But only a descendant. An unrelated process must still be refused, or reentrancy would have
    # quietly disabled the lock for everyone.
    code, out = in_process(
        "from gatelock import GateBusy, gate_lock\n"
        "try:\n"
        "    with gate_lock(%r, owner='stranger', timeout=0):\n"
        "        print('acquired')\n"
        "except GateBusy:\n"
        "    print('refused')\n" % root, env={HELD_ENV: None})
    check("refused" in out, "a process that is not a descendant is still refused")

    # And a reentrant acquire must not release what it did not take.
    with gate_lock(root, owner="inner", timeout=0):
        pass
    check(os.path.exists(lock_path), "a reentrant release leaves the outer holder's lock in place")

check(not os.path.exists(lock_path), "the outermost holder releases it")

# And must succeed once it is free.
acquired = False
try:
    with gate_lock(root, owner="third", timeout=0):
        acquired = True
except GateBusy:
    pass
check(acquired, "the lock is released when the block exits")

# A crashed run must not block the next one forever. pid 999999 will not exist.
with open(lock_path, "w") as handle:
    handle.write("999999\n%f\nghost\n" % time.time())
reclaimed = False
try:
    with gate_lock(root, owner="after-crash", timeout=4):
        reclaimed = True
except GateBusy:
    pass
check(reclaimed, "a lock whose owner died is reclaimed")

# Nor must a lock older than any honest gate run, even if some process now has that pid.
with open(lock_path, "w") as handle:
    handle.write("%d\n%f\nancient\n" % (os.getpid(), time.time() - 7200))
reclaimed = False
try:
    with gate_lock(root, owner="after-stale", timeout=4):
        reclaimed = True
except GateBusy:
    pass
check(reclaimed, "a lock older than any honest run is reclaimed")

# An exception inside the block must still release it, or one failure wedges every later run.
try:
    with gate_lock(root, owner="raiser", timeout=1):
        raise RuntimeError("gate blew up")
except RuntimeError:
    pass
released = not os.path.exists(lock_path)
check(released, "the lock is released even when the gates raise")

os.path.exists(lock_path) and os.unlink(lock_path)
os.rmdir(os.path.join(root, ".claude")) if os.path.isdir(os.path.join(root, ".claude")) else None

print()
if FAILS:
    print("%d case(s) wrong" % len(FAILS))
    sys.exit(1)
print("gatelock: all 11 cases correct")
