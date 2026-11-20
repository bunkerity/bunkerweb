#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration="${1^}"

log "RESTART" "ℹ️ " "Restarting BunkerWeb stack for integration \"$integration\" ..."

restart_stack
# shellcheck disable=SC2181
if [ $? -ne 0 ]; then
  log "RESTART" "❌" "Failed to restart BunkerWeb stack for integration \"$integration\""
  exit 1
fi

log "RESTART" "✅" "BunkerWeb stack restarted for integration \"$integration\""
