#!/bin/bash

# load default values
. /opt/entrypoint/defaults.sh

# load some functions
. /opt/entrypoint/utils.sh

# fail2ban setup
if [ "$(has_value USE_FAIL2BAN yes)" != "" ] ; then
	cp /opt/fail2ban/nginx-action.local /etc/fail2ban/action.d/nginx-action.local
	cp /opt/fail2ban/nginx-filter.local /etc/fail2ban/filter.d/nginx-filter.local
	cp /opt/fail2ban/nginx-jail.local /etc/fail2ban/jail.d/nginx-jail.local
	replace_in_file "/etc/fail2ban/jail.d/nginx-jail.local" "%FAIL2BAN_BANTIME%" "$FAIL2BAN_BANTIME"
	replace_in_file "/etc/fail2ban/jail.d/nginx-jail.local" "%FAIL2BAN_FINDTIME%" "$FAIL2BAN_FINDTIME"
	replace_in_file "/etc/fail2ban/jail.d/nginx-jail.local" "%FAIL2BAN_MAXRETRY%" "$FAIL2BAN_MAXRETRY"
	replace_in_file "/etc/fail2ban/jail.d/nginx-jail.local" "%FAIL2BAN_IGNOREIP%" "$FAIL2BAN_IGNOREIP"
	replace_in_file "/etc/fail2ban/filter.d/nginx-filter.local" "%FAIL2BAN_STATUS_CODES%" "$FAIL2BAN_STATUS_CODES"
fi
