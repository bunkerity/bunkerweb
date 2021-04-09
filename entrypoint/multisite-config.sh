#!/bin/sh

# load default values
. /opt/entrypoint/defaults.sh

# load some functions
. /opt/entrypoint/utils.sh

if [ "$MULTISITE" = "yes" ] ; then
	servers=$(find /etc/nginx -name "server.conf" | cut -d '/' -f 4)
	for server in $servers ; do
		if [ "$server" = "server.conf" ] ; then
			continue
		fi
		SERVER_PREFIX="/etc/nginx/${server}/"
		if grep "/etc/letsencrypt/live" ${SERVER_PREFIX}https.conf > /dev/null && [ ! -f /etc/letsencrypt/live/${server}/fullchain.pem ] ; then
			domains=$(cat ${SERVER_PREFIX}server.conf | sed -nE 's/^.*server_name (.*);$/\1/p' | sed "s/ /,/g")
			/opt/scripts/certbot-new.sh "$domains" "$(cat ${SERVER_PREFIX}email-lets-encrypt.txt)"
		fi
		if grep "modsecurity.conf" ${SERVER_PREFIX}server.conf > /dev/null ; then
			modsec_custom=""
			if ls /modsec-confs/*.conf > /dev/null 2>&1 ; then
				modsec_custom="include /modsec-confs/*.conf\n"
			fi
			if ls /modsec-confs/${server}/*.conf > /dev/null 2>&1 ; then
				modsec_custom="${modsec_custom}include /modsec-confs/${server}/*.conf\n"
			fi
			replace_in_file "${SERVER_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_RULES%" "$modsec_custom"
			if grep "owasp/crs.conf" ${SERVER_PREFIX}modsecurity-rules.conf > /dev/null ; then
				modsec_crs_custom=""
				if ls /modsec-crs-confs/*.conf > /dev/null 2>&1 ; then
					modsec_crs_custom="include /modsec-crs-confs/*.conf\n"
				fi
				if ls /modsec-crs-confs/${server}/*.conf > /dev/null 2>&1 ; then
					modsec_crs_custom="${modsec_crs_custom}include /modsec-crs-confs/${server}/*.conf\n"
				fi
			fi
			replace_in_file "${SERVER_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_CRS%" "$modsec_crs_custom"
		fi
	done
fi
