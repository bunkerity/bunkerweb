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

    # Use tail to follow the log file and add prefix.
    # Strip C0 control characters (except tab `\011` and newline `\012`) plus DEL so an
    # adversarial access/error/modsec payload (URI, User-Agent, matched_data) can't inject
    # ANSI/CSI/OSC escape sequences into `docker logs` output and spoof other services' lines.
    # `tr` and `sed` write into a pipe, so libc block-buffers them at 4 KiB: without
    # line buffering on BOTH stages, a quiet stream (the NGINX error log carrying the
    # ModSecurity detail line of a single blocked request) never reaches `docker logs` until
    # 4 KiB of further traffic pushes it out.
    # `stdbuf -oL sed`, not `sed -u`: both flush per line, but `-u` also makes GNU sed read
    # its input one byte at a time — 300k lines measured at 3.9s with `-u` against 0.06s with
    # `-oL`, a cost paid on access.log exactly during a traffic spike.
    if [ "$stream" == "stdout" ]; then
        exec tail -F "$log_file" | stdbuf -oL tr -d '\000-\010\013-\037\177' | stdbuf -oL sed "s/^/${prefix}/"
    else
        exec tail -F "$log_file" | stdbuf -oL tr -d '\000-\010\013-\037\177' | stdbuf -oL sed "s/^/${prefix}/" >&2
    fi
}

# Start streaming each log file in a separate background process
stream_log "nginx.access" "/var/log/bunkerweb/access.log" "stdout" "[NGINX.ACCESS] " &
stream_log "nginx.error" "/var/log/bunkerweb/error.log" "stderr" "[NGINX.ERROR] " &
stream_log "modsec" "/var/log/bunkerweb/modsec_audit.log" "stderr" "[MODSEC] " &

# Wait for all background processes
wait
