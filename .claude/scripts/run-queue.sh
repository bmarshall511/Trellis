#!/usr/bin/env bash
# Trellis overnight queue.
#
# Runs ready specs in dependency order and HALTS on the first that blocks or fails.
#
# Halting rather than skipping is deliberate: you wake to one thing to decide, not a pile of
# half-built branches whose interactions you now have to reason about. And if spec 3 turned out to be
# ambiguous, specs 4 and 5 — written the same evening, by the same person, in the same mood — probably
# are too.
#
# Usage: run-queue.sh [--limit N] [--dry-run]
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; cd "$ROOT" || exit 1

LIMIT=99; DRY=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --limit) LIMIT="$2"; shift 2 ;;
    --dry-run) DRY="--dry-run"; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

# mapfile is bash 4+; macOS ships bash 3.2 and always will (it went GPLv3 in 2007).
QUEUE=()
while IFS= read -r _line; do
  [ -n "$_line" ] && QUEUE+=("$_line")
done < <(python3 - <<'PY'
import os, re
d = "docs/specs"
specs = {}
for name in sorted(os.listdir(d)):
    if not name.endswith(".md") or name.startswith("_"):
        continue
    text = open(os.path.join(d, name)).read()
    fm = dict(re.findall(r"^(\w+):\s*(.*)$", text.split("---", 2)[1], re.M)) if text.startswith("---") else {}
    specs[fm.get("id", name)] = (fm.get("status", ""), fm.get("depends", "[]"))
ready = []
for sid, (status, depends) in specs.items():
    if status != "ready":
        continue
    deps = [x.strip().strip("'\"") for x in depends.strip("[]").split(",") if x.strip()]
    if all(specs.get(x, ("", ""))[0] == "done" for x in deps):
        ready.append(sid)
print("\n".join(sorted(ready)))
PY
)

if [[ ${#QUEUE[@]} -eq 0 || -z "${QUEUE[0]:-}" ]]; then
  echo "Nothing ready to build."
  exit 0
fi

echo "Queue: ${QUEUE[*]}"
echo "Limit: $LIMIT · halt on first blocked or failed"
echo

STARTED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
declare -a RESULTS=()
COUNT=0

for SPEC in "${QUEUE[@]}"; do
  [[ $COUNT -ge $LIMIT ]] && { echo "Limit reached."; break; }
  COUNT=$((COUNT + 1))
  echo "── $SPEC ──"
  .claude/scripts/run-spec.sh "$SPEC" $DRY
  CODE=$?
  case $CODE in
    0)
      # Merge only if the project has opted in. merge-run.sh re-checks everything itself; it does not
      # trust this script's judgement that the run went well, or the run's judgement either.
      if .claude/scripts/merge-run.sh "$SPEC" >/dev/null 2>&1; then
        RESULTS+=("$SPEC DONE, merged")
      elif grep -q '"mayMerge": *true' trellis.json 2>/dev/null; then
        RESULTS+=("$SPEC DONE, held — see .claude/scripts/merge-run.sh $SPEC")
      else
        RESULTS+=("$SPEC DONE")
      fi
      ;;
    2) RESULTS+=("$SPEC BLOCKED"); echo; echo "Halting: $SPEC blocked."; break ;;
    *) RESULTS+=("$SPEC FAILED");  echo; echo "Halting: $SPEC failed.";  break ;;
  esac
  echo
done

DIGEST="docs/runs/DIGEST.md"
mkdir -p docs/runs
{
  echo "# Overnight digest"
  echo
  echo "Started $STARTED, finished $(date -u +%Y-%m-%dT%H:%M:%SZ)."
  echo
  for line in "${RESULTS[@]}"; do echo "- $line"; done
  echo
  echo "Reports in \`docs/runs/\`. Branches are local and unpushed — review, then publish what you want."
} > "$DIGEST"

echo "── digest ──"
cat "$DIGEST"
.claude/scripts/notify.sh "DIGEST" "overnight" "$DIGEST" >/dev/null 2>&1 || true
