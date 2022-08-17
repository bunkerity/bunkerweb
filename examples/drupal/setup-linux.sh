#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

if id www-data > /dev/null 2>&1 ; then
	user="www-data"
elif id apache > /dev/null 2>&1 ; then
	user="apache"
else
	echo "❌ No PHP user found"
	exit 1
fi
curl https://www.drupal.org/download-latest/tar.gz -Lo /tmp/drupal.tar.gz
tar -xzf /tmp/drupal.tar.gz -C /tmp
current_dir="$(pwd)"
cd /tmp/drupal-*
cp -r * /opt/bunkerweb/www
chown -R $user:nginx /opt/bunkerweb/www
find /opt/bunkerweb/www -type f -exec chmod 0640 {} \;
find /opt/bunkerweb/www -type d -exec chmod 0750 {} \;
cd "$current_dir"
cp -r ./bw-data/configs/* /opt/bunkerweb/configs
chown -R nginx:nginx /opt/bunkerweb/configs
