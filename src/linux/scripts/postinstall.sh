#!/bin/bash

# Stop nginx if it's running and remove the old config file if it exists 
systemctl start nginx

# Give all the permissions to the nginx user
chown -R nginx:nginx /usr/share/bunkerweb /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb

# Start bunkerweb service as nginx user and enable it to start on boot
systemctl enable bunkerweb
systemctl start bunkerweb
systemctl enable bunkerweb-ui
systemctl start bunkerweb-ui