#!/bin/bash

#Start the nginx service
echo "Starting nginx service..."
systemctl start nginx

#Give all the permissions to the nginx user
echo "Setting ownership for all necessary directories to nginx user and group..."
chown -R nginx:nginx /usr/share/bunkerweb /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb

#Start bunkerweb service as nginx user and enable it to start on boot
echo "Enabling and starting bunkerweb service..."
systemctl enable bunkerweb
systemctl start bunkerweb

#Start and enable bunkerweb-ui service
echo "Enabling and starting bunkerweb-ui service..."
systemctl enable bunkerweb-ui
systemctl start bunkerweb-ui

echo "All services started and enabled successfully!"