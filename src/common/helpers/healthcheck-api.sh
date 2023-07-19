#!/bin/bash

if [ ! -f /var/run/bunkerweb/api.pid ] ; then
	exit 1
fi

if [ ! -f /var/tmp/bunkerweb/api.healthy ] ; then
	exit 1
fi

exit 0