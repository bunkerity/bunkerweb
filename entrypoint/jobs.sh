#!/bin/bash

# load default values
. ./opt/entrypoint/defaults.sh

# load some functions
. /opt/entrypoint/utils.sh

# GeoIP
if [ "$BLACKLIST_COUNTRY" != "" ] || [ "$WHITELIST_COUNTRY" != "" ] ; then
	if [ -f "/cache/geoip.mmdb" ] ; then
		echo "[*] Copying cached geoip.mmdb ..."
		cp /cache/geoip.mmdb /etc/nginx/geoip.mmdb
	else
		echo "[*] Downloading GeoIP database (in background) ..."
		/opt/scripts/geoip.sh > /dev/null 2>&1 &
	fi
fi

# User-Agents
if [ "$(has_value BLOCK_USER_AGENT yes)" != "" ] ; then
	if [ -f "/cache/user-agents.list" ] ; then
		echo "[*] Copying cached user-agents.list ..."
		cp /cache/user-agents.list /etc/nginx/user-agents.list
	else
		echo "[*] Downloading bad user-agent list (in background) ..."
		/opt/scripts/user-agents.sh > /dev/null 2>&1 &
	fi
fi

# Referrers
if [ "$(has_value BLOCK_REFERRER yes)" != "" ] ; then
	if [ -f "/cache/referrers.list" ] ; then
		echo "[*] Copying cached referrers.list ..."
		cp /cache/referrers.list /etc/nginx/referrers.list
	else
		echo "[*] Downloading bad referrer list (in background) ..."
		/opt/scripts/referrers.sh > /dev/null 2>&1 &
	fi
fi

# exit nodes
if [ "$(has_value BLOCK_TOR_EXIT_NODE yes)" != "" ] ; then
	if [ -f "/cache/tor-exit-nodes.list" ] ; then
		echo "[*] Copying cached tor-exit-nodes.list ..."
		cp /cache/tor-exit-nodes.list /etc/nginx/tor-exit-nodes.list
	else
		echo "[*] Downloading tor exit nodes list (in background) ..."
		/opt/scripts/exit-nodes.sh > /dev/null 2>&1 &
	fi
fi

# proxies
if [ "$(has_value BLOCK_PROXIES yes)" != "" ] ; then
	if [ -f "/cache/proxies.list" ] ; then
		echo "[*] Copying cached proxies.list ..."
		cp /cache/proxies.list /etc/nginx/proxies.list
	else
		echo "[*] Downloading proxies list (in background) ..."
		/opt/scripts/proxies.sh > /dev/null 2>&1 &
	fi
fi

# abusers
if [ "$(has_value BLOCK_ABUSERS yes)" != "" ] ; then
	if [ -f "/cache/abusers.list" ] ; then
		echo "[*] Copying cached abusers.list ..."
		cp /cache/abusers.list /etc/nginx/abusers.list
	else
		echo "[*] Downloading abusers list (in background) ..."
		/opt/scripts/abusers.sh > /dev/null 2>&1 &
	fi
fi
