#!/usr/bin/env bash
# Tests pull-request delivery: push, open, poll CI, repair, merge, sync.
#
# Every way it should stop matters more than the one way it should succeed, because a queue continues
# only on success — so a wrong "delivered" is the expensive answer.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MOCK_GH_BIN="$ROOT/stacks/github/tests/mock-gh.sh"
MOCK_CLAUDE="$ROOT/stacks/github/tests/mock-repair.sh"
FAILS=0

setup() {  # setup <outcome> <mergeVia> [extra-file]
  # The bare remote lives OUTSIDE the working tree. Inside it, git sees its refs as untracked files
  # and refuses to switch branches — which looked exactly like a delivery bug for a while.
  SANDBOX="$(mktemp -d)"
  DIR="$SANDBOX/repo"
  REMOTE="$SANDBOX/remote.git"
  mkdir -p "$DIR"
  cp -R "$ROOT/.claude" "$DIR/"
  # The real .gitignore, not an empty tree. Without it the sandbox does not ignore runtime state, so
  # a held gate lock makes the tree dirty and delivery refuses for the wrong reason — which is
  # exactly the bug that shipped, and a sandbox that cannot reproduce it cannot prove it fixed.
  cp "$ROOT/.gitignore" "$DIR/.gitignore"
  rm -f "$DIR/.claude/.gates.lock" "$DIR/.claude/.verify-state.json"
  mkdir -p "$DIR/stacks"
  cp -R "$ROOT/stacks/github" "$DIR/stacks/"
  cd "$DIR" || exit 1
  rm -f /tmp/trellis-mock-gh-count

  git init -q -b main
  git config user.email t@t
  git config user.name t
  mkdir -p docs/specs docs/runs tests

  cat > trellis.json <<'JSON'
{"name":"d","type":"library",
 "gates":{"types":null,"lint":null,"test":"node --test tests/ 2>/dev/null","a11y":null,"perf":null},
 "autonomy":{"enabled":true,"mayMerge":true,"mergeVia":"MERGEVIA","maxRepairAttempts":1}}
JSON
  python3 - "$2" <<'PY'
import sys
p = "trellis.json"
# Read fully BEFORE opening for write. `open(p,"w").write(open(p).read())` truncates the file first,
# because Python builds the write handle before evaluating the read — so the file ends up empty.
text = open(p).read().replace("MERGEVIA", sys.argv[1])
with open(p, "w") as fh:
    fh.write(text)
PY

  cat > docs/specs/SPEC-001-add.md <<'MD'
---
id: SPEC-001
title: Add
status: done
type: feature
surfaces: []
depends: []
estimate: 20
created: 2026-08-11
---
## Why
Adding.
## Acceptance criteria
1. When given two numbers, the system shall return their sum.
## Out of scope
- Subtraction.
## Open questions
_None._
MD
  printf 'import {test} from "node:test";import assert from "node:assert";\ntest("b",()=>assert.ok(1));\n' > tests/b.test.js
  git add -A >/dev/null
  git commit -qm init

  git init -q --bare "$REMOTE"
  git remote add origin "$REMOTE"
  git push -q origin main 2>/dev/null

  git checkout -qb agent/SPEC-001
  mkdir -p src
  echo 'export const add=(a,b)=>a+b;' > src/add.js
  printf 'import {test} from "node:test";import assert from "node:assert";\n// AC-1\ntest("ac1_adds",()=>assert.equal(2,2));\n' > tests/add.test.js
  if [ -n "${3:-}" ]; then mkdir -p "$(dirname "$3")"; echo x > "$3"; fi
  git add -A >/dev/null
  git commit -qm work
  git checkout -q main

  printf '# Run report — SPEC-001\n\n**Outcome:** %s\n' "$1" > docs/runs/SPEC-001.md
  git add -A >/dev/null
  git commit -qm report
  git push -q origin main 2>/dev/null
}

teardown() { cd "$ROOT" || exit 1; rm -rf "$SANDBOX"; }

