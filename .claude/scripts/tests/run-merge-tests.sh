#!/usr/bin/env bash
# Tests the automatic merge path.
#
# This is the only route to the default branch, so every way it should REFUSE matters more than the
# one way it should proceed.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
FAILS=0

setup() {  # setup <outcome> <mayMerge> [extra-file]
  DIR="$(mktemp -d)"; cp -R "$ROOT/.claude" "$DIR/"; mkdir -p "$DIR/stacks"
  cp -R "$ROOT/stacks/github" "$DIR/stacks/" 2>/dev/null
  cd "$DIR" || exit 1
  git init -q -b main; git config user.email t@t; git config user.name t
  mkdir -p docs/specs docs/runs tests
  cat > trellis.json <<JSON
{"name":"m","type":"library",
 "gates":{"types":null,"lint":null,"test":"node --test tests/ 2>/dev/null","a11y":null,"perf":null},
 "autonomy":{"enabled":true,"maxRepairAttempts":1,"mayMerge":$2}}
JSON
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
  printf 'import {test} from "node:test";import assert from "node:assert";\ntest("base",()=>assert.ok(1));\n' > tests/base.test.js
  git add -A >/dev/null; git commit -qm init
  git checkout -qb agent/SPEC-001
  mkdir -p src; echo 'export const add=(a,b)=>a+b;' > src/add.js
  printf 'import {test} from "node:test";import assert from "node:assert";\n// AC-1\ntest("ac1_adds",()=>assert.equal(2,2));\n' > tests/add.test.js
  [[ -n "${3:-}" ]] && { mkdir -p "$(dirname "$3")"; echo "content" > "$3"; }
  git add -A >/dev/null; git commit -qm work
  git checkout -q main
  printf '# Run report — SPEC-001\n\n**Outcome:** %s\n' "$1" > docs/runs/SPEC-001.md
  git add -A >/dev/null; git commit -qm report
}
teardown() { cd "$ROOT" || exit 1; rm -rf "$DIR"; }

check() {  # check <want merged|refused> <label>
  local want="$1" label="$2" got=refused
  ./.claude/scripts/merge-run.sh SPEC-001 >/dev/null 2>&1 && got=merged
  if [[ "$got" == "$want" ]]; then printf "  PASS  %-52s %s\n" "$label" "$got"
  else printf "  FAIL  %-52s %s (wanted %s)\n" "$label" "$got" "$want"; FAILS=$((FAILS+1)); fi
}

echo "Automatic merge:"
setup DONE true;      check merged  "DONE, mayMerge on, low-risk diff"; teardown
setup DONE false;     check refused "mayMerge off"; teardown
setup BLOCKED true;   check refused "run was BLOCKED"; teardown
setup FAILED true;    check refused "run was FAILED"; teardown
setup TAMPERED true;  check refused "run was TAMPERED"; teardown
setup DONE true ".github/workflows/ci.yml"; check refused "diff touches CI config"; teardown
setup DONE true "package.json";             check refused "diff adds a dependency manifest"; teardown
setup DONE true "src/auth/session.js";      check refused "diff touches auth"; teardown

# gates red on the branch, though the report claims DONE
setup DONE true; git checkout -q agent/SPEC-001
printf 'import {test} from "node:test";import assert from "node:assert";\ntest("fails",()=>assert.equal(1,2));\n' > tests/broken.test.js
git add -A >/dev/null; git commit -qm break; git checkout -q main
check refused "report says DONE but gates are red on the branch"; teardown

# no classifier available at all
setup DONE true; rm -rf stacks
check refused "no risk classifier in any stack module"; teardown

echo
if [[ $FAILS -eq 0 ]]; then echo "merge: all 10 cases correct"; else echo "$FAILS case(s) wrong"; fi
exit $FAILS
