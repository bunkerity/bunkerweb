#!/bin/bash

# Default statuses to check
DEFAULT_STATUSES=("ok" "reloading")

# Parse optional argument for specific status
SPECIFIC_STATUS=""
if [ $# -gt 0 ]; then
	SPECIFIC_STATUS="$1"
fi

if [ ! -f /var/run/bunkerweb/nginx.pid ] ; then
	exit 1
fi

check="$(curl -s -H "Host: healthcheck.bunkerweb.io" http://127.0.0.1:9999/healthz 2>&1)"
# shellcheck disable=SC2181
if [ $? -ne 0 ]; then
	exit 1
fi

if [ -n "$SPECIFIC_STATUS" ]; then
	if [ "$check" != "$SPECIFIC_STATUS" ]; then
		exit 1
	fi
else
	if [[ ! " ${DEFAULT_STATUSES[*]} " =~ $check ]]; then
		exit 1
	fi
fi

exit 0
