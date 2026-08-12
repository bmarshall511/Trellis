#!/usr/bin/env bash
# Updates the Trellis framework files in this project from upstream.
#
# This exists because the alternative was a hand-written list of files pasted into a prompt, and that
# list was wrong the first time it was used — it omitted .claude/lib/frontmatter.py, so the integrity
# check died with ModuleNotFoundError for anyone who followed it exactly.
#
# A hand-maintained list of "the files that make up Trellis" is the same mistake as every other
# enumeration in this codebase: right on the day it is written. So the list comes from
# .claude/framework-paths.json, which already exists and is already the authority on what Trellis owns.
#
# Your project's own files are never touched. Framework files are replaced wholesale, because you do
# not own them — if you have edited one, that is what --check will tell you before anything changes.
#
# Usage:
#   trellis-update.sh                 update from the default upstream
#   trellis-update.sh --check         report what would change, touch nothing
#   trellis-update.sh --ref <branch>  update from a branch or tag other than main
set -uo pipefail

UPSTREAM="${TRELLIS_UPSTREAM:-https://github.com/bmarshall511/Trellis.git}"
REF="main"
CHECK_ONLY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=true; shift ;;
    --ref) REF="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repository" >&2; exit 1; }
cd "$ROOT" || exit 1

die() { echo "trellis-update: $*" >&2; exit 1; }

[[ -f .claude/framework-paths.json ]] || die "no .claude/framework-paths.json — nothing declares which files are Trellis's"

if ! $CHECK_ONLY && [[ -n "$(git status --porcelain)" ]]; then
  die "working tree is dirty. Commit or stash first — this replaces framework files wholesale and you
should be able to see exactly what changed."
fi

TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

echo "Fetching $UPSTREAM ($REF)…"
git clone -q --depth 1 --branch "$REF" "$UPSTREAM" "$TEMP/upstream" 2>/dev/null \
  || die "could not fetch $UPSTREAM at $REF"

# The upstream copy is the authority on what it owns — a new framework directory added upstream would
# be invisible to this project's older manifest.
MANIFEST="$TEMP/upstream/.claude/framework-paths.json"
[[ -f "$MANIFEST" ]] || die "upstream has no framework-paths.json"

# `mapfile` is bash 4+. macOS ships bash 3.2 and always will — it went GPLv3 in 2007 — so every
# script here must run on it. A read loop is the portable equivalent.
OWNED=()
while IFS= read -r line; do
  [[ -n "$line" ]] && OWNED+=("$line")
done < <(python3 -c "
import json
print('\n'.join(json.load(open('$MANIFEST')).get('owned', [])))
")
[[ ${#OWNED[@]} -gt 0 ]] || die "upstream manifest lists no owned paths"

# trellis.json is listed as framework-owned because Trellis defines its format — but its CONTENTS are
# the project's. Replacing it would wipe the project's declaration.
KEEP=("trellis.json")

changed=(); added=(); removed=(); modified_locally=()
set +u  # empty arrays under bash 3.2

for path in "${OWNED[@]}"; do
  skip=false
  for keep in "${KEEP[@]}"; do [[ "$path" == "$keep" ]] && skip=true; done
  $skip && continue

  src="$TEMP/upstream/${path%/}"
  dst="${path%/}"

  if [[ ! -e "$src" ]]; then
    [[ -e "$dst" ]] && removed+=("$dst")
    continue
  fi

  if [[ ! -e "$dst" ]]; then
    added+=("$dst")
    $CHECK_ONLY || { mkdir -p "$(dirname "$dst")"; cp -R "$src" "$dst"; }
    continue
  fi

  if ! diff -rq "$src" "$dst" >/dev/null 2>&1; then
    changed+=("$dst")
    # Something you edited is about to be replaced. Worth saying so by name.
    if git log --oneline -1 -- "$dst" 2>/dev/null | grep -qv '^$'; then
      if ! git diff --quiet HEAD -- "$dst" 2>/dev/null; then
        modified_locally+=("$dst")
      fi
    fi
    $CHECK_ONLY || { rm -rf "$dst"; mkdir -p "$(dirname "$dst")"; cp -R "$src" "$dst"; }
  fi
done

report() {
  local label="$1"; shift
  [[ $# -eq 0 ]] && return
  echo
  echo "$label"
  printf '  %s\n' "$@"
}

# bash 3.2 treats an empty array expansion as unbound under `set -u`, so guard each one.
[[ ${#changed[@]} -gt 0 ]] && report "Updated:" "${changed[@]}"
[[ ${#added[@]} -gt 0 ]] && report "Added:" "${added[@]}"
[[ ${#removed[@]} -gt 0 ]] && report "Present here but gone upstream (left in place):" "${removed[@]}"

if [[ ${#modified_locally[@]} -gt 0 ]]; then
  report "⚠ You had uncommitted edits to these framework files:" "${modified_locally[@]}"
  echo "  They were overwritten. Recover with: git diff HEAD"
fi

if [[ ${#changed[@]} -eq 0 && ${#added[@]} -eq 0 ]]; then
  echo
  echo "Already up to date."
  exit 0
fi

if $CHECK_ONLY; then
  echo
  echo "Nothing changed — this was --check."
  exit 0
fi

# Executable bits do not survive every copy path, and a hook that is not executable fails silently.
find .claude .githooks stacks -name "*.sh" -o -name "*.py" 2>/dev/null | while read -r f; do
  case "$f" in
    */hooks/*|*/scripts/*|*/tests/*) chmod +x "$f" 2>/dev/null ;;
  esac
done

echo
echo "Verifying…"
FAILED=0
for check in ".claude/scripts/check-integrity.py" ".claude/hooks/tests/run.py" \
             ".claude/scripts/validate-config.py"; do
  if [[ -x "$check" ]]; then
    if "$check" >/dev/null 2>&1; then
      echo "  ✓ $(basename "$check")"
    else
      echo "  ✗ $(basename "$check") — run it directly to see why"
      FAILED=1
    fi
  fi
done

echo
if [[ $FAILED -eq 0 ]]; then
  echo "Updated. Review with: git diff"
else
  echo "Updated, but a check failed. Review before committing — git checkout . reverts everything."
  exit 1
fi
