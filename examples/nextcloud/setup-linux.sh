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
CREATE DATABASE IF NOT EXISTS nc;
CREATE USER IF NOT EXISTS 'user'@'localhost' IDENTIFIED BY 'db-user-pwd';
GRANT ALL PRIVILEGES ON nc.* TO 'user'@'localhost';
FLUSH PRIVILEGES;
SQL

curl https://download.nextcloud.com/server/releases/latest.zip -Lo /tmp/nextcloud.zip
unzip -qq /tmp/nextcloud.zip -d /tmp
cp -r /tmp/nextcloud/* /var/www/html

# Nextcloud's own unattended-install mechanism: index.php runs OC\Setup from this file on the
# first request, against the local socket ("localhost" as dbhost, same as wp-config.php's
# DB_HOST), then deletes it -- no separate `occ` invocation needed.
cat > /var/www/html/config/autoconfig.php <<'PHP'
<?php
$AUTOCONFIG = array(
  'dbtype' => 'mysql',
  'dbname' => 'nc',
  'dbuser' => 'user',
  'dbpass' => 'db-user-pwd',
  'dbhost' => 'localhost',
  'dbtableprefix' => 'oc_',
  'adminlogin' => 'admin',
  'adminpass' => 'changeme',
  'directory' => '/var/www/html/data',
);
PHP

chown -R $user:nginx /var/www/html
find /var/www/html -type f -exec chmod 0640 {} \;
find /var/www/html -type d -exec chmod 0750 {} \;
