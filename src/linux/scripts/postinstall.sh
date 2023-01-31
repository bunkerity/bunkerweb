#!/bin/bash

# Function to run a command and check its return code
function do_and_check_cmd() {
    output=$("$@" 2>&1)
    ret="$?"
    if [ $ret -ne 0 ] ; then
        echo "❌ Error from command : $*"
        echo "$output"
        exit $ret
    else
        echo "✔️ Success: $*"
        echo "$output"
    fi
    return 0
}

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

# Copy old line from environment file to new one
echo "Copying old line from environment file to new one..."
while read line; do
    echo "$line" >> /etc/bunkerweb/variables.env
done < /var/tmp/variables.env

echo "Copying old line from ui environment file to new one..."
while read line; do
    echo "$line" >> /etc/bunkerweb/ui.env
done < /var/tmp/ui.env

# Remove old environment files
echo "Removing old environment files..."
rm -f /var/tmp/variables.env
rm -f /var/tmp/ui.env

echo "All services started and enabled successfully!"