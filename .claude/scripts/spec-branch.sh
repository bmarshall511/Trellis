#!/usr/bin/env bash
# Resolve a spec id to the branch holding its work. Prints the branch name, or explains why not.
#
# Four scripts hardcoded `agent/${SPEC_ID}` and the commands documented that exact form, so
# `agent/SPEC-024-revoke-an-invite-link` — the shape a person naturally types, because it says what
# the branch is — failed delivery with "no branch agent/SPEC-024". A message naming a branch you
# never created, about work sitting right there on one you did.
#
# Both forms resolve now. The canonical form is still `agent/<spec-id>`, which is what run-spec.sh
# creates; the descriptive suffix is accepted because rejecting it bought nothing and cost a
# confusing failure at the end of a build.
#
# The suffix must start with a hyphen. `agent/SPEC-24*` would otherwise match `agent/SPEC-240`, and
# delivering the wrong spec's branch is a worse outcome than any of this.
set -uo pipefail

SPEC_ID="${1:-}"
if [ -z "$SPEC_ID" ]; then
  echo "usage: spec-branch.sh <spec-id>" >&2
  exit 2
fi

MATCHES=()
while IFS= read -r ref; do
  [ -n "$ref" ] && MATCHES+=("$ref")
done < <(git for-each-ref --format='%(refname:short)' \
           "refs/heads/agent/${SPEC_ID}" "refs/heads/agent/${SPEC_ID}-*" 2>/dev/null)

set +u  # bash 3.2 treats an empty array expansion as unbound
COUNT=${#MATCHES[@]}

if [ "$COUNT" -eq 1 ]; then
  echo "${MATCHES[0]}"
  exit 0
fi

if [ "$COUNT" -eq 0 ]; then
  {
    echo "no branch for ${SPEC_ID}."
    echo "Expected agent/${SPEC_ID}, or agent/${SPEC_ID}-<something>."
    EXISTING="$(git for-each-ref --format='  %(refname:short)' 'refs/heads/agent/*' 2>/dev/null)"
    if [ -n "$EXISTING" ]; then
      echo "Agent branches that do exist:"
      echo "$EXISTING"
    fi
  } >&2
  exit 1
fi

# Ambiguity is the one case that must not be guessed: picking either could deliver work nobody
# reviewed under the name of work somebody did.
{
  echo "${COUNT} branches match ${SPEC_ID}, so which one holds the work is not knowable here:"
  printf '  %s\n' "${MATCHES[@]}"
  echo "Delete or rename the ones that are not the work being delivered."
} >&2
exit 1
