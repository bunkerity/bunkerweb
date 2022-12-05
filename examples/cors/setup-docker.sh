#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

chown -R root:101 bw-data
chmod -R 770 bw-data
chown -R 82:101 ./bw-data/www
find ./bw-data/www -type f -exec chmod 0640 {} \;
find ./bw-data/www -type d -exec chmod 0750 {} \;