#!/bin/bash

set -e

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

# The distro's own mariadb-server (tests/linux/Dockerfile-<distro>), matching how php-fpm itself
# is provisioned there: a package baked into the image, activated here. Same db/user/password
# convention as docker-compose.yml's mydb service so the example is documented consistently.
systemctl enable --now mariadb
for _ in $(seq 1 30) ; do
	mysqladmin ping --silent && break
	sleep 1
done
if ! mysqladmin ping --silent ; then
	echo "❌ mariadb never came up"
	exit 1
fi
mysql -u root <<'SQL'
CREATE DATABASE IF NOT EXISTS wp;
CREATE USER IF NOT EXISTS 'user'@'localhost' IDENTIFIED BY 'db-user-pwd';
GRANT ALL PRIVILEGES ON wp.* TO 'user'@'localhost';
FLUSH PRIVILEGES;
SQL

curl https://wordpress.org/latest.tar.gz -Lo /tmp/wordpress.tar.gz
tar -xzf /tmp/wordpress.tar.gz -C /tmp
cp -r /tmp/wordpress/* /var/www/html

cp /var/www/html/wp-config-sample.php /var/www/html/wp-config.php
# DB_HOST stays "localhost": mysqli treats that value as "connect via the local socket", which
# is what mariadb.service listens on -- no TCP port dependency to add.
sed -i \
	-e "s/database_name_here/wp/" \
	-e "s/username_here/user/" \
	-e "s/password_here/db-user-pwd/" \
	/var/www/html/wp-config.php

chown -R $user:nginx /var/www/html
find /var/www/html -type f -exec chmod 0640 {} \;
find /var/www/html -type d -exec chmod 0750 {} \;
