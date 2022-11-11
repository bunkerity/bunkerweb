#!/bin/bash

# Stop nginx if it's running and remove the old config file if it exists 
systemctl stop nginx

# Change the ownership of /usr/share/bunkerweb to nginx
chown -R nginx:nginx /usr/share/bunkerweb

# Change the ownership of bunkerweb.service to nginx
# chown nginx:nginx /etc/systemd/system/bunkerweb.service

# Start bunkerweb service as nginx user and enable it to start on boot
systemctl enable bunkerweb
systemctl start bunkerweb
systemctl enable bunkerweb-ui
systemctl start bunkerweb-ui