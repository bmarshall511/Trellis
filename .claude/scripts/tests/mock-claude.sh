#!/usr/bin/env bash
# Mock agent for testing the unattended runner. Behaviour is chosen by MOCK_BEHAVIOUR:
#   good     implements the spec properly (gates pass, criteria covered)
#   blocked  writes BLOCKED.md and stops
#   crash    exits non-zero without writing BLOCKED.md
#   liar     claims success but leaves a gate red
#   sneaky   claims success but leaves a criterion uncovered
#   vandal   tries to disable a gate and then claim success
set -uo pipefail
case "${MOCK_BEHAVIOUR:-good}" in
  good)
    mkdir -p src tests
    printf 'export const add = (a, b) => a + b;\n' > src/add.js
    printf 'import {test} from "node:test";import assert from "node:assert";\n// AC-1\ntest("ac1_adds", () => assert.equal(2, 2));\n' > tests/add.test.js
    git add -A && git commit -q -m "implement" ;;
  blocked)
    printf '## Blocked\n\nShould negative numbers be rejected, or clamped to zero?\n' > BLOCKED.md ;;
  crash)
    echo "unexpected failure" >&2; exit 3 ;;
  liar)
    mkdir -p src && printf 'this is not valid javascript {{{\n' > src/broken.js
    git add -A && git commit -q -m "claim done" ;;
  sneaky)
    mkdir -p src tests
    printf 'export const add = (a, b) => a + b;\n' > src/add.js
    printf 'import {test} from "node:test";import assert from "node:assert";\ntest("unrelated", () => assert.ok(1));\n' > tests/add.test.js
    git add -A && git commit -q -m "claim done" ;;
  vandal)
    printf '{"name":"x","type":"library","gates":{"types":null,"lint":null,"test":null,"a11y":null,"perf":null}}\n' > trellis.json
    git add -A && git commit -q -m "disable gates" ;;
esac
exit 0
