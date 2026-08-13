#!/usr/bin/env python3
"""Tests for the gate lock.

The bug it prevents does not look like contention: two gate runs binding the same port produce
connection errors that read as a broken product. So the lock is worth testing properly.
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from gatelock import LOCK_NAME, GateBusy, gate_lock  # noqa: E402

FAILS = []


def check(condition, label):
    print(("  PASS  " if condition else "  FAIL  ") + label)
    if not condition:
        FAILS.append(label)


root = tempfile.mkdtemp()
lock_path = os.path.join(root, LOCK_NAME)

# A second holder must be refused while the first has it.
with gate_lock(root, owner="first", timeout=1):
    refused = False
    try:
        with gate_lock(root, owner="second", timeout=0):
            pass
    except GateBusy:
        refused = True
    check(refused, "a second run is refused while the first holds the lock")

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
print("gatelock: all 5 cases correct")
