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
curl https://releases.mattermost.com/7.2.0/mattermost-7.2.0-linux-amd64.tar.gz -Lo /tmp/mattermost.tar.gz
tar -xzf /tmp/mattermost.tar.gz -C /tmp
cd /tmp/drupal-*
cp -r * /opt/bunkerweb/www
chown -R $user:nginx /opt/bunkerweb/www
find /opt/bunkerweb/www -type f -exec chmod 0640 {} \;
find /opt/bunkerweb/www -type d -exec chmod 0750 {} \;
cp -r bw-data/configs/* /opt/bunkerweb/configs
