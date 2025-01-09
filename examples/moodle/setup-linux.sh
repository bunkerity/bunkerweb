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
curl https://download.moodle.org/download.php/stable404/moodle-latest-404.tgz -Lo /tmp/moodle.tgz
tar -xzf /tmp/moodle.tgz -C /tmp
cp -r /tmp/moodle/* /var/www/html
chown -R $user:nginx /var/www/html
find /var/www/html -type f -exec chmod 0640 {} \;
find /var/www/html -type d -exec chmod 0750 {} \;
