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

# Give all the permissions to the nginx user
echo "Setting ownership for all necessary directories to nginx user and group..."
do_and_check_cmd chown -R nginx:nginx /usr/share/bunkerweb /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb

# Stop and disable nginx on boot
echo "Stop and disable nginx on boot..."
do_and_check_cmd systemctl stop bunkerweb
do_and_check_cmd systemctl disable bunkerweb

# Auto start BW service on boot and start it now
echo "Enabling and starting bunkerweb service..."
do_and_check_cmd systemctl enable bunkerweb
do_and_check_cmd systemctl start bunkerweb

# Auto start Core service on boot and start it now
echo "Enabling and starting bunkerweb-core service..."
do_and_check_cmd systemctl enable bunkerweb-core
do_and_check_cmd systemctl start bunkerweb-core

# Auto start scheduler service on boot and start it now
echo "Enabling and starting bunkerweb-scheduler service..."
do_and_check_cmd systemctl enable bunkerweb-scheduler
do_and_check_cmd systemctl start bunkerweb-scheduler

# Create /var/www/html if needed
if [ ! -d /var/www/html ] ; then
    echo "Creating /var/www/html directory ..."
    do_and_check_cmd mkdir -p /var/www/html
    do_and_check_cmd chmod 750 /var/www/html
    do_and_check_cmd chown root:nginx /var/www/html
else
    echo "/var/www/html directory already exists, skipping copy..."
fi

echo "Postinstall successful !"
