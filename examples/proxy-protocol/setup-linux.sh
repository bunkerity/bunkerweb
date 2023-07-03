#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

DNF=$(which dnf)
APT=$(which apt)

if [ ! -z $DNF ] ; then
	dnf install -y haproxy
elif [ ! -z $APT ] ; then
	apt install -y haproxy
fi

cp haproxy.cfg /etc/haproxy
sed -i "s/*:8080/*:80/g" /etc/haproxy/haproxy.cfg
sed -i "s/*:8443/*:443/g" /etc/haproxy/haproxy.cfg
sed -i "s/mybunker/127.0.0.1/g" /etc/haproxy/haproxy.cfg
systemctl stop bunkerweb
systemctl stop haproxy
systemctl start haproxy

echo "hello" > /var/www/html/index.html
