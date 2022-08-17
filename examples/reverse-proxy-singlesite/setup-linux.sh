#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

mkdir /opt/bunkerweb/www/{app1,app2}
echo "hello" > /opt/bunkerweb/www/app1/index.html
echo "hello" > /opt/bunkerweb/www/app2/index.html
cp -r bw-data/configs/* /opt/bunkerweb/configs
