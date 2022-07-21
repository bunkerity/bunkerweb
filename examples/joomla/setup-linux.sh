#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

curl https://downloads.joomla.org/fr/cms/joomla4/4-1-5/Joomla_4-1-5-Stable-Full_Package.zip?format=zip -Lo /tmp/joomla.zip
unzip /tmp/joomla.zip -d /opt/bunkerweb/www
chown -R www-data:nginx /opt/bunkerweb/www
find /opt/bunkerweb/www -type d -exec chmod 750 /opt/bunkerweb/www {} \;
find /opt/bunkerweb/www -type f -exec chmod 640 /opt/bunkerweb/www {} \;
systemctl start php-fpm
cp variables.env /opt/bunkerweb/variables.env