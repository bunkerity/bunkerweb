#!/bin/bash

if [ "$(id -u)" -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

chown -R 33:101 ./www
find ./www -type f -exec chmod 0640 {} \;
find ./www -type d -exec chmod 0750 {} \;
