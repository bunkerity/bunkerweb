#!/bin/bash

# load some functions
. /opt/entrypoint/utils.sh

# self signed certs for sites
files=$(has_value GENERATE_SELF_SIGNED_SSL yes)
if [ "$files" != " " ] ; then
	for file in $files ; do
		site=$(echo $file | cut -f 4 -d '/')
		dest="/etc/nginx/"
		if [ "$site" != "site.env" ] ; then
			dest="${dest}/${site}/"
		fi
		SELF_SIGNED_SSL_EXPIRY="$(sed -nE 's/^SELF_SIGNED_SSL_EXPIRY=(.*)$/\1/p' $file)"
		SELF_SIGNED_SSL_COUNTRY="$(sed -nE 's/^SELF_SIGNED_SSL_COUNTRY=(.*)$/\1/p' $file)"
		SELF_SIGNED_SSL_STATE="$(sed -nE 's/^SELF_SIGNED_SSL_STATE=(.*)$/\1/p' $file)"
		SELF_SIGNED_SSL_CITY="$(sed -nE 's/^SELF_SIGNED_SSL_CITY=(.*)$/\1/p' $file)"
		SELF_SIGNED_SSL_ORG="$(sed -nE 's/^SELF_SIGNED_SSL_ORG=(.*)$/\1/p' $file)"
		SELF_SIGNED_SSL_OU="$(sed -nE 's/^SELF_SIGNED_SSL_OU=(.*)$/\1/p' $file)"
		SELF_SIGNED_SSL_CN="$(sed -nE 's/^SELF_SIGNED_SSL_CN=(.*)$/\1/p' $file)"
		openssl_output=$(openssl req -nodes -x509 -newkey rsa:4096 -keyout ${dest}self-key.pem -out ${dest}self-cert.pem -days $SELF_SIGNED_SSL_EXPIRY -subj "/C=$SELF_SIGNED_SSL_COUNTRY/ST=$SELF_SIGNED_SSL_STATE/L=$SELF_SIGNED_SSL_CITY/O=$SELF_SIGNED_SSL_ORG/OU=$SELF_SIGNED_SSL_OU/CN=$SELF_SIGNED_SSL_CN" 2>&1)
		if [ $? -eq 0 ] ; then
			echo "[*] Generated self-signed certificate ${dest}self-cert.pem with key ${dest}self-key.pem"
		else
			echo "[!] Error while generating self-signed certificate : $openssl_output"
		fi
	done
fi

# self signed cert for default server
if [ "$(has_value AUTO_LETS_ENCRYPT yes)" != "" ] || [ "$(has_value GENERATE_SELF_SIGNED_SSL yes)" != "" ] || [ "$(has_value USE_CUSTOM_HTTPS yes)" != "" ] ; then
	SELF_SIGNED_SSL_EXPIRY="999"
	SELF_SIGNED_SSL_COUNTRY="US"
	SELF_SIGNED_SSL_STATE="Utah"
	SELF_SIGNED_SSL_CITY="Lehi"
	SELF_SIGNED_SSL_ORG="Your Company, Inc."
	SELF_SIGNED_SSL_OU="IT"
	SELF_SIGNED_SSL_CN="www.yourdomain.com"
	openssl_output=$(openssl req -nodes -x509 -newkey rsa:4096 -keyout /etc/nginx/default-key.pem -out /etc/nginx/default-cert.pem -days $SELF_SIGNED_SSL_EXPIRY -subj "/C=$SELF_SIGNED_SSL_COUNTRY/ST=$SELF_SIGNED_SSL_STATE/L=$SELF_SIGNED_SSL_CITY/O=$SELF_SIGNED_SSL_ORG/OU=$SELF_SIGNED_SSL_OU/CN=$SELF_SIGNED_SSL_CN" 2>&1)
	if [ $? -eq 0 ] ; then
		echo "[*] Generated self-signed certificate for default server"
	else
		echo "[!] Error while generating self-signed certificate for default server : $openssl_output"
	fi
fi

