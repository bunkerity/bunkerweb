#!/bin/sh

certbot renew

if [ -f /run/nginx/nginx.pid ] ; then
	/usr/sbin/nginx -s reload
fi
