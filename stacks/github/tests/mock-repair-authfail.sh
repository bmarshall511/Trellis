#!/usr/bin/env bash
# Stands in for a repair run whose session has expired. Writes nothing and fixes nothing, which is
# exactly the failure that used to burn the whole repair budget in silence.
echo "OAuth session expired and could not be refreshed" >&2
exit 1
