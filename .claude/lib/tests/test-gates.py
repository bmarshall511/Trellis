#!/usr/bin/env python3
"""Tests for the shared gate runner.

Two things are being pinned down. That every path which runs gates takes the lock — which was the
defect: pre-push had its own copy of the loop and no lock, so delivery's verify-then-push ran a
locked cycle and an unlocked one back to back. And that the verified-commit stamp fails closed,
because a stamp trusted too readily is a push that skipped its gates.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, LIB)
from gatelock import LOCK_NAME  # noqa: E402
from gates import GateBusy, declared_gates, run_gates, stamp_is_valid  # noqa: E402

FAILS = []


def check(condition, label):
    print(("  PASS  " if condition else "  FAIL  ") + label)
    if not condition:
        FAILS.append(label)


def new_repo(gates):
    root = tempfile.mkdtemp()
    subprocess.run(["git", "-C", root, "init", "-q"], check=True)
    subprocess.run(["git", "-C", root, "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", root, "config", "user.name", "t"], check=True)
    with open(os.path.join(root, "trellis.json"), "w") as handle:
        json.dump({"name": "t", "type": "library", "gates": gates}, handle)
    subprocess.run(["git", "-C", root, "add", "-A"], check=True)
    subprocess.run(["git", "-C", root, "commit", "-qm", "init"], check=True)
    return root


GREEN = {"types": "true", "lint": "true", "test": None, "a11y": None, "perf": None}
RED = {"types": "true", "lint": "sh -c 'echo boom >&2; exit 1'", "test": None,
       "a11y": None, "perf": None}

# Order and declaration. A gate set to null is declared absent, not silently missing.
check([n for n, _ in declared_gates({"gates": GREEN})] == ["types", "lint"],
      "only declared gates run, in cheapest-first order")

# Green run, then the stamp it leaves.
root = new_repo(GREEN)
ok, failed, _ = run_gates(root, declared_gates({"gates": GREEN}))
check(ok and failed is None, "a green run reports success")
check(stamp_is_valid(root, declared_gates({"gates": GREEN})),
      "a green run stamps the commit it verified")

# The stamp is what lets pre-push skip work delivery just did. Every way it could be wrong must
# come back false, because the cost of a wrong true is a push that skipped its gates.
with open(os.path.join(root, "untracked.txt"), "w") as handle:
    handle.write("edit")
check(not stamp_is_valid(root, declared_gates({"gates": GREEN})),
      "a dirty tree invalidates the stamp")
os.unlink(os.path.join(root, "untracked.txt"))
check(stamp_is_valid(root, declared_gates({"gates": GREEN})), "and it is valid again once clean")

check(not stamp_is_valid(root, declared_gates({"gates": RED})),
      "editing the gate commands invalidates the stamp")

with open(os.path.join(root, "moved.txt"), "w") as handle:
    handle.write("x")
subprocess.run(["git", "-C", root, "add", "-A"], check=True)
subprocess.run(["git", "-C", root, "commit", "-qm", "move"], check=True)
check(not stamp_is_valid(root, declared_gates({"gates": GREEN})),
      "a new commit invalidates the stamp")

run_gates(root, declared_gates({"gates": GREEN}))
stamp_path = os.path.join(root, ".claude", ".gates-verified.json")
with open(stamp_path) as handle:
    aged = json.load(handle)
aged["at"] = time.time() - 6000
with open(stamp_path, "w") as handle:
    json.dump(aged, handle)
check(not stamp_is_valid(root, declared_gates({"gates": GREEN})),
      "a stamp older than one gate run is not trusted")

with open(stamp_path, "w") as handle:
    handle.write("{ not json")
check(not stamp_is_valid(root, declared_gates({"gates": GREEN})),
      "an unreadable stamp is not trusted")
os.unlink(stamp_path)
check(not stamp_is_valid(root, declared_gates({"gates": GREEN})),
      "no stamp means run the gates")

# A red gate stops at the failure and reports which one, with its output.
root = new_repo(RED)
ok, failed, output = run_gates(root, declared_gates({"gates": RED}))
check(not ok and failed == "lint", "a red run names the gate that failed")
check("boom" in output, "and returns its output rather than an exit code")
check(not os.path.exists(os.path.join(root, ".claude", ".gates-verified.json")),
      "a red run stamps nothing")

# The lock. This is the defect: a gate runner that does not take it.
#
# .claude/lib is committed here because it is committed in a real project. Left untracked it makes
# the tree dirty, which correctly invalidates the stamp — and would have had this proving that the
# skip never happens, rather than that it happens when it should.
root = new_repo(GREEN)
os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
os.symlink(LIB, os.path.join(root, ".claude", "lib"))
subprocess.run(["git", "-C", root, "add", "-A"], check=True)
subprocess.run(["git", "-C", root, "commit", "-qm", "claude"], check=True)
holder = subprocess.Popen(
    [sys.executable, "-c",
     "import sys, time; sys.path.insert(0, %r)\n"
     "from gatelock import gate_lock\n"
     "with gate_lock(%r, owner='someone-else', timeout=0):\n"
     "    print('held', flush=True); time.sleep(30)\n" % (LIB, root)],
    stdout=subprocess.PIPE, text=True)
deadline = time.time() + 5
while time.time() < deadline and not os.path.exists(os.path.join(root, LOCK_NAME)):
    time.sleep(0.05)

refused = False
try:
    run_gates(root, declared_gates({"gates": GREEN}), lock_timeout=0)
except GateBusy:
    refused = True
check(refused, "the runner refuses while another gate run holds the lock")

# pre-push is the caller that used to have its own unlocked copy. Prove the real hook, as git would
# invoke it, now goes through the lock — not that some library function does.
REPO = os.path.abspath(os.path.join(LIB, "..", ".."))
hook = os.path.join(REPO, ".githooks", "pre-push")
proc = subprocess.run([hook], cwd=root, capture_output=True, text=True,
                      env={**os.environ, "TRELLIS_GATE_TIMEOUT": "0"})
check(proc.returncode == 1, "pre-push refuses to push while another gate run is in flight")
check("Push blocked" in (proc.stdout + proc.stderr),
      "and says the push was blocked rather than failing silently")

holder.kill()
holder.wait()

# With the lock free and a valid stamp, pre-push skips the work delivery just did. This is the
# 116 seconds the gates were running twice per delivery.
run_gates(root, declared_gates({"gates": GREEN}))
proc = subprocess.run([hook], cwd=root, capture_output=True, text=True)
check(proc.returncode == 0 and "already verified" in proc.stdout,
      "pre-push skips gates already proved green on this exact commit")

print()
if FAILS:
    print("%d case(s) wrong" % len(FAILS))
    sys.exit(1)
print("gates: all 18 cases correct")
