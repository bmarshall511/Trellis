#!/usr/bin/env bash
# Tests the integrity checker.
#
# It had no tests, and shipped a dangling skill reference while reporting "all references resolve".
# The cause was a regex that tried to parse sentence grammar: an optional group for a second name
# CONSUMED it without capturing, so one of two references was checked.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
FAILS=0

probe() {  # probe <expect detect|clean> <label> <command-file-body>
  local want="$1" label="$2" body="$3"
  local dir; dir="$(mktemp -d)"
  cp -R "$ROOT/.claude" "$dir/"; cp "$ROOT/trellis.schema.json" "$dir/" 2>/dev/null
  mkdir -p "$dir/docs/specs" "$dir/stacks"
  cp "$ROOT/README.md" "$ROOT/docs/specs/_template.md" "$dir/" 2>/dev/null
  cp "$ROOT/docs/specs/_template.md" "$dir/docs/specs/" 2>/dev/null
  cp "$ROOT/stacks/README.md" "$dir/stacks/" 2>/dev/null
  printf -- "---\ndescription: probe\n---\n\n%s\n" "$body" > "$dir/.claude/commands/probe.md"
  local out; out="$(cd "$dir" && ./.claude/scripts/check-integrity.py 2>&1)"
  local hit=clean
  grep -q "probe.md references" <<<"$out" && hit=detect
  if [[ "$hit" == "$want" ]]; then
    printf "  PASS  %-58s %s\n" "$label" "$hit"
  else
    printf "  FAIL  %-58s %s (wanted %s)\n" "$label" "$hit" "$want"; FAILS=$((FAILS+1))
  fi
  rm -rf "$dir"
}

echo "Integrity checker — dangling reference detection:"
probe clean  "single real skill"                      'Load the `testing` skill.'
probe detect "single fake skill"                      'Load the `nonexistent-thing` skill.'
probe detect "SECOND of two skills is fake"           'Load the `testing` and `nonexistent-thing` skills.'
probe detect "third of three is fake"                 'Load the `testing`, `security` and `made-up` skills.'
probe clean  "three real skills"                      'Load the `testing`, `security` and `clean-code` skills.'
probe detect "fake agent"                             'Use the `imaginary-auditor` agent.'
probe clean  "real agent"                             'Use the `coverage-auditor` agent.'
probe clean  "spec status in backticks is a value"    'Run the `spec-auditor` agent on anything `ready`.'
probe clean  "gate name in backticks is a value"      'The `a11y` gate must pass — see the `testing` skill.'
probe clean  "project type in backticks is a value"   'For a `library` project, load the `testing` skill.'
probe clean  "no skill or agent mentioned"            'Run `some-other-thing` to continue.'

echo
if [[ $FAILS -eq 0 ]]; then echo "integrity: all 11 cases correct"; else echo "$FAILS case(s) wrong"; fi
exit $FAILS
