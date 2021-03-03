#!/bin/bash

# load default values
. /opt/entrypoint/defaults.sh

# load some functions
. /opt/entrypoint/utils.sh

# copy stub confs
cp /opt/logs/rsyslog.conf /etc/rsyslog.conf
cp /opt/logs/logrotate.conf /etc/logrotate.conf
cp -r /opt/lua/* /usr/local/lib/lua
cp /opt/confs/global/* /etc/nginx/

# remove cron jobs
echo "" > /etc/crontabs/root

# install additional modules if needed
if [ "$ADDITIONAL_MODULES" != "" ] ; then
	apk add $ADDITIONAL_MODULES
fi

# start nginx with temp conf for let's encrypt challenges
if [ "$(has_value AUTO_LETS_ENCRYPT yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx-temp.conf" "%HTTP_PORT%" "$HTTP_PORT"
	nginx -c /etc/nginx/nginx-temp.conf
fi

# include server block(s)
if [ "$MULTISITE" = "yes" ] ; then
	includes=""
	for server in $SERVER_NAME ; do
		includes="${includes}include /etc/nginx/${server}/server.conf;\n"
	done
	replace_in_file "/etc/nginx/nginx.conf" "%INCLUDE_SERVER%" "$includes"
else
	replace_in_file "/etc/nginx/nginx.conf" "%INCLUDE_SERVER%" "include /etc/nginx/server.conf;"
fi

# setup default server block if multisite
if [ "$MULTISITE" = "yes" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%MULTISITE_DEFAULT_SERVER%" "include /etc/nginx/multisite-default-server.conf;"
	if [ "$(has_value LISTEN_HTTP yes)" != "" ] ; then
		replace_in_file "/etc/nginx/multisite-default-server.conf" "%LISTEN_HTTP%" "listen 0.0.0.0:${HTTP_PORT} default_server;"
	else
		replace_in_file "/etc/nginx/multisite-default-server.conf" "%LISTEN_HTTP%" ""
	fi
	if [ "$(has_value AUTO_LETS_ENCRYPT yes)" != "" ] || [ "$(has_value USE_CUSTOM_HTTPS yes)" != "" ] || [ "$(has_value GENERATE_SELF_SIGNED_SSL yes)" != "" ] ; then
		replace_in_file "/etc/nginx/multisite-default-server.conf" "%USE_HTTPS%" "include /etc/nginx/multisite-default-server-https.conf;"
		replace_in_file "/etc/nginx/multisite-default-server-https.conf" "%HTTPS_PORT%" "$HTTPS_PORT"
		if [ "$(has_value HTTP2 yes)" != "" ] ; then
			replace_in_file "/etc/nginx/multisite-default-server-https.conf" "%HTTP2%" "http2"
		else
			replace_in_file "/etc/nginx/multisite-default-server-https.conf" "%HTTP2%" ""
		fi
		replace_in_file "/etc/nginx/multisite-default-server-https.conf" "%HTTPS_PROTOCOLS%" "$HTTPS_PROTOCOLS"
		if [ "$(echo $HTTPS_PROTOCOLS | grep TLSv1.2)" != "" ] ; then
			replace_in_file "/etc/nginx/multisite-default-server-https.conf" "%SSL_DHPARAM%" "ssl_dhparam /etc/nginx/dhparam;"
			replace_in_file "/etc/nginx/multisite-default-server-https.conf" "%SSL_CIPHERS%" "ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;"
		else
			replace_in_file "/etc/nginx/multisite-default-server-https.conf" "%SSL_DHPARAM%" ""
			replace_in_file "/etc/nginx/multisite-default-server-https.conf" "%SSL_CIPHERS%" ""
		fi
		openssl req -nodes -x509 -newkey rsa:4096 -keyout /etc/nginx/default-key.pem -out /etc/nginx/default-cert.pem -days $SELF_SIGNED_SSL_EXPIRY -subj "/C=$SELF_SIGNED_SSL_COUNTRY/ST=$SELF_SIGNED_SSL_STATE/L=$SELF_SIGNED_SSL_CITY/O=$SELF_SIGNED_SSL_ORG/OU=$SELF_SIGNED_SSL_OU/CN=$SELF_SIGNED_SSL_CN"
		if [ "$(has_value AUTO_LETS_ENCRYPT yes)" != "" ] ; then
			replace_in_file "/etc/nginx/multisite-default-server-https.conf" "%LETS_ENCRYPT_WEBROOT%" "include /etc/nginx/multisite-default-server-lets-encrypt-webroot.conf;"
		else
			replace_in_file "/etc/nginx/multisite-default-server-https.conf" "%LETS_ENCRYPT_WEBROOT%" ""
		fi
	else
		replace_in_file "/etc/nginx/multisite-default-server.conf" "%USE_HTTPS%" ""
	fi
	if [ "$DISABLE_DEFAULT_SERVER" = "yes" ] ; then
		replace_in_file "/etc/nginx/multisite-default-server.conf" "%MULTISITE_DISABLE_DEFAULT_SERVER%" "include /etc/nginx/multisite-disable-default-server.conf;"
	else
		replace_in_file "/etc/nginx/multisite-default-server.conf" "%MULTISITE_DISABLE_DEFAULT_SERVER%" ""
	fi
else
	replace_in_file "/etc/nginx/nginx.conf" "%MULTISITE_DEFAULT_SERVER%" ""
fi

# custom log format
replace_in_file "/etc/nginx/nginx.conf" "%LOG_FORMAT%" "$LOG_FORMAT"

# proxy_cache zone
if [ "$(has_value USE_PROXY_CACHE yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%PROXY_CACHE_PATH%" "proxy_cache_path /tmp/proxy_cache keys_zone=proxycache:${PROXY_CACHE_PATH_ZONE_SIZE} ${PROXY_CACHE_PATH_PARAMS};"
else
	replace_in_file "/etc/nginx/nginx.conf" "%PROXY_CACHE_PATH%" ""
fi

# let's encrypt setup
if [ "$AUTO_LETS_ENCRYPT" = "yes" ] ; then
	if [ "$MULTISITE" = "no" ] ; then
		FIRST_SERVER_NAME=$(echo "$SERVER_NAME" | cut -d " " -f 1)
		DOMAINS_LETS_ENCRYPT=$(echo "$SERVER_NAME" | sed "s/ /,/g")
		EMAIL_LETS_ENCRYPT="${EMAIL_LETS_ENCRYPT-contact@$FIRST_SERVER_NAME}"
		if [ ! -f /etc/letsencrypt/live/${FIRST_SERVER_NAME}/fullchain.pem ] ; then
			echo "[*] Performing Let's Encrypt challenge for $SERVER_NAME ..."
			/opt/scripts/certbot-new.sh "$DOMAINS_LETS_ENCRYPT" "$EMAIL_LETS_ENCRYPT"
		fi
	fi
	echo "$AUTO_LETS_ENCRYPT_CRON /opt/scripts/certbot-renew.sh > /dev/null 2>&1" >> /etc/crontabs/root
fi

# self-signed certificate
if [ "$GENERATE_SELF_SIGNED_SSL" = "yes" ] ; then
	mkdir /etc/nginx/self-signed-ssl/
        openssl req -nodes -x509 -newkey rsa:4096 -keyout /etc/nginx/self-signed-ssl/key.pem -out /etc/nginx/self-signed-ssl/cert.pem -days $SELF_SIGNED_SSL_EXPIRY -subj "/C=$SELF_SIGNED_SSL_COUNTRY/ST=$SELF_SIGNED_SSL_STATE/L=$SELF_SIGNED_SSL_CITY/O=$SELF_SIGNED_SSL_ORG/OU=$SELF_SIGNED_SSL_OU/CN=$SELF_SIGNED_SSL_CN"
fi

# country ban/whitelist
if [ "$BLACKLIST_COUNTRY" != "" ] || [ "$WHITELIST_COUNTRY" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%USE_COUNTRY%" "include /etc/nginx/geoip.conf;"
	if [ "$WHITELIST_COUNTRY" != "" ] ; then
		replace_in_file "/etc/nginx/geoip.conf" "%DEFAULT%" "no"
		replace_in_file "/etc/nginx/geoip.conf" "%COUNTRY%" "$(echo $WHITELIST_COUNTRY | sed 's/ / yes;\\n/g') yes;"
	else
		replace_in_file "/etc/nginx/geoip.conf" "%DEFAULT%" "yes"
		replace_in_file "/etc/nginx/geoip.conf" "%COUNTRY%" "$(echo $BLACKLIST_COUNTRY | sed 's/ / no;\\n/g') no;"
	fi
	echo "$GEOIP_CRON /opt/scripts/geoip.sh" >> /etc/crontabs/root
	if [ -f "/cache/geoip.mmdb" ] ; then
		echo "[*] Copying cached geoip.mmdb ..."
		cp /cache/geoip.mmdb /etc/nginx/geoip.mmdb
	else
		echo "[*] Downloading GeoIP database (in background) ..."
		/opt/scripts/geoip.sh &
	fi
else
	replace_in_file "/etc/nginx/nginx.conf" "%USE_COUNTRY%" ""
fi

# block bad UA
if [ "$(has_value BLOCK_USER_AGENT yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_USER_AGENT%" "include /etc/nginx/map-user-agent.conf;"
	echo "$BLOCK_USER_AGENT_CRON /opt/scripts/user-agents.sh" >> /etc/crontabs/root
	if [ -f "/cache/map-user-agent.conf" ] ; then
		echo "[*] Copying cached map-user-agent.conf ..."
		cp /cache/map-user-agent.conf /etc/nginx/map-user-agent.conf
	else
		echo "[*] Downloading bad user-agent list (in background) ..."
		/opt/scripts/user-agents.sh &
	fi
else
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_USER_AGENT%" ""
fi

# block bad refferer
if [ "$(has_value BLOCK_REFERRER yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_REFERRER%" "include /etc/nginx/map-referrer.conf;"
	echo "$BLOCK_REFERRER_CRON /opt/scripts/referrers.sh" >> /etc/crontabs/root
	if [ -f "/cache/map-referrer.conf" ] ; then
		echo "[*] Copying cached map-referrer.conf ..."
		cp /cache/map-referrer.conf /etc/nginx/map-referrer.conf
	else
		echo "[*] Downloading bad referrer list (in background) ..."
		/opt/scripts/referrers.sh &
	fi
else
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_REFERRER%" ""
fi

# block TOR exit nodes
if [ "$(has_value BLOCK_TOR_EXIT_NODE yes)" != "" ] ; then
	echo "$BLOCK_TOR_EXIT_NODE_CRON /opt/scripts/exit-nodes.sh" >> /etc/crontabs/root
	if [ -f "/cache/block-tor-exit-node.conf" ] ; then
		echo "[*] Copying cached block-tor-exit-node.conf ..."
		cp /cache/block-tor-exit-node.conf /etc/nginx/block-tor-exit-node.conf
	else
		echo "[*] Downloading tor exit nodes list (in background) ..."
		/opt/scripts/exit-nodes.sh &
	fi
fi

# block proxies
if [ "$(has_value BLOCK_PROXIES yes)" != "" ] ; then
	echo "$BLOCK_PROXIES_CRON /opt/scripts/proxies.sh" >> /etc/crontabs/root
	if [ -f "/cache/block-proxies.conf" ] ; then
		echo "[*] Copying cached block-proxies.conf ..."
		cp /cache/block-proxies.conf /etc/nginx/block-proxies.conf
	else
		echo "[*] Downloading proxies list (in background) ..."
		/opt/scripts/proxies.sh &
	fi
fi

# block abusers
if [ "$(has_value BLOCK_ABUSERS yes)" != "" ] ; then
	echo "$BLOCK_ABUSERS_CRON /opt/scripts/abusers.sh" >> /etc/crontabs/root
	if [ -f "/cache/block-abusers.conf" ] ; then
		echo "[*] Copying cached block-abusers.conf ..."
		cp /cache/block-abusers.conf /etc/nginx/block-abusers.conf
	else
		echo "[*] Downloading abusers list (in background) ..."
		/opt/scripts/abusers.sh &
	fi
fi

# DNS resolvers
resolvers=$(spaces_to_lua "$DNS_RESOLVERS")
replace_in_file "/usr/local/lib/lua/dns.lua" "%DNS_RESOLVERS%" "$resolvers"
replace_in_file "/etc/nginx/nginx.conf" "%DNS_RESOLVERS%" "$DNS_RESOLVERS"

# whitelist IP
if [ "$(has_value USE_WHITELIST_IP yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%WHITELIST_IP_CACHE%" "lua_shared_dict whitelist_ip_cache 10m;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%WHITELIST_IP_CACHE%" ""
fi
list=$(spaces_to_lua "$WHITELIST_IP_LIST")
replace_in_file "/usr/local/lib/lua/whitelist.lua" "%WHITELIST_IP_LIST%" "$list"

# whitelist rDNS
if [ "$(has_value USE_WHITELIST_REVERSE yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%WHITELIST_REVERSE_CACHE%" "lua_shared_dict whitelist_reverse_cache 10m;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%WHITELIST_REVERSE_CACHE%" ""
fi
list=$(spaces_to_lua "$WHITELIST_REVERSE_LIST")
replace_in_file "/usr/local/lib/lua/whitelist.lua" "%WHITELIST_REVERSE_LIST%" "$list"

# blacklist IP
if [ "$(has_value USE_BLACKLIST_IP yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%BLACKLIST_IP_CACHE%" "lua_shared_dict blacklist_ip_cache 10m;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%BLACKLIST_IP_CACHE%" ""
fi
list=$(spaces_to_lua "$BLACKLIST_IP_LIST")
replace_in_file "/usr/local/lib/lua/blacklist.lua" "%BLACKLIST_IP_LIST%" "$list"

# blacklist rDNS
if [ "$(has_value USE_BLACKLIST_REVERSE yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%BLACKLIST_REVERSE_CACHE%" "lua_shared_dict blacklist_reverse_cache 10m;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%BLACKLIST_REVERSE_CACHE%" ""
fi
list=$(spaces_to_lua "$BLACKLIST_REVERSE_LIST")
replace_in_file "/usr/local/lib/lua/blacklist.lua" "%BLACKLIST_REVERSE_LIST%" "$list"

# request limiting
if [ "$(has_value USE_LIMIT_REQ yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%LIMIT_REQ_ZONE%" "limit_req_zone \$binary_remote_addr zone=limit:${LIMIT_REQ_CACHE} rate=${LIMIT_REQ_RATE};"
else
	replace_in_file "/etc/nginx/nginx.conf" "%LIMIT_REQ_ZONE%" ""
fi

# DNSBL
if [ "$(has_value USE_DNSBL yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%DNSBL_CACHE%" "lua_shared_dict dnsbl_cache 10m;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%DNSBL_CACHE%" "lua_shared_dict dnsbl_cache 10m;"
fi
list=$(spaces_to_lua "$DNSBL_LIST")
replace_in_file "/usr/local/lib/lua/dnsbl.lua" "%DNSBL_LIST%" "$list"

# disable default site
if [ "$DISABLE_DEFAULT_SERVER" = "yes" ] && [ "$MULTISITE" = "yes" ] ; then
	replace_in_file "/etc/nginx/multisite-default-server.conf" "%MULTISITE_DISABLE_DEFAULT_SERVER%" "include /etc/nginx/multisite-disable-default-server.conf;"
else
	replace_in_file "/etc/nginx/multisite-default-server.conf" "%MULTISITE_DISABLE_DEFAULT_SERVER%" ""
fi

# fail2ban setup
if [ "$(has_value USE_FAIL2BAN yes)" != "" ] ; then
	echo "" > /etc/nginx/fail2ban-ip.conf
	rm -rf /etc/fail2ban/jail.d/*.conf
	cp /opt/fail2ban/nginx-action.local /etc/fail2ban/action.d/nginx-action.local
	cp /opt/fail2ban/nginx-filter.local /etc/fail2ban/filter.d/nginx-filter.local
	cp /opt/fail2ban/nginx-jail.local /etc/fail2ban/jail.d/nginx-jail.local
	replace_in_file "/etc/fail2ban/jail.d/nginx-jail.local" "%FAIL2BAN_BANTIME%" "$FAIL2BAN_BANTIME"
	replace_in_file "/etc/fail2ban/jail.d/nginx-jail.local" "%FAIL2BAN_FINDTIME%" "$FAIL2BAN_FINDTIME"
	replace_in_file "/etc/fail2ban/jail.d/nginx-jail.local" "%FAIL2BAN_MAXRETRY%" "$FAIL2BAN_MAXRETRY"
	replace_in_file "/etc/fail2ban/jail.d/nginx-jail.local" "%FAIL2BAN_IGNOREIP%" "$FAIL2BAN_IGNOREIP"
	replace_in_file "/etc/fail2ban/filter.d/nginx-filter.local" "%FAIL2BAN_STATUS_CODES%" "$FAIL2BAN_STATUS_CODES"
fi

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

# CrowdSec setup
if [ "$(has_value USE_CROWDSEC yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%USE_CROWDSEC%" "include /etc/nginx/crowdsec.conf;"
	replace_in_file "/usr/local/lib/lua/crowdsec/crowdsec.conf" "%CROWDSEC_HOST%" "$CROWDSEC_HOST"
	replace_in_file "/usr/local/lib/lua/crowdsec/crowdsec.conf" "%CROWDSEC_KEY%" "$CROWDSEC_KEY"
else
	replace_in_file "/etc/nginx/nginx.conf" "%USE_CROWDSEC%" ""
fi

# create empty logs
touch /var/log/access.log
touch /var/log/error.log

# setup logrotate
replace_in_file "/etc/logrotate.conf" "%LOGROTATE_MAXAGE%" "$LOGROTATE_MAXAGE"
replace_in_file "/etc/logrotate.conf" "%LOGROTATE_MINSIZE%" "$LOGROTATE_MINSIZE"
echo "$LOGROTATE_CRON /opt/scripts/logrotate.sh > /dev/null 2>&1" >> /etc/crontabs/root
