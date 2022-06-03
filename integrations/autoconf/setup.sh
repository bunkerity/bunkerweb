#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

if [ -d bw-data ] ; then
	mkdir bw-data
fi
chown -R root:101 bw-data
chmod -R 770 bw-data
