#!/usr/bin/env bash
# Mock repair agent. Stands in for `claude -p` when testing the CI repair loop.
#
# Makes a trivial, real commit so the loop's push and re-poll steps are genuinely exercised rather
# than skipped over.
set -uo pipefail
mkdir -p src
printf '// repaired at %s\n' "$(date +%s)" >> src/add.js
git add -A >/dev/null 2>&1
git commit -qm "fix: address CI failure" >/dev/null 2>&1
exit 0
