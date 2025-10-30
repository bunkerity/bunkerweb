#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=src/all-in-one/logging-utils.sh
. "${SCRIPT_DIR}/logging-utils.sh"

service_key="$1"
log_file="$2"
prefix="$3"
shift 3

if hide_service_logs_match "$service_key"; then
	exec "$@" 2>&1 | while IFS= read -r line; do echo "${prefix}${line}"; done | tee "$log_file" >/dev/null
else
	exec "$@" 2>&1 | while IFS= read -r line; do echo "${prefix}${line}"; done | tee "$log_file"
fi
