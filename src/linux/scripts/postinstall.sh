#!/bin/bash

# Stop nginx if it's running and remove the old config file if it exists 
systemctl start nginx

# Start bunkerweb service as nginx user and enable it to start on boot
systemctl enable bunkerweb
systemctl start bunkerweb
systemctl enable bunkerweb-ui
systemctl start bunkerweb-ui