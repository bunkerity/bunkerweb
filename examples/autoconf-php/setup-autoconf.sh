#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

chown -R 101:33 ./www
find ./www -type f -exec chmod 0660 {} \;
find ./www -type d -exec chmod 0770 {} \;