#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

mkdir elasticsearch-data
chown 1001:1001 elasticsearch-data
chmod 770 elasticsearch-data
