#!/usr/bin/env bash
# Trellis notification. Called at the end of every unattended run.
#
# Only BLOCKED and FAILED reach a phone. Successes are visible in the branch list and the morning
# digest — a channel that pings for good news is a channel you mute, and then it is not a channel.
#
# Configure by setting TRELLIS_NTFY_TOPIC (see ntfy.sh) or TRELLIS_NOTIFY_CMD.
# Message bodies carry ids and counts only, never content: a topic name is a bearer secret and
# nothing more, so anyone who learns it can read whatever you put in the body.
set -uo pipefail
OUTCOME="${1:-UNKNOWN}"; SPEC="${2:-?}"; REPORT="${3:-}"

case "$OUTCOME" in
  DONE) exit 0 ;;   # deliberately silent
esac

MESSAGE="$SPEC: $OUTCOME"
[[ -n "$REPORT" ]] && MESSAGE="$MESSAGE (see $REPORT)"

if [[ -n "${TRELLIS_NOTIFY_CMD:-}" ]]; then
  "$TRELLIS_NOTIFY_CMD" "$MESSAGE"
elif [[ -n "${TRELLIS_NTFY_TOPIC:-}" ]]; then
  curl -fsS -H "Title: Trellis" -H "Priority: default" \
       -d "$MESSAGE" "https://ntfy.sh/${TRELLIS_NTFY_TOPIC}" >/dev/null
elif command -v terminal-notifier >/dev/null 2>&1; then
  terminal-notifier -title "Trellis" -message "$MESSAGE"
elif command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"$MESSAGE\" with title \"Trellis\"" 2>/dev/null
else
  echo "notify: $MESSAGE"
fi
