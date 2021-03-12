#!/bin/bash

# load default values
. /opt/entrypoint/defaults.sh

# load some functions
. /opt/entrypoint/utils.sh

# clamav setup
if [ "$(has_value USE_CLAMAV_UPLOAD yes)" != "" ] || [ "$USE_CLAMAV_SCAN" = "yes" ] ; then
	echo "[*] Updating clamav (in background) ..."
	freshclam > /dev/null 2>&1 &
	echo "$CLAMAV_UPDATE_CRON /usr/bin/freshclam > /dev/null 2>&1" >> /etc/crontabs/root
fi
if [ "$USE_CLAMAV_SCAN" = "yes" ] ; then
	if [ "$USE_CLAMAV_SCAN_REMOVE" = "yes" ] ; then
        	echo "$USE_CLAMAV_SCAN_CRON /usr/bin/clamscan -r -i --no-summary --remove / >> /var/log/clamav.log 2>&1" >> /etc/crontabs/root
        else
		echo "$USE_CLAMAV_SCAN_CRON /usr/bin/clamscan -r -i --no-summary / >> /var/log/clamav.log 2>&1" >> /etc/crontabs/root
        fi
fi
