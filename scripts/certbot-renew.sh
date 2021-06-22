#!/bin/bash

# load some functions
. /opt/bunkerized-nginx/entrypoint/utils.sh

if [ "$(grep "^SWARM_MODE=yes$" /etc/nginx/global.env)" != "" ] && [ -f /usr/sbin/nginx ] ; then
	exit 0
fi

if [ "$(has_value AUTO_LETS_ENCRYPT yes)" = "" ] ; then
	exit 0
fi

# ask new certificates if needed
certbot renew --deploy-hook /opt/bunkerized-nginx/scripts/certbot-renew-hook.sh

if [ "$?" -eq 0 ] ; then
	job_log "[CERTBOT] renew operation done"
else
	job_log "[CERTBOT] renew operation failed"
fi
