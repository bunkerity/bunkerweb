#!/bin/sh

# load some functions
. /opt/scripts/utils.sh

# ask new certificates if needed
certbot renew --deploy-hook /opt/scripts/certbot-renew-hook.sh

if [ "$?" -eq 0 ] ; then
	job_log "[CERTBOT] renew operation done"
else
	job_log "[CERTBOT] renew operation failed"
fi
