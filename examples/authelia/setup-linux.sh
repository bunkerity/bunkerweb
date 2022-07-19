#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

curl https://github.com/authelia/authelia/releases/download/v4.36.2/authelia-v4.36.2-linux-amd64.tar.gz -Lo /tmp/authelia.tar.gz
cd /tmp/
tar -xvzf authelia.tar.gz
mv authelia-linux-amd64 /usr/bin/authelia
mv authelia.service /etc/systemd/system
mkdir /etc/authelia
cp ./authelia/* /etc/authelia
sed -i "s@/config/@/etc/authelia/@g" /etc/authelia/configuration.yml
systemctl daemon-reload
systemctl start authelia
cp variables.env /opt/bunkerweb/variables.env