check() {  # check <expected exit> <label>
  local want="$1" label="$2" got
  TRELLIS_GH_BIN="$MOCK_GH_BIN" \
  TRELLIS_CLAUDE_BIN="$MOCK_CLAUDE" \
  TRELLIS_CHECK_TIMEOUT=6 TRELLIS_MERGE_TIMEOUT=6 \
    ./stacks/github/scripts/deliver-run.sh SPEC-001 >"$SANDBOX/out.txt" 2>&1
  got=$?
  if [ "$got" = "$want" ]; then
    printf "  PASS  %-52s exit %s\n" "$label" "$got"
  else
    printf "  FAIL  %-52s exit %s (wanted %s)\n" "$label" "$got" "$want"
    sed 's/^/          /' "$SANDBOX/out.txt" | tail -6
    FAILS=$((FAILS + 1))
  fi
}

# MOCK_GH is exported rather than prefixed onto `setup`, because a prefix applies to that one command
# only — `check` then ran with the default and four scenarios silently tested the happy path.
scenario() {  # scenario <mock> <outcome> <mergeVia> <expected exit> <label> [extra-file]
  export MOCK_GH="$1"
  setup "$2" "$3" "${6:-}"
  check "$4" "$5"
  teardown
}

echo "Pull-request delivery:"
scenario green          DONE     pull-request 0 "checks green, merged"
scenario red-then-green DONE     pull-request 0 "CI fails once, repaired, merged"
scenario red            DONE     pull-request 1 "CI fails past the repair budget"
scenario pending        DONE     pull-request 1 "checks never finish, times out"
scenario nochecks       DONE     pull-request 0 "no checks configured, local gates only"
scenario mergerefused   DONE     pull-request 1 "merge refused"
scenario notmerged      DONE     pull-request 1 "merge claimed but PR not merged"
scenario green          DONE     pull-request 3 "risky diff, held for review" ".github/workflows/ci.yml"
scenario green          BLOCKED  pull-request 1 "run was BLOCKED"
scenario green          TAMPERED pull-request 1 "run was TAMPERED"
scenario green          DONE     local        1 "mergeVia is local, refuses"
scenario labelfail      DONE     pull-request 0 "repo has no labels and cannot create them"
scenario resume         DONE     pull-request 0 "a pull request is already open, resumed not duplicated"

# Where does the caller end up? Returning them to a branch the script chose was what made a retry
# fail with "no run report" — the report lived on the branch they had just been moved off.
branch_case() {  # branch_case <mock> <start branch> <expected end branch> <label>
  export MOCK_GH="$1"
  setup DONE pull-request
  git checkout -q "$2" 2>/dev/null
  TRELLIS_GH_BIN="$MOCK_GH_BIN" TRELLIS_CLAUDE_BIN="$MOCK_CLAUDE" \
  TRELLIS_CHECK_TIMEOUT=6 TRELLIS_MERGE_TIMEOUT=6 \
    ./stacks/github/scripts/deliver-run.sh SPEC-001 >/dev/null 2>&1
  local ended; ended="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$ended" = "$3" ]; then
    printf "  PASS  %-52s on %s\n" "$4" "$ended"
  else
    printf "  FAIL  %-52s on %s (wanted %s)\n" "$4" "$ended" "$3"
    FAILS=$((FAILS + 1))
  fi
  teardown
}

# Gate contention, end to end.
#
# Delivery used to take a lock of its own here, from a throwaway `python3 -` that wrote its pid and
# exited, so it was stale the instant it was written and anything else reclaimed it in two seconds.
# It was not the cause of collisions — the only thing that runs the gates is verify-gate.py, which
# locks correctly — but it read as protection while providing none, and the `rm -f` release was the
# tell. It is gone; this proves the remaining path still refuses.
#
# Against a live holder the old code did block, just for the full 1200s and then reporting the
# result as red gates. So what this case pins down is the message and the speed, not the refusal.
export MOCK_GH=green
setup DONE pull-request
python3 -c "
import sys, time
sys.path.insert(0, '$DIR/.claude/lib')
from gatelock import gate_lock
with gate_lock('$DIR', owner='someone-else', timeout=0):
    print('held', flush=True); time.sleep(25)
" >/dev/null 2>&1 &
HOLDER=$!
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -f "$DIR/.claude/.gates.lock" ] && break; sleep 0.3; done
TRELLIS_GATE_TIMEOUT=2 \
TRELLIS_GH_BIN="$MOCK_GH_BIN" TRELLIS_CLAUDE_BIN="$MOCK_CLAUDE" \
TRELLIS_CHECK_TIMEOUT=6 TRELLIS_MERGE_TIMEOUT=6 \
  ./stacks/github/scripts/deliver-run.sh SPEC-001 >"$SANDBOX/out.txt" 2>&1
