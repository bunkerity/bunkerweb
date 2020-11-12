#!/bin/bash

# load default values
. /opt/entrypoint/defaults.sh

# load some functions
. /opt/entrypoint/utils.sh

# get nginx path and override multisite variables
NGINX_PREFIX="/etc/nginx/"
if [ "$MULTISITE" = "yes" ] ; then
	NGINX_PREFIX="${NGINX_PREFIX}${1}/"
	for var in $(env) ; do
		name=$(echo "$var" | cut -d '=' -f 1)
		check=$(echo "$name" | grep "^$1_")
		if [ "$check" != "" ] ; then
			repl_name=$(echo "$name" | sed "s~${1}_~~")
			repl_value=$(echo "$var" | sed "s~${name}=~~")
			read -r "$repl_name" <<< $repl_value
		fi
	done
	ROOT_FOLDER="${ROOT_FOLDER}/$1"
fi

# copy stub confs
if [ "$MULTISITE" = "yes" ] ; then
	mkdir "$NGINX_PREFIX"
fi
cp /opt/confs/site/* "$NGINX_PREFIX"

# replace paths
replace_in_file "${NGINX_PREFIX}server.conf" "%MAIN_LUA%" "include ${NGINX_PREFIX}main-lua.conf;"
if [ "$MULTISITE" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%SERVER_CONF%" "include /server-confs/${1}/*.conf;"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%SERVER_CONF%" "include /server-confs/*.conf;"
fi

# client caching
if [ "$USE_CLIENT_CACHE" = "yes" ] ;
	replace_in_file "${NGINX_PREFIX}server.conf" "%USE_CLIENT_CACHE%" "include ${NGINX_PREFIX}client-cache.conf;"
	replace_in_file "${NGINX_PREFIX}client-cache.conf" "%CLIENT_CACHE_EXTENSIONS%" "$CLIENT_CACHE_EXTENSIONS"
	replace_in_file "${NGINX_PREFIX}client-cache.conf" "%CLIENT_CACHE_ETAG%" "$CLIENT_CACHE_ETAG"
	replace_in_file "${NGINX_PREFIX}client-cache.conf" "%CLIENT_CACHE_CONTROL%" "$CLIENT_CACHE_CONTROL"

else
	replace_in_file "${NGINX_PREFIX}server.conf" "%USE_CLIENT_CACHE%" ""
fi

# remote PHP
if [ "$REMOTE_PHP" != "" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%USE_PHP%" "include ${NGINX_PREFIX}php.conf;"
	replace_in_file "${NGINX_PREFIX}php.conf" "%REMOTE_PHP%" "$REMOTE_PHP"
	replace_in_file "${NGINX_PREFIX}fastcgi.conf" "\$document_root" "${REMOTE_PHP_PATH}/"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%USE_PHP%" ""
fi

# serve files
if [ "$SERVE_FILES" = "yes" ] ; then
        replace_in_file "${NGINX_PREFIX}server.conf" "%SERVE_FILES%" "include ${NGINX_PREFIX}serve-files.conf;"
        replace_in_file "${NGINX_PREFIX}serve-files.conf" "%ROOT_FOLDER%" "$ROOT_FOLDER"
else
        replace_in_file "${NGINX_PREFIX}server.conf" "%SERVE_FILES%" ""
fi

# remove server header
if [ "$HEADER_SERVER" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%HEADER_SERVER%" ""
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%HEADER_SERVER%" "more_clear_headers 'Server';"
fi

# X-Frame-Options header
if [ "$X_FRAME_OPTIONS" != "" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%X_FRAME_OPTIONS%" "include ${NGINX_PREFIX}x-frame-options.conf;"
	replace_in_file "${NGINX_PREFIX}x-frame-options.conf" "%X_FRAME_OPTIONS%" "$X_FRAME_OPTIONS"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%X_FRAME_OPTIONS%" ""
fi

# X-XSS-Protection header
if [ "$X_XSS_PROTECTION" != "" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%X_XSS_PROTECTION%" "include ${NGINX_PREFIX}x-xss-protection.conf;"
	replace_in_file "${NGINX_PREFIX}x-xss-protection.conf" "%X_XSS_PROTECTION%" "$X_XSS_PROTECTION"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%X_XSS_PROTECTION%" ""
fi

# X-Content-Type-Options header
if [ "$X_CONTENT_TYPE_OPTIONS" != "" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%X_CONTENT_TYPE_OPTIONS%" "include ${NGINX_PREFIX}x-content-type-options.conf;"
	replace_in_file "${NGINX_PREFIX}x-content-type-options.conf" "%X_CONTENT_TYPE_OPTIONS%" "$X_CONTENT_TYPE_OPTIONS"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%X_CONTENT_TYPE_OPTIONS%" ""
fi

# Referrer-Policy header
if [ "$REFERRER_POLICY" != "" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%REFERRER_POLICY%" "include ${NGINX_PREFIX}referrer-policy.conf;"
	replace_in_file "${NGINX_PREFIX}referrer-policy.conf" "%REFERRER_POLICY%" "$REFERRER_POLICY"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%REFERRER_POLICY%" ""
fi

# Feature-Policy header
if [ "$FEATURE_POLICY" != "" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%FEATURE_POLICY%" "include ${NGINX_PREFIX}feature-policy.conf;"
	replace_in_file "${NGINX_PREFIX}feature-policy.conf" "%FEATURE_POLICY%" "$FEATURE_POLICY"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%FEATURE_POLICY%" ""
fi

# Content-Security-Policy header
if [ "$CONTENT_SECURITY_POLICY" != "" ] ; then
        replace_in_file "${NGINX_PREFIX}server.conf" "%CONTENT_SECURITY_POLICY%" "include ${NGINX_PREFIX}content-security-policy.conf;"
        replace_in_file "${NGINX_PREFIX}content-security-policy.conf" "%CONTENT_SECURITY_POLICY%" "$CONTENT_SECURITY_POLICY"
else
        replace_in_file "${NGINX_PREFIX}server.conf" "%CONTENT_SECURITY_POLICY%" ""
fi

# cookie flags
if [ "$COOKIE_FLAGS" != "" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%COOKIE_FLAGS%" "include ${NGINX_PREFIX}cookie-flags.conf;"
	if [ "$COOKIE_AUTO_SECURE_FLAG" = "yes" ] ; then
		if [ "$AUTO_LETS_ENCRYPT" = "yes" ] || [ "$USE_CUSTOM_HTTPS" = "yes" ] || [ "$GENERATE_SELF_SIGNED_SSL" = "yes" ] ; then
			COOKIE_FLAGS="${COOKIE_FLAGS} Secure"
		fi
	fi
	replace_in_file "${NGINX_PREFIX}cookie-flags.conf" "%COOKIE_FLAGS%" "$COOKIE_FLAGS"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%COOKIE_FLAGS%" ""
fi

# disable default server
if [ "$DISABLE_DEFAULT_SERVER" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%DISABLE_DEFAULT_SERVER%" "include ${NGINX_PREFIX}disable-default-server.conf;"
	if [ "$MULTISITE" == "yes" ] ; then
		replace_in_file "${NGINX_PREFIX}disable-default-server.conf" "%SERVER_NAME%" "$1"
	else
		SERVER_NAME_PIPE=$(echo $SERVER_NAME | sed "s/ /|/g")
		replace_in_file "${NGINX_PREFIX}disable-default-server.conf" "%SERVER_NAME%" "$SERVER_NAME_PIPE"
	fi
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%DISABLE_DEFAULT_SERVER%" ""
fi

# set the server host name
if [ "$MULTISITE" == "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%SERVER_NAME%" "$1"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%SERVER_NAME%" "$SERVER_NAME"
fi

# allowed HTTP methods
replace_in_file "${NGINX_PREFIX}server.conf" "%ALLOWED_METHODS%" "$ALLOWED_METHODS"

# country ban
if [ "$BLOCK_COUNTRY" != "" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%BLOCK_COUNTRY%" "include ${NGINX_PREFIX}geoip-server.conf;"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%BLOCK_COUNTRY%" ""
fi

# block bad UA
if [ "$BLOCK_USER_AGENT" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%BLOCK_USER_AGENT%" "include ${NGINX_PREFIX}block-user-agent.conf;"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%BLOCK_USER_AGENT%" ""
fi

# block TOR exit nodes
if [ "$BLOCK_TOR_EXIT_NODE" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%BLOCK_TOR_EXIT_NODE%" "include /etc/nginx/block-tor-exit-node.conf;"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%BLOCK_TOR_EXIT_NODE%" ""
fi

# block proxies
if [ "$BLOCK_PROXIES" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%BLOCK_PROXIES%" "include /etc/nginx/block-proxies.conf;"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%BLOCK_PROXIES%" ""
fi

# block abusers
if [ "$BLOCK_ABUSERS" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%BLOCK_ABUSERS%" "include /etc/nginx/block-abusers.conf;"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%BLOCK_ABUSERS%" ""
fi

# HTTPS config
if [ "$AUTO_LETS_ENCRYPT" = "yes" ] || [ "$USE_CUSTOM_HTTPS" = "yes" ] || [ "$GENERATE_SELF_SIGNED_SSL" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%USE_HTTPS%" "include ${NGINX_PREFIX}https.conf;"
	replace_in_file "${NGINX_PREFIX}https.conf" "%HTTPS_PORT%" "$HTTPS_PORT"
	if [ "$HTTP2" = "yes" ] ; then
		replace_in_file "${NGINX_PREFIX}https.conf" "%HTTP2%" "http2"
	else
		replace_in_file "${NGINX_PREFIX}https.conf" "%HTTP2%" ""
	fi
	replace_in_file "${NGINX_PREFIX}https.conf" "%HTTPS_PROTOCOLS%" "$HTTPS_PROTOCOLS"
	if [ "$(echo $HTTPS_PROTOCOLS | grep TLSv1.2)" != "" ] ; then
		replace_in_file "${NGINX_PREFIX}https.conf" "%SSL_DHPARAM%" "ssl_dhparam /etc/nginx/dhparam;"
		replace_in_file "${NGINX_PREFIX}https.conf" "%SSL_CIPHERS%" "ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;"
	else
		replace_in_file "${NGINX_PREFIX}https.conf" "%SSL_DHPARAM%" ""
		replace_in_file "${NGINX_PREFIX}https.conf" "%SSL_CIPHERS%" ""
	fi
	if [ "$STRICT_TRANSPORT_SECURITY" != "" ] ; then
		replace_in_file "${NGINX_PREFIX}https.conf" "%STRICT_TRANSPORT_SECURITY%" "more_set_headers 'Strict-Transport-Security: $STRICT_TRANSPORT_SECURITY';"
	else
		replace_in_file "${NGINX_PREFIX}https.conf" "%STRICT_TRANSPORT_SECURITY%" ""
	fi
	if [ "$AUTO_LETS_ENCRYPT" = "yes" ] ; then
		FIRST_SERVER_NAME=$(echo "$SERVER_NAME" | cut -d " " -f 1)
		replace_in_file "${NGINX_PREFIX}https.conf" "%HTTPS_CERT%" "/etc/letsencrypt/live/${FIRST_SERVER_NAME}/fullchain.pem"
		replace_in_file "${NGINX_PREFIX}https.conf" "%HTTPS_KEY%" "/etc/letsencrypt/live/${FIRST_SERVER_NAME}/privkey.pem"
	elif [ "$USE_CUSTOM_HTTPS" = "yes" ] ; then
		replace_in_file "${NGINX_PREFIX}https.conf" "%HTTPS_CERT%" "$CUSTOM_HTTPS_CERT"
		replace_in_file "${NGINX_PREFIX}https.conf" "%HTTPS_KEY%" "$CUSTOM_HTTPS_KEY"
	elif [ "$GENERATE_SELF_SIGNED_SSL" = "yes" ] ; then
		replace_in_file "${NGINX_PREFIX}https.conf" "%HTTPS_CERT%" "/etc/nginx/self-signed-ssl/cert.pem"
		replace_in_file "${NGINX_PREFIX}https.conf" "%HTTPS_KEY%" "/etc/nginx/self-signed-ssl/key.pem"
	fi
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%USE_HTTPS%" ""
fi

# listen on HTTP_PORT
if [ "$LISTEN_HTTP" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%LISTEN_HTTP%" "listen 0.0.0.0:${HTTP_PORT};"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%LISTEN_HTTP%" ""
fi

# HTTP to HTTPS redirect
if [ "$REDIRECT_HTTP_TO_HTTPS" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%REDIRECT_HTTP_TO_HTTPS%" "include ${NGINX_PREFIX}redirect-http-to-https.conf;"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%REDIRECT_HTTP_TO_HTTPS%" ""
fi

# ModSecurity config
if [ "$USE_MODSECURITY" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}modsecurity.conf" "%MODSEC_RULES_FILE%" "${NGINX_PREFIX}/modsecurity-rules.conf"
	replace_in_file "${NGINX_PREFIX}server.conf" "%USE_MODSECURITY%" "include ${NGINX_PREFIX}modsecurity.conf;"
	if ls /modsec-confs/*.conf > /dev/null 2>&1 ; then
		if [ "$MULTISITE" = "yes" ] ; then
			replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_RULES%" "include /modsec-confs/${1}/*.conf"
		else
			replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_RULES%" "include /modsec-confs/*.conf"
		fi
	else
		replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_RULES%" ""
	fi
	if [ "$USE_MODSECURITY_CRS" = "yes" ] ; then
		replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CRS%" "include /etc/nginx/owasp-crs.conf"
		if ls /modsec-crs-confs/*.conf > /dev/null 2>&1 ; then
			if [ "$MULTISITE" = "yes" ] ; then
				replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_CRS%" "include /modsec-crs-confs/${1}/*.conf"
			else
				replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_CRS%" "include /modsec-crs-confs/*.conf"
			fi
		else
			replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_CRS%" ""
		fi
		replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CRS_RULES%" "include /etc/nginx/owasp-crs/*.conf"
	else
		replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CRS%" ""
		replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_CRS%" ""
		replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CRS_RULES%" ""
	fi
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%USE_MODSECURITY%" ""
fi

# real IP behind reverse proxy
if [ "$PROXY_REAL_IP" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%PROXY_REAL_IP%" "include ${NGINX_PREFIX}proxy-real-ip.conf;"
	froms=""
	for from in $PROXY_REAL_IP_FROM ; do
		froms="${froms}set_real_ip_from ${from};\n"
	done
	replace_in_file "${NGINX_PREFIX}proxy-real-ip.conf" "%PROXY_REAL_IP_FROM%" "$froms"
	replace_in_file "${NGINX_PREFIX}proxy-real-ip.conf" "%PROXY_REAL_IP_HEADER%" "$PROXY_REAL_IP_HEADER"
	replace_in_file "${NGINX_PREFIX}proxy-real-ip.conf" "%PROXY_REAL_IP_RECURSIVE%" "$PROXY_REAL_IP_RECURSIVE"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%PROXY_REAL_IP%" ""
fi

# custom errors
ERRORS=""
for var in $(env) ; do
	var_name=$(echo "$var" | cut -d '=' -f 1 | cut -d '_' -f 1)
	if [ "z${var_name}" = "zERROR" ] ; then
		err_code=$(echo "$var" | cut -d '=' -f 1 | cut -d '_' -f 2)
		err_page=$(echo "$var" | cut -d '=' -f 2)
		cp /opt/confs/error.conf ${NGINX_PREFIX}error-${err_code}.conf
		replace_in_file "${NGINX_PREFIX}error-${err_code}.conf" "%CODE%" "$err_code"
		replace_in_file "${NGINX_PREFIX}error-${err_code}.conf" "%PAGE%" "$err_page"
		replace_in_file "${NGINX_PREFIX}error-${err_code}.conf" "%ROOT_FOLDER%" "$ROOT_FOLDER"
		ERRORS="${ERRORS}include ${NGINX_PREFIX}error-${err_code}.conf;\n"
	fi
done
replace_in_file "${NGINX_PREFIX}server.conf" "%ERRORS%" "$ERRORS"

# auth basic
if [ "$USE_AUTH_BASIC" = "yes" ] ; then
	if [ "$AUTH_BASIC_LOCATION" = "sitewide" ] ; then
		replace_in_file "${NGINX_PREFIX}server.conf" "%AUTH_BASIC%" "include ${NGINX_PREFIX}auth-basic-sitewide.conf;"
		replace_in_file "${NGINX_PREFIX}auth-basic-sitewide.conf" "%AUTH_BASIC_TEXT%" "$AUTH_BASIC_TEXT";
	else
		replace_in_file "${NGINX_PREFIX}server.conf" "%AUTH_BASIC%" "include ${NGINX_PREFIX}auth-basic.conf;"
		replace_in_file "${NGINX_PREFIX}auth-basic.conf" "%AUTH_BASIC_LOCATION%" "$AUTH_BASIC_LOCATION";
		replace_in_file "${NGINX_PREFIX}auth-basic.conf" "%AUTH_BASIC_TEXT%" "$AUTH_BASIC_TEXT";
	fi
	htpasswd -b -B -c ${NGINX_PREFIX}.htpasswd "$AUTH_BASIC_USER" "$AUTH_BASIC_PASSWORD"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%AUTH_BASIC%" ""
fi

# whitelist IP
if [ "$USE_WHITELIST_IP" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_WHITELIST_IP%" "true"
else
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_WHITELIST_IP%" "false"
fi

# whitelist rDNS
if [ "$USE_WHITELIST_REVERSE" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_WHITELIST_REVERSE%" "true"
else
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_WHITELIST_REVERSE%" "false"
fi

# blacklist IP
if [ "$USE_BLACKLIST_IP" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_BLACKLIST_IP%" "true"
else
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_BLACKLIST_IP%" "false"
fi

# blacklist rDNS
if [ "$USE_BLACKLIST_REVERSE" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_BLACKLIST_REVERSE%" "true"
else
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_BLACKLIST_REVERSE%" "false"
fi

# DNSBL
if [ "$USE_DNSBL" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_DNSBL%" "true"
else
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_DNSBL%" "false"
fi

# antibot uri and session secret
replace_in_file "${NGINX_PREFIX}main-lua.conf" "%ANTIBOT_URI%" "$ANTIBOT_URI"
if [ "$ANTIBOT_SESSION_SECRET" = "random" ] ; then
	ANTIBOT_SESSION_SECRET=$(cat /dev/urandom | tr -dc A-Za-z0-9 | head -c 32)
fi
replace_in_file "${NGINX_PREFIX}main-lua.conf" "%ANTIBOT_SESSION_SECRET%" "$ANTIBOT_SESSION_SECRET"

# antibot via cookie
if [ "$USE_ANTIBOT" = "cookie" ] ; then
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_COOKIE%" "true"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_JAVASCRIPT%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_CAPTCHA%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_RECAPTCHA%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_JAVASCRIPT%" ""
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_CAPTCHA%" ""
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_RECAPTCHA%" ""
# antibot via javascript
elif [ "$USE_ANTIBOT" = "javascript" ] ; then
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_COOKIE%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_JAVASCRIPT%" "true"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_CAPTCHA%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_RECAPTCHA%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_JAVASCRIPT%" "include ${NGINX_PREFIX}antibot-javascript.conf;"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_CAPTCHA%" ""
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_RECAPTCHA%" ""
	replace_in_file "${NGINX_PREFIX}antibot-javascript.conf" "%ANTIBOT_URI%" "$ANTIBOT_URI"
# antibot via captcha
elif [ "$USE_ANTIBOT" = "captcha" ] ; then
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_COOKIE%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_JAVASCRIPT%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_CAPTCHA%" "true"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_RECAPTCHA%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_JAVASCRIPT%" ""
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_CAPTCHA%" "include ${NGINX_PREFIX}antibot-captcha.conf;"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_RECAPTCHA%" ""
	replace_in_file "${NGINX_PREFIX}antibot-captcha.conf" "%ANTIBOT_URI%" "$ANTIBOT_URI"
# antibot via recaptcha
elif [ "$USE_ANTIBOT" = "recaptcha" ] ; then
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_COOKIE%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_JAVASCRIPT%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_CAPTCHA%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_RECAPTCHA%" "true"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_JAVASCRIPT%" ""
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_CAPTCHA%" ""
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_RECAPTCHA%" "include ${NGINX_PREFIX}antibot-recaptcha.conf;"
	replace_in_file "${NGINX_PREFIX}antibot-recaptcha.conf" "%ANTIBOT_URI%" "$ANTIBOT_URI"
	replace_in_file "${NGINX_PREFIX}antibot-recaptcha.conf" "%ANTIBOT_RECAPTCHA_SITEKEY%" "$ANTIBOT_RECAPTCHA_SITEKEY"
	replace_in_file "${NGINX_PREFIX}antibot-recaptcha.conf" "%ANTIBOT_RECAPTCHA_SECRET%" "$ANTIBOT_RECAPTCHA_SECRET"
	replace_in_file "${NGINX_PREFIX}antibot-recaptcha.conf" "%ANTIBOT_RECAPTCHA_SCORE%" "$ANTIBOT_RECAPTCHA_SCORE"
else
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_COOKIE%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_JAVASCRIPT%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_CAPTCHA%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_ANTIBOT_RECAPTCHA%" "false"
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_JAVASCRIPT%" ""
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_CAPTCHA%" ""
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%INCLUDE_ANTIBOT_RECAPTCHA%" ""
fi

# request limiting
if [ "$USE_LIMIT_REQ" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}server.conf" "%LIMIT_REQ%" "include ${NGINX_PREFIX}limit-req.conf;"
	replace_in_file "${NGINX_PREFIX}limit-req.conf" "%LIMIT_REQ_BURST%" "$LIMIT_REQ_BURST"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%LIMIT_REQ%" ""
fi

# fail2ban
if [ "$USE_FAIL2BAN" = "yes" ] ; then
	echo "" > ${NGINX_PREFIX}fail2ban-ip.conf
	replace_in_file "${NGINX_PREFIX}server.conf" "%USE_FAIL2BAN%" "include ${NGINX_PREFIX}fail2ban-ip.conf;"
else
	replace_in_file "${NGINX_PREFIX}server.conf" "%USE_FAIL2BAN%" ""
fi

# clamav scan uploaded files
if [ "$USE_CLAMAV_UPLOAD" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%USE_CLAMAV_UPLOAD%" "include ${NGINX_PREFIX}modsecurity-clamav.conf"
else
	replace_in_file "${NGINX_PREFIX}modsecurity-rules.conf" "%USE_CLAMAV_UPLOAD%" ""
fi

# CrowdSec
if [ "$USE_CROWDSEC" = "yes" ] ; then
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_CROWDSEC%" "true"
else
	replace_in_file "${NGINX_PREFIX}main-lua.conf" "%USE_CROWDSEC%" "false"
fi
