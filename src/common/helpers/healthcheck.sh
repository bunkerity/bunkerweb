#!/bin/bash

if [ ! -f /var/run/bunkerweb/nginx.pid ] ; then
	exit 1
fi

check="$(curl -s -H "Host: healthcheck.bunkerweb.io" http://127.0.0.1:6000/healthz 2>&1)"
# shellcheck disable=SC2181
if [ $? -ne 0 ] || [ "$check" != "ok" ] ; then
	exit 1
fi

exit 0
