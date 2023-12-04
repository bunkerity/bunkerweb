#!/bin/bash

if [ "$(id -u)" -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

DNF=$(which dnf)
APT=$(which apt)

if [ -n "$DNF" ] ; then
	dnf install -y haproxy
elif [ -n "$APT" ] ; then
	apt install -y haproxy
fi

cp haproxy.cfg /etc/haproxy
sed -i "s/*:8080/*:80/" /etc/haproxy/haproxy.cfg
sed -i "s/mybunker/127.0.0.1/" /etc/haproxy/haproxy.cfg
systemctl stop bunkerweb
sleep 10
systemctl stop haproxy
systemctl start haproxy
if [ $? -ne 0 ] ; then
	systemctl status haproxy
	journalctl -u haproxy.service
fi

echo "hello" > /var/www/html/index.html
