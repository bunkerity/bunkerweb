#!/bin/bash

if [ "$(id -u)" -ne 0 ] ; then
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
curl https://ftp.drupal.org/files/projects/drupal-10.2.6.tar.gz -Lo /tmp/drupal.tar.gz
tar -xzf /tmp/drupal.tar.gz -C /tmp
current_dir="$(pwd)"
cd /tmp/drupal-* || exit 1
cp -r ./* /var/www/html
chown -R $user:nginx /var/www/html
find /var/www/html -type f -exec chmod 0640 {} \;
find /var/www/html -type d -exec chmod 0750 {} \;
cd "$current_dir" || exit 1
cp -r ./bw-data/configs/* /etc/bunkerweb/configs
chown -R nginx:nginx /etc/bunkerweb/configs
