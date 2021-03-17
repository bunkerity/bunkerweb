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
	if [ -f "/cache/map-user-agent.conf" ] ; then
		echo "[*] Copying cached map-user-agent.conf ..."
		cp /cache/map-user-agent.conf /etc/nginx/map-user-agent.conf
	else
		echo "[*] Downloading bad user-agent list (in background) ..."
		/opt/scripts/user-agents.sh > /dev/null 2>&1 &
	fi
fi

# Referrers
if [ "$(has_value BLOCK_REFERRER yes)" != "" ] ; then
	if [ -f "/cache/map-referrer.conf" ] ; then
		echo "[*] Copying cached map-referrer.conf ..."
		cp /cache/map-referrer.conf /etc/nginx/map-referrer.conf
	else
		echo "[*] Downloading bad referrer list (in background) ..."
		/opt/scripts/referrers.sh > /dev/null 2>&1 &
	fi
fi

# exit nodes
if [ "$(has_value BLOCK_TOR_EXIT_NODE yes)" != "" ] ; then
	if [ -f "/cache/block-tor-exit-node.conf" ] ; then
		echo "[*] Copying cached block-tor-exit-node.conf ..."
		cp /cache/block-tor-exit-node.conf /etc/nginx/block-tor-exit-node.conf
	else
		echo "[*] Downloading tor exit nodes list (in background) ..."
		/opt/scripts/exit-nodes.sh > /dev/null 2>&1 &
	fi
fi

# proxies
if [ "$(has_value BLOCK_PROXIES yes)" != "" ] ; then
	if [ -f "/cache/block-proxies.conf" ] ; then
		echo "[*] Copying cached block-proxies.conf ..."
		cp /cache/block-proxies.conf /etc/nginx/block-proxies.conf
	else
		echo "[*] Downloading proxies list (in background) ..."
		/opt/scripts/proxies.sh > /dev/null 2>&1 &
	fi
fi

# abusers
if [ "$(has_value BLOCK_ABUSERS yes)" != "" ] ; then
	if [ -f "/cache/block-abusers.conf" ] ; then
		echo "[*] Copying cached block-abusers.conf ..."
		cp /cache/block-abusers.conf /etc/nginx/block-abusers.conf
	else
		echo "[*] Downloading abusers list (in background) ..."
		/opt/scripts/abusers.sh > /dev/null 2>&1 &
	fi
fi
