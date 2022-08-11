#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

chown -R www-data:nginx ./bw-data/www
find ./bw-data/www -type f -exec chmod 0640 {} \;
find ./bw-data/www -type d -exec chmod 0750 {} \;
cp -rp ./bw-data/www/* /opt/bunkerweb/www