# certbot
files=$(has_value AUTO_LETS_ENCRYPT yes)
if [ "$files" != " " ] ; then
	for file in $files ; do
		if [ "$(echo "$file" | grep 'site.env$')" = "" ] ; then
			continue
		fi
		SERVER_NAME="$(sed -nE 's/^SERVER_NAME=(.*)$/\1/p' $file)"
		FIRST_SERVER="$(echo $SERVER_NAME | cut -d ' ' -f 1)"
		EMAIL_LETS_ENCRYPT="$(sed -nE 's/^EMAIL_LETS_ENCRYPT=(.*)$/\1/p' $file)"
		if [ "$EMAIL_LETS_ENCRYPT" = "" ] ; then
			EMAIL_LETS_ENCRYPT="contact@${FIRST_SERVER}"
		fi
		certbot_outpout=$(/opt/scripts/certbot-new.sh "$(echo -n $SERVER_NAME | sed 's/ /,/g')" "$EMAIL_LETS_ENCRYPT" 2>&1)
		if [ $? -eq 0 ] ; then
			echo "[*] Certbot new successfully executed"
		else
			echo "[*] Error while executing certbot new : $certbot_output"
		fi
	done
fi


# GeoIP
if [ "$(has_value BLACKLIST_COUNTRY .+)" != "" ] || [ "$(has_value WHITELIST_COUNTRY .+)" != "" ] ; then
	if [ -f "/cache/geoip.mmdb" ] ; then
		echo "[*] Copying cached geoip.mmdb ..."
		cp /cache/geoip.mmdb /etc/nginx/geoip.mmdb
	elif [ "$(ps aux | grep "geoip\.sh")" = "" ] ; then
		echo "[*] Downloading GeoIP database ..."
		/opt/scripts/geoip.sh > /dev/null 2>&1
	fi
fi

# User-Agents
if [ "$(has_value BLOCK_USER_AGENT yes)" != "" ] ; then
	if [ -f "/cache/user-agents.list" ] && [ "$(wc -l /cache/user-agents.list | cut -d ' ' -f 1)" -gt 1 ] ; then
		echo "[*] Copying cached user-agents.list ..."
		cp /cache/user-agents.list /etc/nginx/user-agents.list
	elif [ "$(ps aux | grep "user-agents\.sh")" = "" ] ; then
		echo "[*] Downloading bad user-agent list (in background) ..."
		/opt/scripts/user-agents.sh > /dev/null 2>&1 &
	fi
fi

# Referrers
if [ "$(has_value BLOCK_REFERRER yes)" != "" ] ; then
	if [ -f "/cache/referrers.list" ] && [ "$(wc -l /cache/referrers.list | cut -d ' ' -f 1)" -gt 1 ] ; then
		echo "[*] Copying cached referrers.list ..."
		cp /cache/referrers.list /etc/nginx/referrers.list
	elif [ "$(ps aux | grep "referrers\.sh")" = "" ] ; then
		echo "[*] Downloading bad referrer list (in background) ..."
		/opt/scripts/referrers.sh > /dev/null 2>&1 &
	fi
fi

# exit nodes
if [ "$(has_value BLOCK_TOR_EXIT_NODE yes)" != "" ] ; then
	if [ -f "/cache/tor-exit-nodes.list" ] && [ "$(wc -l /cache/tor-exit-nodes.list | cut -d ' ' -f 1)" -gt 1 ] ; then
		echo "[*] Copying cached tor-exit-nodes.list ..."
		cp /cache/tor-exit-nodes.list /etc/nginx/tor-exit-nodes.list
	elif [ "$(ps aux | grep "exit-nodes\.sh")" = "" ] ; then
		echo "[*] Downloading tor exit nodes list (in background) ..."
		/opt/scripts/exit-nodes.sh > /dev/null 2>&1 &
	fi
fi

# proxies
if [ "$(has_value BLOCK_PROXIES yes)" != "" ] ; then
	if [ -f "/cache/proxies.list" ] && [ "$(wc -l /cache/proxies.list | cut -d ' ' -f 1)" -gt 1 ] ; then
		echo "[*] Copying cached proxies.list ..."
		cp /cache/proxies.list /etc/nginx/proxies.list
	elif [ "$(ps aux | grep "proxies\.sh")" = "" ] ; then
		echo "[*] Downloading proxies list (in background) ..."
		/opt/scripts/proxies.sh > /dev/null 2>&1 &
	fi
fi

# abusers
if [ "$(has_value BLOCK_ABUSERS yes)" != "" ] ; then
	if [ -f "/cache/abusers.list" ] && [ "$(wc -l /cache/abusers.list | cut -d ' ' -f 1)" -gt 1 ] ; then
		echo "[*] Copying cached abusers.list ..."
		cp /cache/abusers.list /etc/nginx/abusers.list
	elif [ "$(ps aux | grep "abusers\.sh")" = "" ] ; then
		echo "[*] Downloading abusers list (in background) ..."
		/opt/scripts/abusers.sh > /dev/null 2>&1 &
	fi
fi
