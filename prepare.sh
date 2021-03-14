#!/bin/sh

# install dependencies
apk --no-cache add certbot libstdc++ libmaxminddb geoip pcre yajl fail2ban clamav apache2-utils rsyslog openssl lua libgd go jq mariadb-connector-c bash brotli

# custom entrypoint
mkdir /opt/entrypoint.d

# prepare /www
mkdir /www
chown -R root:nginx /www
chmod -R 770 /www

# prepare /opt
chown -R root:nginx /opt
find /opt -type f -exec chmod 0740 {} \;
find /opt -type d -exec chmod 0750 {} \;
chmod ugo+x /opt/entrypoint/* /opt/scripts/*
chmod 770 /opt

# prepare /etc/nginx
chown -R root:nginx /etc/nginx
chmod -R 770 /etc/nginx

# prepare /var/log
rm -f /var/log/nginx/*
chown root:nginx /var/log/nginx
touch /var/log/nginx/error.log /var/log/nginx/modsec_audit.log /var/log/jobs.log
chown nginx:nginx /var/log/nginx/*
chmod -R 770 /var/log/nginx
touch /var/log/access.log /var/log/error.log /var/log/jobs.log /var/log/fail2ban.log
chown nginx:nginx /var/log/*.log
chmod 770 /var/log/*.log

# prepare /acme-challenge
mkdir /acme-challenge
chown root:nginx /acme-challenge
chmod 770 /acme-challenge

# prepare /etc/letsencrypt
mkdir /etc/letsencrypt
chown root:nginx /etc/letsencrypt
chmod 770 /etc/letsencrypt

# prepare /etc/fail2ban
rm -rf /etc/fail2ban/jail.d/*.conf
chown -R root:nginx /etc/fail2ban
find /etc/fail2ban -type f -exec chmod 0760 {} \;
find /etc/fail2ban -type d -exec chmod 0770 {} \;

# prepare /var/run/fail2ban and /var/lib/fail2ban
chown -R root:nginx /var/run/fail2ban /var/lib/fail2ban
chmod -R 770 /var/run/fail2ban /var/lib/fail2ban

# prepare /usr/local/lib/lua
chown root:nginx /usr/local/lib/lua
chmod 770 /usr/local/lib/lua

# prepare /cache
mkdir /cache
chown root:nginx /cache
chmod 770 /cache

# prepare misc files
chown root:nginx /etc/rsyslog.conf /etc/logrotate.conf
chmod 660 /etc/rsyslog.conf /etc/logrotate.conf
chown root:nginx /etc/rsyslog.conf

# prepare /etc/crontabs/nginx
touch /etc/crontabs/nginx
chown root:nginx /etc/crontabs/nginx
chmod 660 /etc/crontabs/nginx
