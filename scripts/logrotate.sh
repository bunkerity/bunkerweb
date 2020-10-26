#!/bin/sh

logrotate -f /etc/logrotate.conf > /dev/null 2>&1

pkill -HUP rsyslogd

fail2ban-client flushlogs

if [ -f /tmp/nginx.pid ] ; then
        /usr/sbin/nginx -s reload
fi
