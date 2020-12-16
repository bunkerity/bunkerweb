#!/bin/sh

# install dependencies
apk --no-cache add certbot libstdc++ libmaxminddb geoip pcre yajl fail2ban clamav apache2-utils rsyslog openssl lua libgd go jq mariadb-connector-c bash brotli

# make scripts executable
chmod +x /opt/entrypoint/* /opt/scripts/*
mkdir /opt/entrypoint.d

# log files/folders rights
rm -f /var/log/nginx/*
chown root:nginx /var/log/nginx
chmod 750 /var/log/nginx
touch /var/log/nginx/error.log /var/log/nginx/modsec_audit.log /var/log/jobs.log
chown nginx:nginx /var/log/nginx/*.log

# let's encrypt webroot
mkdir /acme-challenge
chown root:nginx /acme-challenge
chmod 750 /acme-challenge
