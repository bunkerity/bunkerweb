#!/bin/bash

if [ ! -f /var/run/bunkerweb/ui.pid ] ; then
	exit 1
fi

if [ ! -f /var/tmp/bunkerweb/ui.healthy ] ; then
	exit 1
fi

exit 0
