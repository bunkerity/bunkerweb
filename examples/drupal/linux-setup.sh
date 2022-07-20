#!/bin/bash

if [ $(id -u) -ne 0 ] ; then
	echo "❌ Run me as root"
	exit 1
fi

curl https://ftp.drupal.org/files/projects/drupal-9.4.2.tar.gz -Lo /tmp/drupal.tar.gz
tar -xvzf /tmp/drupal.tar.gz -C /tmp
cp -r /tmp/drupal-9.4.2/* /opt/bunkerweb/www
chown -R www-data:nginx /opt/bunkerweb/www
find /opt/bunkerweb/www -type d -exec chmod 750 /opt/bunkerweb/www {} \;
find /opt/bunkerweb/www -type f -exec chmod 640 /opt/bunkerweb/www {} \;

systemctl start php-fpm