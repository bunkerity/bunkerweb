#!/bin/bash

# load default values
. /opt/entrypoint/defaults.sh

# load some functions
. /opt/entrypoint/utils.sh

# copy stub confs
cp /opt/confs/global/* /etc/nginx/

# include server block(s)
if [ "$SWARM_MODE" = "no" ] ; then
	if [ "$MULTISITE" = "yes" ] ; then
		includes=""
		for server in $SERVER_NAME ; do
			includes="${includes}include /etc/nginx/${server}/server.conf;\n"
		done
		replace_in_file "/etc/nginx/nginx.conf" "%INCLUDE_SERVER%" "$includes"
	else
		replace_in_file "/etc/nginx/nginx.conf" "%INCLUDE_SERVER%" "include /etc/nginx/server.conf;"
	fi
else
	replace_in_file "/etc/nginx/nginx.conf" "%INCLUDE_SERVER%" ""
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
	echo "$AUTO_LETS_ENCRYPT_CRON /opt/scripts/certbot-renew.sh > /dev/null 2>&1" >> /etc/crontabs/nginx
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
	echo "$GEOIP_CRON /opt/scripts/geoip.sh" >> /etc/crontabs/nginx
else
	replace_in_file "/etc/nginx/nginx.conf" "%USE_COUNTRY%" ""
fi

# block bad UA
if [ "$(has_value BLOCK_USER_AGENT yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_USER_AGENT%" "include /etc/nginx/map-user-agent.conf;"
	echo "$BLOCK_USER_AGENT_CRON /opt/scripts/user-agents.sh" >> /etc/crontabs/nginx
else
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_USER_AGENT%" ""
fi

# block bad refferer
if [ "$(has_value BLOCK_REFERRER yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_REFERRER%" "include /etc/nginx/map-referrer.conf;"
	echo "$BLOCK_REFERRER_CRON /opt/scripts/referrers.sh" >> /etc/crontabs/nginx
else
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_REFERRER%" ""
fi

# block TOR exit nodes
if [ "$(has_value BLOCK_TOR_EXIT_NODE yes)" != "" ] ; then
	echo "$BLOCK_TOR_EXIT_NODE_CRON /opt/scripts/exit-nodes.sh" >> /etc/crontabs/nginx
fi

# block proxies
if [ "$(has_value BLOCK_PROXIES yes)" != "" ] ; then
	echo "$BLOCK_PROXIES_CRON /opt/scripts/proxies.sh" >> /etc/crontabs/nginx
fi

# block abusers
if [ "$(has_value BLOCK_ABUSERS yes)" != "" ] ; then
	echo "$BLOCK_ABUSERS_CRON /opt/scripts/abusers.sh" >> /etc/crontabs/nginx
fi

# DNS resolvers
replace_in_file "/etc/nginx/nginx.conf" "%DNS_RESOLVERS%" "$DNS_RESOLVERS"

# whitelist IP
if [ "$(has_value USE_WHITELIST_IP yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%WHITELIST_IP_CACHE%" "lua_shared_dict whitelist_ip_cache 10m;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%WHITELIST_IP_CACHE%" ""
fi

# whitelist rDNS
if [ "$(has_value USE_WHITELIST_REVERSE yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%WHITELIST_REVERSE_CACHE%" "lua_shared_dict whitelist_reverse_cache 10m;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%WHITELIST_REVERSE_CACHE%" ""
fi

# blacklist IP
if [ "$(has_value USE_BLACKLIST_IP yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%BLACKLIST_IP_CACHE%" "lua_shared_dict blacklist_ip_cache 10m;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%BLACKLIST_IP_CACHE%" ""
fi

# blacklist rDNS
if [ "$(has_value USE_BLACKLIST_REVERSE yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%BLACKLIST_REVERSE_CACHE%" "lua_shared_dict blacklist_reverse_cache 10m;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%BLACKLIST_REVERSE_CACHE%" ""
fi

# request limiting
if [ "$(has_value USE_LIMIT_REQ yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%LIMIT_REQ_ZONE%" "limit_req_zone \$binary_remote_addr\$uri zone=limit:${LIMIT_REQ_CACHE} rate=${LIMIT_REQ_RATE};"
else
	replace_in_file "/etc/nginx/nginx.conf" "%LIMIT_REQ_ZONE%" ""
fi

# connection limiting
if [ "$(has_value USE_LIMIT_CONN yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%LIMIT_CONN_ZONE%" "limit_conn_zone \$binary_remote_addr zone=ddos:${LIMIT_CONN_CACHE};"
else
	replace_in_file "/etc/nginx/nginx.conf" "%LIMIT_CONN_ZONE%" ""
fi

# DNSBL
if [ "$(has_value USE_DNSBL yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%DNSBL_CACHE%" "lua_shared_dict dnsbl_cache 10m;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%DNSBL_CACHE%" "lua_shared_dict dnsbl_cache 10m;"
fi

# disable default site
if [ "$DISABLE_DEFAULT_SERVER" = "yes" ] && [ "$MULTISITE" = "yes" ] ; then
	replace_in_file "/etc/nginx/multisite-default-server.conf" "%MULTISITE_DISABLE_DEFAULT_SERVER%" "include /etc/nginx/multisite-disable-default-server.conf;"
else
	replace_in_file "/etc/nginx/multisite-default-server.conf" "%MULTISITE_DISABLE_DEFAULT_SERVER%" ""
fi

# fail2ban setup
if [ "$(has_value USE_FAIL2BAN yes)" != "" ] ; then
	echo "" > /etc/nginx/fail2ban-ip.conf
fi

# CrowdSec setup
if [ "$(has_value USE_CROWDSEC yes)" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%USE_CROWDSEC%" "include /etc/nginx/crowdsec.conf;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%USE_CROWDSEC%" ""
fi

# API
if [ "$USE_API" = "yes" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%USE_API%" "include /etc/nginx/api.conf;"
	if [ "$API_URI" = "random" ] ; then
		API_URI="/$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 32 | head -n 1)"
		echo "[*] Generated API URI : $API_URI"
	fi
	list=$(spaces_to_lua "$API_WHITELIST_IP")
	replace_in_file "/usr/local/lib/lua/api.lua" "%API_WHITELIST_IP%" "$list"
else
	replace_in_file "/etc/nginx/nginx.conf" "%USE_API%" ""
fi
