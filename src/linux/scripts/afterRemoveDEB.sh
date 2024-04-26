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

function reload_systemd() {
    do_and_check_cmd systemctl daemon-reload
    do_and_check_cmd systemctl reset-failed
}

# remove a systemd service
function remove_systemd_service {
    service=$1
    service_file="/lib/systemd/system/$service.service"
    echo "checking service $service with $service_file file "
    if [ -f "$service_file" ]; then
        echo "ℹ️ Remove $service service"
        do_and_check_cmd systemctl stop "$service"
        do_and_check_cmd systemctl disable "$service"
        do_and_check_cmd rm -f "$service_file"
        reload_systemd
    else
        echo "$service_file not found"
    fi
}

function remove {
    echo "Package is being uninstalled"

    # Stop nginx
    if systemctl is-active nginx; then
        echo "ℹ️ Stop nginx service"
        do_and_check_cmd systemctl stop nginx
    fi

    remove_systemd_service "bunkerweb"
    remove_systemd_service "bunkerweb-ui"

    # Remove /usr/share/bunkerweb
    if test -e "/usr/share/bunkerweb"; then
        echo "ℹ️ Remove /usr/share/bunkerweb"
        do_and_check_cmd rm -rf /usr/share/bunkerweb
    fi

    # Remove /var/tmp/bunkerweb
    if test -e "/var/tmp/bunkerweb"; then
        echo "ℹ️ Remove /var/tmp/bunkerweb"
        do_and_check_cmd rm -rf /var/tmp/bunkerweb
    fi

    # Remove /var/run/bunkerweb
    if test -e "/var/run/bunkerweb"; then
        echo "ℹ️ Remove /var/run/bunkerweb"
        do_and_check_cmd rm -rf /var/run/bunkerweb
    fi

    # Remove /var/log/bunkerweb
    if test -e "/var/log/bunkerweb"; then
        echo "ℹ️ Remove /var/log/bunkerweb"
        do_and_check_cmd rm -rf /var/log/bunkerweb
    fi

    # Remove /var/lib/bunkerweb
    if test -e "/var/cache/bunkerweb"; then
        echo "ℹ️ Remove  /var/cache/bunkerweb"
        do_and_check_cmd rm -rf /var/cache/bunkerweb
    fi

    # Remove /usr/bin/bwcli
    if test -f "/usr/bin/bwcli"; then
        echo "ℹ️ Remove /usr/bin/bwcli"
        do_and_check_cmd rm -f /usr/bin/bwcli
    fi

    echo "ℹ️ BunkerWeb successfully uninstalled"
}

function purge() {
    echo "Package is being purged"
    remove

    # Remove /var/lib/bunkerweb
    if test -e "/var/lib/bunkerweb"; then
        echo "ℹ️ Remove /var/lib/bunkerweb"
        do_and_check_cmd rm -rf /var/lib/bunkerweb
    fi

    # Remove /var/tmp/bunkerweb/variables.env
    if test -d "/etc/bunkerweb"; then
        echo "ℹ️ Remove /etc/bunkerweb"
        do_and_check_cmd rm -rf /etc/bunkerweb
    fi

    echo "ℹ️ BunkerWeb successfully purged"
}

# Check if we are root
if [ "$(id -u)" -ne 0 ] ; then
    echo "❌ Run me as root"
    exit 1
fi

# Detect OS
OS=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
if ! [[ "$OS" =~ (debian|ubuntu) ]]; then
    echo "❌ Unsupported Operating System"
    exit 1
fi

# Check if the package is being upgraded or uninstalled
if [ "$1" = "remove" ]; then
    # Call the remove function
    remove
elif [ "$1" = "purge" ]; then
    # Call the purge function
    purge
else
    echo "Package is being upgraded"
    # Check the version of the package and if it's inferior to 1.5.0, we need to copy the variables.env file
    VERSION=$(dpkg-query -W -f='${Version}' bunkerweb)
    if ! [[ "$VERSION" =~ ^1\.5 ]]; then
        echo "ℹ️ Copyenv variables to /var/tmp/bunkerweb/*.env"
        do_and_check_cmd cp -f /opt/bunkerweb/variables.env /var/tmp/variables.env
        do_and_check_cmd cp -f /opt/bunkerweb/ui.env /var/tmp/ui.env
    fi
    cp -f /etc/bunkerweb/variables.env /var/tmp/variables.env
    cp -f /etc/bunkerweb/ui.env /var/tmp/ui.env
    cp -f /var/lib/bunkerweb/db.sqlite3 /var/tmp/db.sqlite3
    exit 0
fi