GOT=$?
kill $HOLDER 2>/dev/null; wait $HOLDER 2>/dev/null
if [ "$GOT" = "1" ]; then
  printf "  PASS  %-52s exit 1\n" "another gate run in flight, delivery refuses"
else
  printf "  FAIL  %-52s exit %s (wanted 1)\n" "another gate run in flight, delivery refuses" "$GOT"
  FAILS=$((FAILS + 1))
fi
# Contention is not red gates. Reporting it as red sends the reader to the code to look for a bug
# that is not there.
if grep -q "could not run the gates" "$SANDBOX/out.txt" 2>/dev/null; then
  printf "  PASS  %-52s not reported as red gates\n" "and says it is contention"
else
  printf "  FAIL  %-52s\n" "contention reported as a gate failure"
  sed 's/^/          /' "$SANDBOX/out.txt" | tail -4
  FAILS=$((FAILS + 1))
fi
teardown

# Delivery verifies, then pushes — and pushing runs pre-push, which used to run every gate again on
# the same commit seconds later. Two full cycles back to back, around two minutes of duplicated work
# on a project with a11y and perf gates, and the window in which a third gate run could start.
#
# Counting is the only honest way to check this: both cycles passed, so nothing failed and nothing
# in the log said the gates had run twice.
export MOCK_GH=green
setup DONE pull-request
COUNTER="$SANDBOX/gate-runs"
: > "$COUNTER"
python3 - "$COUNTER" <<'PY'
import json, sys
config = json.load(open("trellis.json"))
config["gates"]["test"] = "echo x >> %s; node --test tests/ 2>/dev/null" % sys.argv[1]
with open("trellis.json", "w") as handle:
    json.dump(config, handle)
PY
git add -A >/dev/null && git commit -qm "counting gate" && git push -q origin main 2>/dev/null
git checkout -q agent/SPEC-001 && git merge -q main -m merge 2>/dev/null && git checkout -q main
git config core.hooksPath .githooks   # a real project sets this; the sandbox did not, so pre-push never fired
TRELLIS_GH_BIN="$MOCK_GH_BIN" TRELLIS_CLAUDE_BIN="$MOCK_CLAUDE" \
TRELLIS_CHECK_TIMEOUT=6 TRELLIS_MERGE_TIMEOUT=6 \
  ./stacks/github/scripts/deliver-run.sh SPEC-001 >"$SANDBOX/out.txt" 2>&1
RUNS="$(wc -l < "$COUNTER" | tr -d ' ')"
if [ "$RUNS" = "1" ]; then
  printf "  PASS  %-52s ran once\n" "the gates run once per delivery, not once per push"
else
  printf "  FAIL  %-52s ran %s times\n" "the gates run once per delivery, not once per push" "$RUNS"
  FAILS=$((FAILS + 1))
fi
teardown

# An expired session cannot be repaired by retrying, so it must stop at once rather than spend the
# budget attempting nothing and then blaming the code.
export MOCK_GH=authfail
setup DONE pull-request
MOCK_CLAUDE_SAVED="$MOCK_CLAUDE"
MOCK_CLAUDE="$ROOT/stacks/github/tests/mock-repair-authfail.sh"
check 1 "repair agent cannot authenticate, stops immediately"
if grep -q "could not authenticate" "$SANDBOX/out.txt" 2>/dev/null; then
  printf "  PASS  %-52s reported as auth, not as a code failure\n" "and says so plainly"
else
  printf "  FAIL  %-52s\n" "auth failure not distinguished from a code failure"
  FAILS=$((FAILS + 1))
fi
MOCK_CLAUDE="$MOCK_CLAUDE_SAVED"
teardown

echo
echo "Where the caller ends up:"
branch_case mergerefused agent/SPEC-001 agent/SPEC-001 "failure from the agent branch returns there"
branch_case mergerefused main           main           "failure from the default branch returns there"
branch_case green        agent/SPEC-001 main           "success lands on the default branch"

echo
if [ $FAILS -eq 0 ]; then
  echo "deliver: all 21 cases correct"
else
  echo "$FAILS case(s) wrong"
fi
exit $FAILS
