#!/bin/bash

if [ -f /opt/bunkerweb/tmp/nginx-temp.pid ] ; then
	exit 1
fi

if [ ! -f /opt/bunkerweb/tmp/nginx.pid ] ; then
	exit 1
fi

check="$(curl -s -H "Host: healthcheck.bunkerweb.io" http://127.0.0.1:6000/healthz 2>&1)"
if [ $? -ne 0 ] || [ "$check" != "ok" ] ; then
	exit 1
fi

exit 0
