#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration="${1^}"
type="${2:-}"
full_cleanup="${3:-}"

log "STOP" "ℹ️ " "Cleaning up BunkerWeb stack for integration \"$integration\" with type \"$type\"..."

exit_code=0
if [ -n "$full_cleanup" ]; then
  log "STOP" "ℹ️ " "Full cleanup requested"
  exit_code=1
fi

cleanup_stack "$exit_code"
# shellcheck disable=SC2181
if [ $? -ne 0 ]; then
  log "STOP" "❌" "Failed to clean up BunkerWeb stack for integration \"$integration\" with type \"$type\""
  exit 1
fi

log "STOP" "✅" "BunkerWeb stack cleaned up for integration \"$integration\" with type \"$type\""
