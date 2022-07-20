#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

chown -R 101:101 bw-data
find ./bw-data/ -type f -exec chmod 0640 {} \;
find ./bw-data/ -type d -exec chmod 0750 {} \;
chown -R 101:33 ./bw-data/www
find ./bw-data/www -type f -exec chmod 0660 {} \;
find ./bw-data/www -type d -exec chmod 0770 {} \;