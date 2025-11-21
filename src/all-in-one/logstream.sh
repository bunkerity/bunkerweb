#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/logging-utils.sh"

# Function to stream log file when it exists
stream_log() {
    local service_key="$1"
    local log_file="$2"
    local stream="$3"
    local prefix="$4"

    if hide_service_logs_match "$service_key"; then
        if [ "${CUSTOM_LOG_LEVEL:-}" = "debug" ] || [ "${LOG_LEVEL:-}" = "debug" ]; then
            echo "[LOGSTREAM] Suppressing ${service_key} logs via HIDE_SERVICE_LOGS"
        fi
        return 0
    fi

    # Wait for log file to be created
    while [ ! -f "$log_file" ]; do
      if [ "${CUSTOM_LOG_LEVEL:-}" = "debug" ] || [ "${LOG_LEVEL:-}" = "debug" ]; then
      echo "[LOGSTREAM] Waiting for $log_file to be created..."
      fi
      sleep 1
    done

    echo "[LOGSTREAM] Started streaming $log_file"

    # Use tail to follow the log file and add prefix
    if [ "$stream" == "stdout" ]; then
        exec tail -F "$log_file" | sed "s/^/${prefix}/"
    else
        exec tail -F "$log_file" | sed "s/^/${prefix}/" >&2
    fi
}

# Start streaming each log file in a separate background process
stream_log "nginx.access" "/var/log/bunkerweb/access.log" "stdout" "[NGINX.ACCESS] " &
stream_log "nginx.error" "/var/log/bunkerweb/error.log" "stderr" "[NGINX.ERROR] " &
stream_log "modsec" "/var/log/bunkerweb/modsec_audit.log" "stderr" "[MODSEC] " &

# Wait for all background processes
wait
