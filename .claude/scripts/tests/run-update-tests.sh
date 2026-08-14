#!/usr/bin/env bash
# Tests the updater against a local upstream.
#
# It deleted .claude/launch.json on six consecutive updates in one project, while printing
# "(gone upstream, left in place)" about that very file. The report and the behaviour disagreed, and
# the loss was silent until a preview server failed to start. There was already a commit in that
# repo called "Restore .claude/launch.json, removed by the Trellis update".
#
# The cause was not the reporting. Framework directories were replaced wholesale — `rm -rf .claude`
# then copy — so anything of the project's own living inside one went with it. Trellis owns the
# framework files in .claude/, not the whole directory, and a project puts its own files there
# because that is where Claude Code looks for them.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
FAILS=0

# A minimal upstream and a project cloned from it, so the real script runs its real path.
setup() {
  SANDBOX="$(mktemp -d)"
  UPSTREAM="$SANDBOX/upstream"
  PROJECT="$SANDBOX/project"

  mkdir -p "$UPSTREAM/.claude/scripts" "$UPSTREAM/.claude/hooks" "$UPSTREAM/stacks/github"
  cp "$ROOT/.claude/scripts/trellis-update.sh" "$UPSTREAM/.claude/scripts/"
  cp "$ROOT/.claude/framework-paths.json" "$UPSTREAM/.claude/"
  echo "upstream hook v2" > "$UPSTREAM/.claude/hooks/some-hook.py"
  echo "upstream stack v2" > "$UPSTREAM/stacks/github/guard.json"
  echo '{"name":"x"}' > "$UPSTREAM/trellis.json"
  git -C "$UPSTREAM" init -q -b main
  git -C "$UPSTREAM" config user.email t@t
  git -C "$UPSTREAM" config user.name t
  git -C "$UPSTREAM" add -A >/dev/null
  git -C "$UPSTREAM" commit -qm upstream

  git clone -q "$UPSTREAM" "$PROJECT" 2>/dev/null
  cd "$PROJECT" || exit 1
  git config user.email t@t
  git config user.name t

  # Older content, so the framework files genuinely differ and the update has work to do.
  echo "old hook" > .claude/hooks/some-hook.py
  echo "old stack" > stacks/github/guard.json

  # The project's own files, living inside framework directories because that is where the tools
  # that read them look. Trellis does not own these and must not remove them.
  echo '{"configurations":[]}' > .claude/launch.json
  mkdir -p .claude/agents
  echo "project's own agent" > .claude/agents/house-style.md
  echo "project note" > stacks/NOTES.md

  git add -A >/dev/null
  git commit -qm "project files" >/dev/null
}
teardown() { cd "$ROOT" || exit 1; rm -rf "$SANDBOX"; }

survives() {  # survives <path> <label>
  if [ -f "$1" ]; then
    printf "  PASS  %-56s survived\n" "$2"
  else
    printf "  FAIL  %-56s DELETED\n" "$2"
    FAILS=$((FAILS + 1))
  fi
}

updated() {  # updated <path> <expected content> <label>
  local got; got="$(cat "$1" 2>/dev/null)"
  if [ "$got" = "$2" ]; then
    printf "  PASS  %-56s updated\n" "$3"
  else
    printf "  FAIL  %-56s is '%s', wanted '%s'\n" "$3" "$got" "$2"
    FAILS=$((FAILS + 1))
  fi
}

echo "Updating from upstream:"
setup
TRELLIS_UPSTREAM="$UPSTREAM" ./.claude/scripts/trellis-update.sh >"$SANDBOX/out.txt" 2>&1

updated .claude/hooks/some-hook.py "upstream hook v2" "a framework file is replaced"
updated stacks/github/guard.json "upstream stack v2" "a framework file inside stacks/ is replaced"
survives .claude/launch.json "the project's launch.json, inside .claude/"
survives .claude/agents/house-style.md "the project's own agent, inside .claude/"
survives stacks/NOTES.md "the project's own note, inside stacks/"

# The report has to match what happened. Saying "left in place" while deleting is worse than either
# outcome on its own, because it stops anyone believing the report.
if grep -q "launch.json" "$SANDBOX/out.txt" && [ -f .claude/launch.json ]; then
  printf "  PASS  %-56s report agrees with disk\n" "what it says it left, it left"
elif ! grep -q "launch.json" "$SANDBOX/out.txt" && [ -f .claude/launch.json ]; then
  printf "  PASS  %-56s untouched and unmentioned\n" "what it says it left, it left"
else
  printf "  FAIL  %-56s reported one thing and did another\n" "what it says it left, it left"
  FAILS=$((FAILS + 1))
fi
teardown

# --check must be exactly that. A dry run that deletes is the worst possible version of this bug.
echo
echo "Checking without applying:"
setup
BEFORE="$(find .claude stacks -type f | sort)"
TRELLIS_UPSTREAM="$UPSTREAM" ./.claude/scripts/trellis-update.sh --check >/dev/null 2>&1
AFTER="$(find .claude stacks -type f | sort)"
if [ "$BEFORE" = "$AFTER" ]; then
  printf "  PASS  %-56s nothing changed\n" "--check touches no files at all"
else
  printf "  FAIL  %-56s the file list changed\n" "--check touches no files at all"
  FAILS=$((FAILS + 1))
fi
updated .claude/hooks/some-hook.py "old hook" "and leaves the old content in place"
teardown

echo
if [ $FAILS -eq 0 ]; then
  echo "update: all 9 cases correct"
else
  echo "$FAILS case(s) wrong"
fi
exit $FAILS
