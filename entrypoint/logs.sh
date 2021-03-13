#!/bin/bash

# load default values
. /opt/entrypoint/defaults.sh

# load some functions
. /opt/entrypoint/utils.sh

# copy stub confs
cat /opt/logs/rsyslog.conf > /etc/rsyslog.conf
cat /opt/logs/logrotate.conf > /etc/logrotate.conf

# create empty logs
touch /var/log/access.log
touch /var/log/error.log
touch /var/log/jobs.log

# setup logrotate
replace_in_file "/etc/logrotate.conf" "%LOGROTATE_MAXAGE%" "$LOGROTATE_MAXAGE"
replace_in_file "/etc/logrotate.conf" "%LOGROTATE_MINSIZE%" "$LOGROTATE_MINSIZE"
echo "$LOGROTATE_CRON /opt/scripts/logrotate.sh > /dev/null 2>&1" >> /etc/crontabs/nginx
