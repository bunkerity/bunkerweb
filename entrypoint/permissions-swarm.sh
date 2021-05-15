#!/bin/bash

# /etc/letsencrypt
if [ ! -r "/etc/letsencrypt" ] || [ ! -x "/etc/letsencrypt" ] ; then
	echo "[!] WARNING - wrong permissions on /etc/letsencrypt"
	exit 1
fi

# /www
if [ ! -r "/www" ] || [ ! -x "/www" ] ; then
	echo "[!] ERROR - wrong permissions on /www"
	exit 2
fi

# /modsec-confs
if [ ! -r "/modsec-confs" ] || [ ! -x "/modsec-confs" ] ; then
	echo "[!] ERROR - wrong permissions on /modsec-confs"
	exit 3
fi
# /modsec-crs-confs
if [ ! -r "/modsec-crs-confs" ] || [ ! -x "/modsec-crs-confs" ] ; then
	echo "[!] ERROR - wrong permissions on /modsec-crs-confs"
	exit 4
fi
# /server-confs
if [ ! -r "/server-confs" ] || [ ! -x "/server-confs" ] ; then
	echo "[!] ERROR - wrong permissions on /server-confs"
	exit 5
fi
# /http-confs
if [ ! -r "/http-confs" ] || [ ! -x "/http-confs" ] ; then
	echo "[!] ERROR - wrong permissions on /http-confs"
	exit 6
fi

# /etc/nginx
if [ ! -r "/etc/nginx" ] || [ ! -x "/etc/nginx" ] ; then
	echo "[!] ERROR - wrong permissions on /etc/nginx"
	exit 7
fi

# /acme-challenge
if [ ! -r "/acme-challenge" ] || [ ! -x "/acme-challenge" ] ; then
	echo "[!] ERROR - wrong permissions on /acme-challenge"
	exit 8
fi

