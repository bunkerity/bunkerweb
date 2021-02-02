#!/bin/sh

# load some functions
. /opt/scripts/utils.sh

logrotate -f /etc/logrotate.conf > /dev/null 2>&1

pkill -HUP rsyslogd

fail2ban-client flushlogs

if [ -f /tmp/nginx.pid ] ; then
	/usr/sbin/nginx -s reload > /dev/null 2>&1
	if [ "$?" -eq 0 ] ; then
		job_log "[NGINX] successfull nginx reload after logrotate"
	else
		job_log "[NGINX] failed nginx reload after logrotate"
	fi
fi
