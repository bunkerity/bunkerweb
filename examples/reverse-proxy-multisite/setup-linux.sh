#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

mkdir /opt/bunkerweb/www/{app1.example.com,app2.example.com}
echo "hello" > /opt/bunkerweb/www/app1.example.com/index.html
echo "hello" > /opt/bunkerweb/www/app2.example.com/index.html
