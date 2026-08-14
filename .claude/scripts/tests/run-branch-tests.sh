#!/usr/bin/env bash
# Tests resolving a spec id to its branch.
#
# Four scripts hardcoded `agent/${SPEC_ID}`, so a branch named agent/SPEC-024-revoke-an-invite-link —
# the shape a person types, because it says what the branch is — failed delivery with "no branch
# agent/SPEC-024". A message naming a branch nobody created, at the end of a finished build.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RESOLVE="$ROOT/.claude/scripts/spec-branch.sh"
FAILS=0

setup() {
  DIR="$(mktemp -d)"
  cd "$DIR" || exit 1
  git init -q -b main
  git config user.email t@t
  git config user.name t
  echo x > seed && git add -A && git commit -qm seed
}
teardown() { cd "$ROOT" || exit 1; rm -rf "$DIR"; }

check() {  # check <spec-id> <expected branch, or empty to expect failure> <label>
  local got status
  got="$("$RESOLVE" "$1" 2>/dev/null)"
  status=$?
  if [ -n "$2" ]; then
    if [ "$status" = "0" ] && [ "$got" = "$2" ]; then
      printf "  PASS  %-54s %s\n" "$3" "$got"
    else
      printf "  FAIL  %-54s got '%s' (exit %s), wanted '%s'\n" "$3" "$got" "$status" "$2"
      FAILS=$((FAILS + 1))
    fi
  elif [ "$status" != "0" ]; then
    printf "  PASS  %-54s refused\n" "$3"
  else
    printf "  FAIL  %-54s resolved to '%s', should have refused\n" "$3" "$got"
    FAILS=$((FAILS + 1))
  fi
}

# The message is captured before being searched rather than piped into grep. Under `pipefail` the
# pipeline takes the resolver's exit status, and a refusal exits non-zero by design — so a matching
# message read as a failing assertion.
says() {  # says <spec-id> <text the message must contain> <label>
  local message
  message="$("$RESOLVE" "$1" 2>&1 >/dev/null)"
  if printf '%s' "$message" | grep -q "$2"; then
    printf "  PASS  %-54s\n" "$3"
  else
    printf "  FAIL  %-54s message did not mention '%s'\n" "$3" "$2"
    FAILS=$((FAILS + 1))
  fi
}

echo "Resolving a spec id to its branch:"

setup
git checkout -qb agent/SPEC-024
check SPEC-024 "agent/SPEC-024" "the canonical form"
teardown

setup
git checkout -qb agent/SPEC-024-revoke-an-invite-link
check SPEC-024 "agent/SPEC-024-revoke-an-invite-link" "a descriptive suffix, which is what people type"
teardown

setup
# The suffix must start with a hyphen. Delivering SPEC-240's branch as SPEC-24's would be worse than
# any failure this file exists to prevent.
git checkout -qb agent/SPEC-240
check SPEC-24 "" "a longer id is not a suffix of a shorter one"
teardown

setup
git checkout -qb agent/SPEC-024-first
git checkout -q main
git checkout -qb agent/SPEC-024-second
check SPEC-024 "" "two candidate branches are refused rather than guessed"
says SPEC-024 "2 branches match" "and the refusal says how many"
teardown

setup
git checkout -qb agent/SPEC-001
check SPEC-024 "" "no branch at all"
says SPEC-024 "agent/SPEC-001" "and the refusal lists the agent branches that do exist"
teardown

setup
check SPEC-024 "" "no agent branches at all"
teardown

echo
if [ $FAILS -eq 0 ]; then
  echo "branch: all 8 cases correct"
else
  echo "$FAILS case(s) wrong"
fi
exit $FAILS
