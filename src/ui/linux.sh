#!/bin/sh

order="$1"
if [ "$order" != "reload" ] && [ "$order" != "start" ] && [ "$order" != "stop" ] && [ "$order" != "restart" ] ; then
	exit 1
fi

systemctl "$1" nginx

exit $?
