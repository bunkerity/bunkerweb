#!/bin/bash

# /etc/letsencrypt
if [ ! -w "/etc/letsencrypt" ] || [ ! -r "/etc/letsencrypt" ] || [ ! -x "/etc/letsencrypt" ] ; then
	echo "[!] ERROR - wrong permissions on /etc/letsencrypt"
	exit 1
fi

if [ -f "/usr/sbin/nginx" ] ; then
	# /www
	if [ ! -r "/www" ] || [ ! -x "/www" ] ; then
		echo "[!] ERROR - wrong permissions on /www"
		exit 1
	fi
	# /server-confs
	if [ ! -r "/server-confs" ] || [ ! -x "/server-confs" ] ; then
		echo "[!] ERROR - wrong permissions on /server-confs"
		exit 1
	fi
	# /http-confs
	if [ ! -r "/http-confs" ] || [ ! -x "/http-confs" ] ; then
		echo "[!] ERROR - wrong permissions on /http-confs"
		exit 1
	fi
fi

# /modsec-confs
if [ ! -r "/modsec-confs" ] || [ ! -x "/modsec-confs" ] ; then
	echo "[!] ERROR - wrong permissions on /modsec-confs"
	exit 1
fi

# /modsec-crs-confs
if [ ! -r "/modsec-crs-confs" ] || [ ! -x "/modsec-crs-confs" ] ; then
	echo "[!] ERROR - wrong permissions on /modsec-crs-confs"
	exit 1
fi

# /acme-challenge
if [ ! -w "/acme-challenge" ] || [ ! -r "/acme-challenge" ] || [ ! -x "/acme-challenge" ] ; then
	echo "[!] ERROR - wrong permissions on /acme-challenge"
	exit 1
fi

# /etc/nginx
if [ ! -w "/etc/nginx" ] || [ ! -r "/etc/nginx" ] || [ ! -x "/etc/nginx" ] ; then
	echo "[!] ERROR - wrong permissions on /etc/nginx"
	exit 1
fi
