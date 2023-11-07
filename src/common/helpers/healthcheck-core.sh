#!/bin/bash

if [ ! -f /var/run/bunkerweb/core.pid ] ; then
	exit 1
fi

if [ ! -f /var/tmp/bunkerweb/core.healthy ] ; then
	exit 1
fi

exit 0
