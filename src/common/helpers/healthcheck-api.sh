#!/bin/bash

# API healthcheck: inspired by other service healthchecks

# Ensure API process is running
if [ ! -f /var/run/bunkerweb/api.pid ] ; then
	exit 1
fi

# Ensure service reported healthy
if [ ! -f /var/tmp/bunkerweb/api.healthy ] ; then
	exit 1
fi

exit 0
