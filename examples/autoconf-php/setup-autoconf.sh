#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

chown -R 101:101 bw-data
find ./bw-data/ -type f -exec chmod 0644 {} \;
find ./bw-data/ -type d -exec chmod 0755 {} \;
chown -R 101:33 ./bw-data/www
find ./bw-data/www -type f -exec chmod 0664 {} \;
find ./bw-data/www -type d -exec chmod 0775 {} \;
