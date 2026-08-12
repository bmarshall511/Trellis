#!/usr/bin/env bash
# Tests the mockup approval lock.
#
# The gate's whole value is that approval cannot drift from what was approved. Every case here is a
# way that could silently stop being true — and one of them (a brand asset swapped underneath an
# approved mockup) was a real defect, reported from a project using Trellis.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
FAILS=0

setup() {
  DIR="$(mktemp -d)"; cp -R "$ROOT/.claude" "$DIR/"; cd "$DIR" || exit 1
  git init -q; git config user.email t@t; git config user.name t
  mkdir -p docs/mockups/_foundations/brand docs/mockups/SPEC-001
  echo ':root{--accent:#6f3c0c}'                 > docs/mockups/_foundations/tokens.css
  echo '<svg><circle fill="#6f3c0c"/></svg>'     > docs/mockups/_foundations/brand/logo.svg
  echo '<html>style tile</html>'                 > docs/mockups/_foundations/index.html
  echo 'png-bytes-v1'                            > docs/mockups/_foundations/index.png
  echo '<html><img src="../_foundations/brand/logo.svg"><h1>Hi</h1></html>' > docs/mockups/SPEC-001/page.html
  ./.claude/scripts/mockup.py approve SPEC-001 >/dev/null
}
teardown() { cd "$ROOT" || exit 1; rm -rf "$DIR"; }

check() {  # check <want APPROVED|STALE|UNAPPROVED> <label>
  local want="$1" label="$2" got
  got="$(./.claude/scripts/mockup.py verify SPEC-001 2>&1 | head -1 | awk '{print $1}')"
  if [[ "$got" == "$want" ]]; then
    printf "  PASS  %-52s %s\n" "$label" "$got"
  else
    printf "  FAIL  %-52s %s (wanted %s)\n" "$label" "$got" "$want"; FAILS=$((FAILS+1))
  fi
}

echo "Mockup approval lock:"

setup; check APPROVED "freshly approved"; teardown
setup; echo 'edited' >> docs/mockups/SPEC-001/page.html; check STALE "mockup edited after approval"; teardown
setup; echo ':root{--accent:#111}' > docs/mockups/_foundations/tokens.css
       check STALE "design token changed"; teardown
setup; echo '<svg><circle fill="#f00"/></svg>' > docs/mockups/_foundations/brand/logo.svg
       check STALE "brand asset swapped underneath"; teardown
setup; mkdir -p docs/mockups/_foundations/icons; echo '<svg/>' > docs/mockups/_foundations/icons/x.svg
       check STALE "foundations directory nobody anticipated"; teardown
setup; echo 'png-bytes-v2' > docs/mockups/_foundations/index.png
       check APPROVED "foundations screenshot regenerated"; teardown
setup; rm -f docs/mockups/SPEC-001/approval.json; check UNAPPROVED "approval removed"; teardown
setup; mv docs/mockups/SPEC-001/page.html docs/mockups/SPEC-001/renamed.html
       check STALE "mockup renamed, contents identical"; teardown

echo
if [[ $FAILS -eq 0 ]]; then echo "mockup: all 8 cases correct"; else echo "$FAILS case(s) wrong"; fi
exit $FAILS
