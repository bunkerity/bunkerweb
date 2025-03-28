#!/bin/bash

# Function to stream log file when it exists
stream_log() {
    local log_file="$1"
    local stream="$2"
    local prefix="$3"

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
stream_log "/var/log/bunkerweb/access.log" "stdout" "[NGINX.ACCESS] " &
stream_log "/var/log/bunkerweb/error.log" "stderr" "[NGINX.ERROR] " &
stream_log "/var/log/bunkerweb/modsec_audit.log" "stderr" "[MODSEC] " &

# Wait for all background processes
wait
