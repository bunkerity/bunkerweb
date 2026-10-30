#!/bin/bash

# Parse optional argument for specific status
SPECIFIC_STATUS=""
if [ $# -gt 0 ]; then
	SPECIFIC_STATUS="$1"
fi

if [ ! -f /var/run/bunkerweb/nginx.pid ] ; then
	exit 1
fi

check="$(curl -s -H "Host: healthcheck.bunkerweb.io" http://127.0.0.1:6000/healthz 2>&1)"
# shellcheck disable=SC2181
if [ $? -ne 0 ]; then
	exit 1
fi

if [ -n "$SPECIFIC_STATUS" ]; then
	[ "$check" = "$SPECIFIC_STATUS" ] || exit 1
	exit 0
fi

# An instance that is loading is still serving, so flipping it to unhealthy there pulls it
# out of the k8s endpoints for a state it leaves on its own. Matched exactly : a substring
# test accepted anything the status list happened to contain.
case "$check" in
	ok | loading) exit 0 ;;
	*) exit 1 ;;
esac
