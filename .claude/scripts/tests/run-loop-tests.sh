#!/usr/bin/env bash
# Verifies the unattended runner reaches the right verdict for each way a run can go wrong.
# The runner must judge by evidence — gates and coverage — never by what the agent claims.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
MOCK="$ROOT/.claude/scripts/tests/mock-claude.sh"
FAILS=0

scenario() {
  local behaviour="$1" want="$2" label="$3"
  local dir; dir="$(mktemp -d)"
  cp -R "$ROOT/.claude" "$dir/" 2>/dev/null
  cd "$dir" || return
  git init -q; git config user.email t@t; git config user.name t
  mkdir -p docs/specs docs/runs
  cat > trellis.json <<'JSON'
{"name":"loop-test","type":"library",
 "gates":{"types":null,"lint":null,"test":"node --test tests/ 2>/dev/null","a11y":null,"perf":null},
 "autonomy":{"enabled":true,"maxRepairAttempts":1}}
JSON
  cat > docs/specs/SPEC-001-add.md <<'MD'
---
id: SPEC-001
title: Add two numbers
status: ready
type: feature
surfaces: []
depends: []
estimate: 20
created: 2026-08-11
---
## Why
Adding is needed.
## Acceptance criteria
1. When given two numbers, the system shall return their sum.
## Out of scope
- Subtraction.
## Open questions
_None._
MD
  mkdir -p tests && printf 'import {test} from "node:test";import assert from "node:assert";\ntest("baseline", () => assert.ok(1));\n' > tests/baseline.test.js
  git add -A >/dev/null && git commit -qm init

  MOCK_BEHAVIOUR="$behaviour" TRELLIS_CLAUDE_BIN="$MOCK" TRELLIS_NOTIFY_CMD=/usr/bin/true \
    "$dir/.claude/scripts/run-spec.sh" SPEC-001 >/dev/null 2>&1
  local code=$?
  local got
  case $code in 0) got=DONE ;; 2) got=BLOCKED ;; *) got=FAILED ;; esac
  # For tamper cases, require the report to say so explicitly rather than failing incidentally.
  if [[ "$behaviour" == "vandal" || "$behaviour" == "saboteur" ]] \
     && ! grep -q TAMPERED docs/runs/SPEC-001.md 2>/dev/null; then
    got="FAILED-but-not-detected-as-tampering"
  fi
  if [[ "$got" == "$want" ]]; then
    printf "  PASS  %-8s → %-8s %s\n" "$behaviour" "$got" "$label"
  else
    printf "  FAIL  %-8s → %-8s (wanted %s) %s\n" "$behaviour" "$got" "$want" "$label"
    FAILS=$((FAILS+1))
  fi
  cd "$ROOT"; rm -rf "$dir"
}

echo "Unattended runner verdicts:"
scenario good    DONE    "implements properly"
scenario blocked BLOCKED "asks rather than guessing"
scenario crash   FAILED  "exits non-zero with no BLOCKED.md"
scenario liar    FAILED  "claims success with a gate red"
scenario sneaky  FAILED  "claims success with a criterion uncovered"
scenario vandal  FAILED  "disables the gates, then claims success"
scenario saboteur FAILED "empties a stack module's production guard rules"

echo
[[ $FAILS -eq 0 ]] && echo "loop: all 7 scenarios reach the correct verdict" || echo "$FAILS scenario(s) wrong"
exit $FAILS
