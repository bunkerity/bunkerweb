#!/bin/bash

if [ "$(id -u)" -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

cp -r bw-data/configs/* /etc/bunkerweb/configs

curl https://github.com/authelia/authelia/releases/download/v4.36.2/authelia-v4.36.2-linux-amd64.tar.gz -Lo /tmp/authelia.tar.gz
tar -xzf /tmp/authelia.tar.gz -C /tmp
mv /tmp/authelia-linux-amd64 /usr/bin/authelia
mv /tmp/authelia.service /etc/systemd/system
mkdir /etc/authelia
cp ./authelia/* /etc/authelia
sed -i "s@/config/@/etc/authelia/@g" /etc/authelia/configuration.yml
sed -i "s@redis:@@g" /etc/authelia/configuration.yml
sed -i "s@host: redis@@g" /etc/authelia/configuration.yml
sed -i "s@port: 6379@@g" /etc/authelia/configuration.yml
systemctl daemon-reload
systemctl start authelia
