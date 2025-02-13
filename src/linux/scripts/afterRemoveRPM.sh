#!/bin/bash

# Function to run a command and check its return code
function do_and_check_cmd() {
    output=$("$@" 2>&1)
    ret=$?
    if [ $ret -ne 0 ]; then
        echo "❌ Error from command: $*"
        echo "$output"
        exit $ret
    else
        echo "✔️ Success: $*"
        echo "$output"
    fi
}

# Reload systemd configuration
function reload_systemd() {
    if command -v systemctl >/dev/null 2>&1; then
        do_and_check_cmd systemctl daemon-reload
        do_and_check_cmd systemctl reset-failed
    else
        echo "ℹ️ Systemd not found, skipping reload."
    fi
}

# Detect and remove systemd services related to the package
function remove_systemd_services() {
    service_prefix=$1  # Prefix to identify relevant services
    echo "ℹ️ Searching for services related to '$service_prefix'"

    # Search for services in common locations
    for dir in /etc/systemd/system /usr/lib/systemd/system /lib/systemd/system; do
        if [ -d "$dir" ]; then
            services=$(find "$dir" -type f -name "${service_prefix}*.service" -exec basename {} \;)
            for service_file in $services; do
                service_name="${service_file%.service}"
                echo "ℹ️ Found service: $service_name"
                echo "ℹ️ Removing $service_name service"

                if command -v systemctl >/dev/null 2>&1; then
                    do_and_check_cmd systemctl stop "$service_name" || echo "ℹ️ Service $service_name already stopped."
                    do_and_check_cmd systemctl disable "$service_name"
                else
                    echo "❌ Systemctl not available, skipping service operations."
                fi

                # Remove the service file
                do_and_check_cmd rm -f "$dir/$service_file"
            done
        fi
    done

    reload_systemd
}

# Remove directories or files if they exist
function remove_path() {
    path=$1
    description=$2

    if [ -e "$path" ]; then
        echo "ℹ️ Removing $description ($path)"
        do_and_check_cmd rm -rf "$path"
    else
        echo "ℹ️ $description ($path) does not exist. Skipping."
    fi
}

# Perform actions for package removal
function remove() {
    echo "ℹ️ Package is being uninstalled"

    # Stop nginx if it is active
    if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet nginx; then
        echo "ℹ️ Stopping nginx service"
        do_and_check_cmd systemctl stop nginx
    fi

    # Dynamically remove all related systemd services
    remove_systemd_services "bunkerweb"

    # Remove associated paths
    remove_path "/usr/share/bunkerweb" "application files"
    remove_path "/var/tmp/bunkerweb" "temporary files"
    remove_path "/var/run/bunkerweb" "runtime files"
    remove_path "/var/log/bunkerweb" "log files"
    remove_path "/var/cache/bunkerweb" "cache files"
    remove_path "/usr/bin/bwcli" "CLI binary"

    echo "ℹ️ BunkerWeb successfully uninstalled"
}

# Perform actions for package purge
function purge() {
    echo "ℹ️ Package is being purged"
    remove

    # Remove additional paths during purge
    remove_path "/var/lib/bunkerweb" "data files"
    remove_path "/etc/bunkerweb" "configuration files"

    echo "ℹ️ BunkerWeb successfully purged"
}

# Check for root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ This script must be run as root"
    exit 1
fi

# Detect operating system
if [ -f /etc/redhat-release ]; then
    OS="redhat"
elif command -v lsb_release >/dev/null 2>&1; then
    OS=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
else
    if [ -f /etc/os-release ]; then
        OS=$(grep "^ID=" /etc/os-release | cut -d= -f2 | tr -d '"' | tr '[:upper:]' '[:lower:]')
    else
        echo "❌ Unable to detect operating system"
        exit 1
    fi
fi

# Support only Red Hat-based systems
if ! [[ "$OS" =~ (redhat|centos|fedora) ]]; then
    echo "❌ Unsupported operating system: $OS"
    exit 1
fi

# Handle script arguments
case "$1" in
    0)
        remove
        purge
        ;;
    1)
        echo "ℹ️ Package is being upgraded"
        # Backup important files during upgrade
        remove_path "/var/tmp/variables.env" "temporary environment variables"
        remove_path "/var/tmp/ui.env" "UI environment variables"
        remove_path "/var/tmp/scheduler.env" "Scheduler environment variables"
        remove_path "/var/tmp/db.sqlite3" "database"
        if [ -f /etc/bunkerweb/variables.env ]; then
            do_and_check_cmd cp -f /etc/bunkerweb/variables.env /var/tmp/variables.env
        fi
        if [ -f /etc/bunkerweb/ui.env ]; then
            do_and_check_cmd cp -f /etc/bunkerweb/ui.env /var/tmp/ui.env
        fi
        if [ -f /etc/bunkerweb/scheduler.env ]; then
            do_and_check_cmd cp -f /etc/bunkerweb/scheduler.env /var/tmp/scheduler.env
        fi
        if [ -f /var/lib/bunkerweb/db.sqlite3 ]; then
            do_and_check_cmd cp -f /var/lib/bunkerweb/db.sqlite3 /var/tmp/db.sqlite3
        fi
        do_and_check_cmd touch /var/tmp/bunkerweb_upgrade
        ;;
    *)
        echo "❌ Invalid argument"
        exit 1
        ;;
esac
