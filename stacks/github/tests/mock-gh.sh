#!/usr/bin/env bash
# Mock gh for testing delivery. Behaviour chosen by MOCK_GH:
#   green         checks pass first time, merge succeeds
#   red           checks always fail (exercises the repair budget)
#   red-then-green  fails once, then passes (exercises a successful repair)
#   pending       checks never finish (exercises the timeout)
#   nochecks      repository has no checks configured
#   mergerefused  checks pass but the merge is refused
#   notmerged     merge command succeeds but the PR never shows as merged
#   labelfail     repository has no labels and cannot create them
set -uo pipefail
BEHAVIOUR="${MOCK_GH:-green}"
COUNTER="${MOCK_GH_STATE:-/tmp/trellis-mock-gh-count}"

case "$1 ${2:-}" in
  "label create")
    # A repository with no labels. `labelfail` simulates one where creation is not permitted either,
    # which is what a fork or a restricted token looks like.
    [ "$BEHAVIOUR" = "labelfail" ] && exit 1
    exit 0 ;;

  "pr create")
    # gh refuses outright when a label does not exist. That killed the first delivery in a fresh
    # repository, after the branch had already been pushed.
    if [ "$BEHAVIOUR" = "labelfail" ]; then
      case "$*" in
        *--label*) echo "could not add label: 'agent-run' not found"; exit 1 ;;
      esac
    fi
    echo "https://github.com/test/repo/pull/1"; exit 0 ;;

  "pr checks")
    case "$BEHAVIOUR" in
      green|mergerefused|notmerged|labelfail) echo '[{"state":"SUCCESS","name":"verify"}]' ;;
      red)      echo '[{"state":"FAILURE","name":"verify"}]' ;;
      pending)  echo '[{"state":"IN_PROGRESS","name":"verify"}]' ;;
      nochecks) echo '[]' ;;
      red-then-green)
        n=$(cat "$COUNTER" 2>/dev/null || echo 0)
        echo $((n + 1)) > "$COUNTER"
        if [ "$n" -eq 0 ]; then echo '[{"state":"FAILURE","name":"verify"}]'
        else echo '[{"state":"SUCCESS","name":"verify"}]'; fi ;;
    esac
    exit 0 ;;

  "run view") echo "FAIL tests/add.test.js: expected 2, got 3"; exit 0 ;;

  "pr merge")
    [ "$BEHAVIOUR" = "mergerefused" ] && exit 1
    [ "$BEHAVIOUR" = "labelfail" ] && { git push -q origin "agent/SPEC-001:main" 2>/dev/null; exit 0; }
    # Actually land the merge in the test remote, so the script's fast-forward step is genuinely
    # exercised rather than skipped over. A mock that returns success without changing anything
    # would let a broken sync pass.
    [ "$BEHAVIOUR" = "notmerged" ] || git push -q origin "agent/SPEC-001:main" 2>/dev/null
    exit 0 ;;

  "pr view")
    [ "$BEHAVIOUR" = "notmerged" ] && { echo "OPEN"; exit 0; }
    echo "MERGED"; exit 0 ;;
esac
exit 0
