#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

mkdir /var/www/html/{app1.example.com,app2.example.com}
echo "hello" > /var/www/html/app1.example.com/index.html
echo "hello" > /var/www/html/app2.example.com/index.html
