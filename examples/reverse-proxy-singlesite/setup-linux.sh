#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

mkdir /var/www/html/{app1,app2}
echo "hello" > /var/www/html/app1/index.html
echo "hello" > /var/www/html/app2/index.html
cp -r bw-data/configs/* /etc/bunkerweb/configs
chown -R nginx:nginx /etc/bunkerweb/configs