#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

chown -R root:101 bw-data
find ./bw-data -type f -exec chmod 0660 {} \;
find ./bw-data -type d -exec chmod 0770 {} \;