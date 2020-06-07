#!/bin/sh

echo "[*] Starting bunkerized-nginx ..."

# execute custom scripts if it's a customized image
run-parts /opt/entrypoint.d

# trap SIGTERM and SIGINT
function trap_exit() {
	echo "[*] Catched stop operation"
	echo "[*] Stopping crond ..."
	pkill -TERM crond
	if [ "$USE_PHP" = "yes" ] ; then
		echo "[*] Stopping php ..."
		pkill -TERM php-fpm7
	fi
	if [ "$USE_FAIL2BAN" = "yes" ] ; then
		echo "[*] Stopping fail2ban"
		fail2ban-client stop > /dev/null
	fi
	echo "[*] Stopping nginx ..."
	/usr/sbin/nginx -s stop
	pkill -TERM tail
}
trap "trap_exit" TERM INT

# replace pattern in file
function replace_in_file() {
	# escape slashes
	pattern=$(echo "$2" | sed "s/\//\\\\\//g")
	replace=$(echo "$3" | sed "s/\//\\\\\//g")
	sed -i "s/$pattern/$replace/g" "$1"
}

# copy stub confs
cp /opt/confs/*.conf /etc/nginx
cp -r /opt/confs/owasp-crs /etc/nginx
cp /opt/confs/php.ini /etc/php7/php.ini

# remove cron jobs
echo "" > /etc/crontabs/root

# set default values
MAX_CLIENT_SIZE="${MAX_CLIENT_SIZE-10m}"
SERVER_TOKENS="${SERVER_TOKENS-off}"
CACHE="${CACHE-max=1000 inactive=60s}"
CACHE_ERRORS="${CACHE_ERRORS-on}"
CACHE_USES="${CACHE_USES-1}"
CACHE_VALID="${CACHE_VALID-60s}"
#CLIENT_CACHE="${CLIENT_CACHE}-css|gif|htm|html|ico|jpeg|jpg|js|png|svg|tif|tiff|eot|otf|ttf|woff|woff2"
#CLIENT_CACHE_EXPIRES="${CLIENT_CACHE_EXPIRES}-1d}"
#CLIENT_CACHE_CONTROL=
USE_GZIP="${USE_GZIP-off}"
GZIP_COMP_LEVEL="${GZIP_COMP_LEVEL-6}"
GZIP_MIN_LENGTH="${GZIP_MIN_LENGTH-10240}"
GZIP_TYPES="${GZIP_TYPES-text/css text/javascript text/xml text/plain text/x-component application/javascript application/x-javascript application/json application/xml application/rss+xml application/atom+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml}"
USE_PHP="${USE_PHP-yes}"
HEADER_SERVER="${HEADER_SERVER-no}"
X_FRAME_OPTIONS="${X_FRAME_OPTIONS-DENY}"
X_XSS_PROTECTION="${X_XSS_PROTECTION-1; mode=block}"
X_CONTENT_TYPE_OPTIONS="${X_CONTENT_TYPE_OPTIONS-nosniff}"
REFERRER_POLICY="${REFERRER_POLICY-no-referrer}"
FEATURE_POLICY="${FEATURE_POLICY-accelerometer 'none'; ambient-light-sensor 'none'; autoplay 'none'; camera 'none'; display-capture 'none'; document-domain 'none'; encrypted-media 'none'; fullscreen 'none'; geolocation 'none'; gyroscope 'none'; magnetometer 'none'; microphone 'none'; midi 'none'; payment 'none'; picture-in-picture 'none'; speaker 'none'; sync-xhr 'none'; usb 'none'; vibrate 'none'; vr 'none'}"
DISABLE_DEFAULT_SERVER="${DISABLE_DEFAULT_SERVER-no}"
SERVER_NAME="${SERVER_NAME-www.bunkerity.com}"
ALLOWED_METHODS="${ALLOWED_METHODS-GET|POST|HEAD}"
BLOCK_COUNTRY="${BLOCK_COUNTRY-}"
BLOCK_USER_AGENT="${BLOCK_USER_AGENT-yes}"
BLOCK_TOR_EXIT_NODE="${BLOCK_TOR_EXIT_NODE-no}"
AUTO_LETS_ENCRYPT="${AUTO_LETS_ENCRYPT-no}"
HTTP2="${HTTP2-yes}"
STRICT_TRANSPORT_SECURITY="${STRICT_TRANSPORT_SECURITY-max-age=31536000}"
PHP_EXPOSE="${PHP_EXPOSE-no}"
PHP_DISPLAY_ERRORS="${PHP_DISPLAY_ERRORS-no}"
PHP_OPEN_BASEDIR="${PHP_OPEN_BASEDIR-/www/:/tmp/}"
PHP_ALLOW_URL_FOPEN="${PHP_ALLOW_URL_FOPEN-no}"
PHP_ALLOW_URL_INCLUDE="${PHP_ALLOW_URL_INCLUDE-no}"
PHP_FILE_UPLOADS="${PHP_FILE_UPLOADS-yes}"
PHP_UPLOAD_MAX_FILESIZE="${PHP_UPLOAD_MAX_FILESIZE-10M}"
PHP_DISABLE_FUNCTIONS="${PHP_DISABLE_FUNCTIONS-system, exec, shell_exec, passthru, phpinfo, show_source, highlight_file, popen, proc_open, fopen_with_path, dbmopen, dbase_open, putenv, filepro, filepro_rowcount, filepro_retrieve, posix_mkfifo}"
USE_MODSECURITY="${USE_MODSECURITY-yes}"
USE_MODSECURITY_CRS="${USE_MODSECURITY_CRS-yes}"
CONTENT_SECURITY_POLICY="${CONTENT_SECURITY_POLICY-object-src 'none'; frame-ancestors 'none'; form-action 'self'; upgrade-insecure-requests; block-all-mixed-content; sandbox allow-forms allow-same-origin allow-scripts; base-uri 'self';}"
COOKIE_FLAGS="${COOKIE_FLAGS-* HttpOnly}"
SERVE_FILES="${SERVE_FILES-yes}"
WRITE_ACCESS="${WRITE_ACCESS-no}"
REDIRECT_HTTP_TO_HTTPS="${REDIRECT_HTTP_TO_HTTPS-no}"
LISTEN_HTTP="${LISTEN_HTTP-yes}"
USE_FAIL2BAN="${USE_FAIL2BAN-yes}"
FAIL2BAN_STATUS_CODES="${FAIL2BAN_STATUS_CODES-400|401|403|404|405|444}"
FAIL2BAN_BANTIME="${FAIL2BAN_BANTIME-3600}"
FAIL2BAN_FINDTIME="${FAIL2BAN_FINDTIME-60}"
FAIL2BAN_MAXRETRY="${FAIL2BAN_MAXRETRY-10}"
USE_CLAMAV_UPLOAD="${USE_CLAMAV_UPLOAD-yes}"
USE_CLAMAV_SCAN="${USE_CLAMAV_SCAN-yes}"
CLAMAV_SCAN_REMOVE="${CLAMAV_SCAN_REMOVE-yes}"

# install additional modules if needed
if [ "$ADDITIONAL_MODULES" != "" ] ; then
	apk add $ADDITIONAL_MODULES
fi

# replace values
replace_in_file "/etc/nginx/nginx.conf" "%MAX_CLIENT_SIZE%" "$MAX_CLIENT_SIZE"
replace_in_file "/etc/nginx/nginx.conf" "%SERVER_TOKENS%" "$SERVER_TOKENS"
replace_in_file "/etc/nginx/cache.conf" "%CACHE%" "$CACHE"
replace_in_file "/etc/nginx/cache.conf" "%CACHE_ERRORS%" "$CACHE_ERRORS"
replace_in_file "/etc/nginx/cache.conf" "%CACHE_USES%" "$CACHE_USES"
replace_in_file "/etc/nginx/cache.conf" "%CACHE_VALID%" "$CACHE_VALID"
replace_in_file "/etc/nginx/gzip.conf" "%USE_GZIP%" "$USE_GZIP"
replace_in_file "/etc/nginx/gzip.conf" "%GZIP_COMP_LEVEL%" "$GZIP_COMP_LEVEL"
replace_in_file "/etc/nginx/gzip.conf" "%GZIP_MIN_LENGTH%" "$GZIP_MIN_LENGTH"
replace_in_file "/etc/nginx/gzip.conf" "%GZIP_TYPES%" "$GZIP_TYPES"
if [ "$USE_PHP" = "yes" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%USE_PHP%" "include /etc/nginx/php.conf;"
	if [ "$PHP_EXPOSE" = "yes" ] ; then
		replace_in_file "/etc/php7/php.ini" "%PHP_EXPOSE%" "On"
	else
		replace_in_file "/etc/php7/php.ini" "%PHP_EXPOSE%" "Off"
	fi
	if [ "$PHP_DISPLAY_ERRORS" = "yes" ] ; then
		replace_in_file "/etc/php7/php.ini" "%PHP_DISPLAY_ERRORS%" "On"
	else
		replace_in_file "/etc/php7/php.ini" "%PHP_DISPLAY_ERRORS%" "Off"
	fi
	replace_in_file "/etc/php7/php.ini" "%PHP_OPEN_BASEDIR%" "$PHP_OPEN_BASEDIR"
	if [ "$PHP_ALLOW_URL_FOPEN" = "yes" ] ; then
		replace_in_file "/etc/php7/php.ini" "%PHP_ALLOW_URL_FOPEN%" "On"
	else
		replace_in_file "/etc/php7/php.ini" "%PHP_ALLOW_URL_FOPEN%" "Off"
	fi
	if [ "$PHP_ALLOW_URL_INCLUDE" = "yes" ] ; then
		replace_in_file "/etc/php7/php.ini" "%PHP_ALLOW_URL_INCLUDE%" "On"
	else
		replace_in_file "/etc/php7/php.ini" "%PHP_ALLOW_URL_INCLUDE%" "Off"
	fi
	if [ "$PHP_FILE_UPLOADS" = "yes" ] ; then
		replace_in_file "/etc/php7/php.ini" "%PHP_FILE_UPLOADS%" "On"
	else
		replace_in_file "/etc/php7/php.ini" "%PHP_FILE_UPLOADS%" "Off"
	fi
	replace_in_file "/etc/php7/php.ini" "%PHP_UPLOAD_MAX_FILESIZE%" "$PHP_UPLOAD_MAX_FILESIZE"
	replace_in_file "/etc/php7/php.ini" "%PHP_DISABLE_FUNCTIONS%" "$PHP_DISABLE_FUNCTIONS"
else
	replace_in_file "/etc/nginx/server.conf" "%USE_PHP%" ""
fi
if [ "$HEADER_SERVER" = "yes" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%HEADER_SERVER%" ""
else
	replace_in_file "/etc/nginx/server.conf" "%HEADER_SERVER%" "more_clear_headers 'Server';"
fi
if [ "$X_FRAME_OPTIONS" != "" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%X_FRAME_OPTIONS%" "include /etc/nginx/x-frame-options.conf;"
	replace_in_file "/etc/nginx/x-frame-options.conf" "%X_FRAME_OPTIONS%" "$X_FRAME_OPTIONS"
else
	replace_in_file "/etc/nginx/server.conf" "%X_FRAME_OPTIONS%" ""
fi
if [ "$X_XSS_PROTECTION" != "" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%X_XSS_PROTECTION%" "include /etc/nginx/x-xss-protection.conf;"
	replace_in_file "/etc/nginx/x-xss-protection.conf" "%X_XSS_PROTECTION%" "$X_XSS_PROTECTION"
else
	replace_in_file "/etc/nginx/server.conf" "%X_XSS_PROTECTION%" ""
fi
if [ "$X_CONTENT_TYPE_OPTIONS" != "" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%X_CONTENT_TYPE_OPTIONS%" "include /etc/nginx/x-content-type-options.conf;"
	replace_in_file "/etc/nginx/x-content-type-options.conf" "%X_CONTENT_TYPE_OPTIONS%" "$X_CONTENT_TYPE_OPTIONS"
else
	replace_in_file "/etc/nginx/server.conf" "%X_CONTENT_TYPE_OPTIONS%" ""
fi
if [ "$REFERRER_POLICY" != "" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%REFERRER_POLICY%" "include /etc/nginx/referrer-policy.conf;"
	replace_in_file "/etc/nginx/referrer-policy.conf" "%REFERRER_POLICY%" "$REFERRER_POLICY"
else
	replace_in_file "/etc/nginx/server.conf" "%REFERRER_POLICY%" ""
fi
if [ "$FEATURE_POLICY" != "" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%FEATURE_POLICY%" "include /etc/nginx/feature-policy.conf;"
	replace_in_file "/etc/nginx/feature-policy.conf" "%FEATURE_POLICY%" "$FEATURE_POLICY"
else
	replace_in_file "/etc/nginx/server.conf" "%FEATURE_POLICY%" ""
fi
if [ "$DISABLE_DEFAULT_SERVER" = "yes" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%DISABLE_DEFAULT_SERVER%" "include /etc/nginx/disable-default-server.conf;"
	SERVER_NAME_PIPE=$(echo $SERVER_NAME | sed "s/ /|/g")
	replace_in_file "/etc/nginx/disable-default-server.conf" "%SERVER_NAME%" "$SERVER_NAME_PIPE"
else
	replace_in_file "/etc/nginx/server.conf" "%DISABLE_DEFAULT_SERVER%" ""
fi
replace_in_file "/etc/nginx/server.conf" "%SERVER_NAME%" "$SERVER_NAME"
replace_in_file "/etc/nginx/server.conf" "%ALLOWED_METHODS%" "$ALLOWED_METHODS"
if [ "$BLOCK_COUNTRY" != "" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_COUNTRY%" "include /etc/nginx/geoip.conf;"
	replace_in_file "/etc/nginx/server.conf" "%BLOCK_COUNTRY%" "include /etc/nginx/geoip-server.conf;"
	replace_in_file "/etc/nginx/geoip.conf" "%BLOCK_COUNTRY%" "$(echo $BLOCK_COUNTRY | sed 's/ / no;\n/g') no;"
else
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_COUNTRY%" ""
	replace_in_file "/etc/nginx/server.conf" "%BLOCK_COUNTRY%" ""
fi
if [ "$BLOCK_USER_AGENT" = "yes" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%BLOCK_USER_AGENT%" "include /etc/nginx/block-user-agent.conf;"
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_USER_AGENT%" "include /etc/nginx/map-user-agent.conf;"
	/opt/scripts/user-agents.sh
	echo "0 0 * * * /opt/scripts/user-agents.sh" >> /etc/crontabs/root
else
	replace_in_file "/etc/nginx/server.conf" "%BLOCK_USER_AGENT%" ""
	replace_in_file "/etc/nginx/nginx.conf" "%BLOCK_USER_AGENT%" ""
fi
if [ "$BLOCK_TOR_EXIT_NODE" = "yes" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%BLOCK_TOR_EXIT_NODE%" "include /etc/nginx/block-tor-exit-node.conf;"
	/opt/scripts/exit-nodes.sh
	echo "0 * * * * /opt/scripts/exit-nodes.sh" >> /etc/crontabs/root
else
	replace_in_file "/etc/nginx/server.conf" "%BLOCK_TOR_EXIT_NODE%" ""
fi
if [ "$AUTO_LETS_ENCRYPT" = "yes" ] ; then

	FIRST_SERVER_NAME=$(echo "$SERVER_NAME" | cut -d " " -f 1)
	DOMAINS_LETS_ENCRYPT=$(echo "$SERVER_NAME" | sed "s/ /,/g")
	EMAIL_LETS_ENCRYPT="${EMAIL_LETS_ENCRYPT-contact@$FIRST_SERVER_NAME}"

	replace_in_file "/etc/nginx/server.conf" "%AUTO_LETS_ENCRYPT%" "include /etc/nginx/auto-lets-encrypt.conf;"

	if [ "$HTTP2" = "yes" ] ; then
		replace_in_file "/etc/nginx/auto-lets-encrypt.conf" "%HTTP2%" "http2"
	else
		replace_in_file "/etc/nginx/auto-lets-encrypt.conf" "%HTTP2%" ""
	fi
	replace_in_file "/etc/nginx/auto-lets-encrypt.conf" "%FIRST_SERVER_NAME%" "$FIRST_SERVER_NAME"
	if [ "$STRICT_TRANSPORT_SECURITY" != "" ] ; then
		replace_in_file "/etc/nginx/auto-lets-encrypt.conf" "%STRICT_TRANSPORT_SECURITY%" "more_set_headers 'Strict-Transport-Security: $STRICT_TRANSPORT_SECURITY';"
	else
		replace_in_file "/etc/nginx/auto-lets-encrypt.conf" "%STRICT_TRANSPORT_SECURITY%" ""
	fi
	if [ -f /etc/letsencrypt/live/${FIRST_SERVER_NAME}/fullchain.pem ] ; then
		/opt/scripts/certbot-renew.sh
	else
		certbot certonly --standalone -n --preferred-challenges http -d "$DOMAINS_LETS_ENCRYPT" --email "$EMAIL_LETS_ENCRYPT" --agree-tos
	fi
	echo "0 0 * * * /opt/scripts/certbot-renew.sh" >> /etc/crontabs/root
else
	replace_in_file "/etc/nginx/server.conf" "%AUTO_LETS_ENCRYPT%" ""
fi

if [ "$LISTEN_HTTP" = "yes" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%LISTEN_HTTP%" "listen 0.0.0.0:80;"
else
	replace_in_file "/etc/nginx/server.conf" "%LISTEN_HTTP%" ""
fi

if [ "$REDIRECT_HTTP_TO_HTTPS" = "yes" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%REDIRECT_HTTP_TO_HTTPS%" "include /etc/nginx/redirect-http-to-https.conf;"
else
	replace_in_file "/etc/nginx/server.conf" "%REDIRECT_HTTP_TO_HTTPS%" ""
fi

if [ "$USE_MODSECURITY" = "yes" ] ; then
	replace_in_file "/etc/nginx/nginx.conf" "%USE_MODSECURITY%" "include /etc/nginx/modsecurity.conf;"
	if ls /modsec-confs/*.conf > /dev/null 2>&1 ; then
		replace_in_file "/etc/nginx/modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_RULES%" "include /modsec-confs/*.conf"
	else
		replace_in_file "/etc/nginx/modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_RULES%" ""
	fi
	if [ "$USE_MODSECURITY_CRS" = "yes" ] ; then
		replace_in_file "/etc/nginx/modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CRS%" "include /etc/nginx/owasp-crs.conf"
		if ls /modsec-crs-confs/*.conf > /dev/null 2>&1 ; then
			replace_in_file "/etc/nginx/modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_CRS%" "include /modsec-crs-confs/*.conf"
		else
			replace_in_file "/etc/nginx/modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_CRS%" ""
		fi
		replace_in_file "/etc/nginx/modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CRS_RULES%" "include /etc/nginx/owasp-crs/*.conf"
	else
		replace_in_file "/etc/nginx/modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CRS%" ""
		replace_in_file "/etc/nginx/modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CUSTOM_CRS%" ""
		replace_in_file "/etc/nginx/modsecurity-rules.conf" "%MODSECURITY_INCLUDE_CRS_RULES%" ""
	fi
else
	replace_in_file "/etc/nginx/nginx.conf" "%USE_MODSECURITY%" ""
fi

ERRORS=""
for var in $(env) ; do
	var_name=$(echo "$var" | cut -d '=' -f 1 | cut -d '_' -f 1)
	if [ "z${var_name}" = "zERROR" ] ; then
		err_code=$(echo "$var" | cut -d '=' -f 1 | cut -d '_' -f 2)
		err_page=$(echo "$var" | cut -d '=' -f 2)
		cp /opt/confs/error.conf /etc/nginx/error-${err_code}.conf
		replace_in_file "/etc/nginx/error-${err_code}.conf" "%CODE%" "$err_code"
		replace_in_file "/etc/nginx/error-${err_code}.conf" "%PAGE%" "$err_page"
		ERRORS="${ERRORS}include /etc/nginx/error-${err_code}.conf;\n"
	fi
done
if [ "$ERRORS" != "" ] ; then
	replace_in_file "/etc/nginx/server.conf" "%ERRORS%" "$ERRORS"
else
	replace_in_file "/etc/nginx/server.conf" "%ERRORS%" ""
fi
if [ "$CONTENT_SECURITY_POLICY" != "" ] ; then
        replace_in_file "/etc/nginx/server.conf" "%CONTENT_SECURITY_POLICY%" "include /etc/nginx/content-security-policy.conf;"
        replace_in_file "/etc/nginx/content-security-policy.conf" "%CONTENT_SECURITY_POLICY%" "$CONTENT_SECURITY_POLICY"
else
        replace_in_file "/etc/nginx/server.conf" "%CONTENT_SECURITY_POLICY%" ""
fi
if [ "$COOKIE_FLAGS" != "" ] ; then
        replace_in_file "/etc/nginx/server.conf" "%COOKIE_FLAGS%" "include /etc/nginx/cookie-flags.conf;"
        replace_in_file "/etc/nginx/cookie-flags.conf" "%COOKIE_FLAGS%" "$COOKIE_FLAGS"
else
        replace_in_file "/etc/nginx/server.conf" "%COOKIE_FLAGS%" ""
fi
if [ "$SERVE_FILES" = "yes" ] ; then
        replace_in_file "/etc/nginx/server.conf" "%SERVE_FILES%" "include /etc/nginx/serve-files.conf;"
else
        replace_in_file "/etc/nginx/server.conf" "%SERVE_FILES%" ""
fi

# fail2ban setup
if [ "$USE_FAIL2BAN" = "yes" ] ; then
	echo "" > /etc/nginx/fail2ban-ip.conf
	rm -rf /etc/fail2ban/jail.d/*
	replace_in_file "/etc/nginx/server.conf" "%USE_FAIL2BAN%" "include /etc/nginx/fail2ban-ip.conf;"
	cp /opt/fail2ban/nginx-action.local /etc/fail2ban/action.d/nginx-action.local
	cp /opt/fail2ban/nginx-filter.local /etc/fail2ban/filter.d/nginx-filter.local
	cp /opt/fail2ban/jail.local /etc/fail2ban/jail.local
	replace_in_file "/etc/fail2ban/jail.local" "%FAIL2BAN_BANTIME%" "$FAIL2BAN_BANTIME"
	replace_in_file "/etc/fail2ban/jail.local" "%FAIL2BAN_FINDTIME%" "$FAIL2BAN_FINDTIME"
	replace_in_file "/etc/fail2ban/jail.local" "%FAIL2BAN_MAXRETRY%" "$FAIL2BAN_MAXRETRY"
	replace_in_file "/etc/fail2ban/filter.d/nginx-filter.local" "%FAIL2BAN_STATUS_CODES%" "$FAIL2BAN_STATUS_CODES"
else
	replace_in_file "/etc/nginx/server.conf" "%USE_FAIL2BAN%" ""
fi

# clamav setup
if [ "$USE_CLAMAV_UPLOAD" = "yes" ] || [ "$USE_CLAMAV_SCAN" = "yes" ] ; then
	echo "[*] Updating clamav ..."
	freshclam > /dev/null 2>&1
	echo "0 0 * * * /usr/bin/freshclam > /dev/null 2>&1" >> /etc/crontabs/root
fi
if [ "$USE_CLAMAV_UPLOAD" = "yes" ] ; then
	replace_in_file "/etc/nginx/modsecurity-rules.conf" "%USE_CLAMAV_UPLOAD%" "include /etc/nginx/modsecurity-clamav.conf"
else
	replace_in_file "/etc/nginx/modsecurity-rules.conf" "%USE_CLAMAV_UPLOAD%" ""
fi
if [ "$USE_CLAMAV_SCAN" = "yes" ] ; then
	if [ "$USE_CLAMAV_SCAN_REMOVE" = "yes" ] ; then
		echo "0 */1 * * * /usr/bin/clamscan -r -i --no-summary --remove / >> /var/log/clamav.log 2> /dev/null" >> /etc/crontabs/root
	else
		echo "0 */1 * * * /usr/bin/clamscan -r -i --no-summary / >> /var/log/clamav.log 2> /dev/null" >> /etc/crontabs/root
	fi
fi

# edit access if needed
if [ "$WRITE_ACCESS" = "yes" ] ; then
	chown -R root:nginx /www
	chmod g+w -R /www
fi

# start PHP
if [ "$USE_PHP" = "yes" ] ; then
	replace_in_file "/etc/php7/php-fpm.d/www.conf" "user = nobody" "user = nginx"
	replace_in_file "/etc/php7/php-fpm.d/www.conf" "group = nobody" "group = nginx"
	php-fpm7
fi

# start crond
crond

# start nginx
echo "[*] Running nginx ..."
/usr/sbin/nginx

# start fail2ban
if [ "$USE_FAIL2BAN" = "yes" ] ; then
	fail2ban-server > /dev/null
fi

# display logs
tail -f /var/log/access.log &
wait $!

# sigterm trapped
echo "[*] bunkerized-nginx stopped"
exit 0
