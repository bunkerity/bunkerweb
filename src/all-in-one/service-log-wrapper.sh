#!/bin/bash
#
# Supervisor child wrapper for BunkerWeb all-in-one Python services.
#
# Responsibilities:
#   1. Prefix each line of the service's merged stdout+stderr with a "[SERVICE] "
#      tag so `docker logs bunkerweb-aio` stays readable when multiple services
#      share a single stream.
#   2. Honor HIDE_SERVICE_LOGS: when the service matches the configured list,
#      redirect its output to /dev/null so it doesn't reach `docker logs`.
#
# Intentionally writes no files. Log retention on the host is the responsibility
# of the container runtime's logging driver (`docker logs`, journald, etc.). On
# Linux installs, file-based logging is rotated externally by logrotate.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "${SCRIPT_DIR}/logging-utils.sh"

service_key="$1"
prefix="$2"
shift 2

if hide_service_logs_match "$service_key"; then
	exec "$@" >/dev/null 2>&1
else
	# Strip C0 control characters (except tab `\011` and newline `\012`) plus DEL so an
	# adversarial log payload can't inject ANSI/CSI/OSC escape sequences into
	# `docker logs` output and spoof other services' lines.
	exec "$@" 2>&1 | tr -d '\000-\010\013-\037\177' | while IFS= read -r line; do printf '%s%s\n' "${prefix}" "${line}"; done
fi
