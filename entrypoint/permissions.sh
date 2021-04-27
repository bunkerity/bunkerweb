#!/bin/bash

# /etc/letsencrypt
if [ ! -w "/etc/letsencrypt" ] || [ ! -r "/etc/letsencrypt" ] || [ ! -x "/etc/letsencrypt" ] ; then
	echo "[!] WARNING - wrong permissions on /etc/letsencrypt"
	exit 1
fi

if [ -f "/usr/sbin/nginx" ] ; then
	# /www
	if [ ! -r "/www" ] || [ ! -x "/www" ] ; then
		echo "[!] ERROR - wrong permissions on /www"
		exit 2
	fi

fi

# /acme-challenge
if [ ! -w "/acme-challenge" ] || [ ! -r "/acme-challenge" ] || [ ! -x "/acme-challenge" ] ; then
	echo "[!] ERROR - wrong permissions on /acme-challenge"
	exit 3
fi

# /etc/nginx
if [ ! -w "/etc/nginx" ] || [ ! -r "/etc/nginx" ] || [ ! -x "/etc/nginx" ] ; then
	echo "[!] ERROR - wrong permissions on /etc/nginx"
	exit 4
fi

