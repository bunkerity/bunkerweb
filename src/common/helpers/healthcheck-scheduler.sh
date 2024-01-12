#!/bin/bash

if [ ! -f /var/run/bunkerweb/scheduler.pid ] ; then
	exit 1
fi

if [ ! -f /var/tmp/bunkerweb/scheduler.healthy ] ; then
	exit 1
fi

exit 0
