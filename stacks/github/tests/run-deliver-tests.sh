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

echo
if [ $FAILS -eq 0 ]; then
  echo "deliver: all 11 cases correct"
else
  echo "$FAILS case(s) wrong"
fi
exit $FAILS
