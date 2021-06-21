#!/bin/bash

# load some functions
. /opt/bunkerized-nginx/entrypoint/utils.sh

# User-Agents
if [ "$(has_value BLOCK_USER_AGENT yes)" != "" ] ; then
	if [ -f "/cache/user-agents.list" ] && [ "$(wc -l /cache/user-agents.list | cut -d ' ' -f 1)" -gt 1 ] ; then
		echo "[*] Copying cached user-agents.list ..."
		cp /opt/bunkerized-nginx/cache/user-agents.list /etc/nginx/user-agents.list
	elif [ "$(ps aux | grep "user-agents\.sh")" = "" ] ; then
		echo "[*] Downloading bad user-agent list (in background) ..."
		/opt/bunkerized-nginx/scripts/user-agents.sh > /dev/null 2>&1 &
	fi
fi

# Referrers
if [ "$(has_value BLOCK_REFERRER yes)" != "" ] ; then
	if [ -f "/cache/referrers.list" ] && [ "$(wc -l /cache/referrers.list | cut -d ' ' -f 1)" -gt 1 ] ; then
		echo "[*] Copying cached referrers.list ..."
		cp /opt/bunkerized-nginx/cache/referrers.list /etc/nginx/referrers.list
	elif [ "$(ps aux | grep "referrers\.sh")" = "" ] ; then
		echo "[*] Downloading bad referrer list (in background) ..."
		/opt/bunkerized-nginx/scripts/referrers.sh > /dev/null 2>&1 &
	fi
fi

# exit nodes
if [ "$(has_value BLOCK_TOR_EXIT_NODE yes)" != "" ] ; then
	if [ -f "/cache/tor-exit-nodes.list" ] && [ "$(wc -l /cache/tor-exit-nodes.list | cut -d ' ' -f 1)" -gt 1 ] ; then
		echo "[*] Copying cached tor-exit-nodes.list ..."
		cp /opt/bunkerized-nginx/cache/tor-exit-nodes.list /etc/nginx/tor-exit-nodes.list
	elif [ "$(ps aux | grep "exit-nodes\.sh")" = "" ] ; then
		echo "[*] Downloading tor exit nodes list (in background) ..."
		/opt/bunkerized-nginx/scripts/exit-nodes.sh > /dev/null 2>&1 &
	fi
fi

# proxies
if [ "$(has_value BLOCK_PROXIES yes)" != "" ] ; then
	if [ -f "/cache/proxies.list" ] && [ "$(wc -l /cache/proxies.list | cut -d ' ' -f 1)" -gt 1 ] ; then
		echo "[*] Copying cached proxies.list ..."
		cp /opt/bunkerized-nginx/cache/proxies.list /etc/nginx/proxies.list
	elif [ "$(ps aux | grep "proxies\.sh")" = "" ] ; then
		echo "[*] Downloading proxies list (in background) ..."
		/opt/bunkerized-nginx/scripts/proxies.sh > /dev/null 2>&1 &
	fi
fi

# abusers
if [ "$(has_value BLOCK_ABUSERS yes)" != "" ] ; then
	if [ -f "/cache/abusers.list" ] && [ "$(wc -l /cache/abusers.list | cut -d ' ' -f 1)" -gt 1 ] ; then
		echo "[*] Copying cached abusers.list ..."
		cp /opt/bunkerized-nginx/cache/abusers.list /etc/nginx/abusers.list
	elif [ "$(ps aux | grep "abusers\.sh")" = "" ] ; then
		echo "[*] Downloading abusers list (in background) ..."
		/opt/bunkerized-nginx/scripts/abusers.sh > /dev/null 2>&1 &
	fi
fi
