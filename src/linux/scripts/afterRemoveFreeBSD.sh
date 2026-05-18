#!/bin/sh

# FreeBSD afterRemove script for BunkerWeb
# Uses rc.d init system instead of systemd

# Function to run a command and check its return code
do_and_check_cmd() {
    "$@"
    ret=$?
    if [ $ret -ne 0 ]; then
        echo "[ERROR] Command failed: $*"
        exit $ret
    fi
}

# Remove rc.d services
remove_rcd_services() {
    service_prefix=$1
    echo "[INFO] Searching for rc.d services related to $service_prefix"

    for service_file in "/usr/local/etc/rc.d/${service_prefix}"*; do
        if [ -f "$service_file" ]; then
            service_name=$(basename "$service_file")
            echo "[INFO] Found service: $service_name"
            echo "[INFO] Removing $service_name service"

            # Stop service if running
            if service "$service_name" status >/dev/null 2>&1; then
                service "$service_name" stop || echo "[INFO] Service $service_name already stopped."
            fi

            # Disable service in rc.conf
            sysrc -x "${service_name}_enable" 2>/dev/null || true

            # Remove the service file
            do_and_check_cmd rm -f "$service_file"
        fi
    done
}

# Remove directories or files if they exist
remove_path() {
    path=$1
    description=$2

    if [ -e "$path" ]; then
        echo "[INFO] Removing $description ($path)"
        do_and_check_cmd rm -rf "$path"
    else
        echo "[INFO] $description ($path) does not exist. Skipping."
    fi
}

# Perform actions for package removal
remove() {
    echo "[INFO] Package is being uninstalled"

    # Stop nginx if it is active
    if service nginx status >/dev/null 2>&1; then
        echo "[INFO] Stopping nginx service"
        service nginx stop || true
    fi

    # Dynamically remove all related rc.d services
    remove_rcd_services "bunkerweb"

    # Remove associated paths
    remove_path "/usr/share/bunkerweb" "application files"
    remove_path "/usr/local/etc/sudoers.d/bunkerweb-nginx-reload" "BunkerWeb sudoers reload rule"
    remove_path "/var/tmp/bunkerweb" "temporary files"
    remove_path "/var/run/bunkerweb" "runtime files"
    remove_path "/var/log/bunkerweb" "log files"
    remove_path "/var/cache/bunkerweb" "cache files"
    remove_path "/usr/bin/bwcli" "CLI binary"

    echo "[INFO] BunkerWeb successfully uninstalled"
}

# Perform actions for package purge
purge() {
    echo "[INFO] Package is being purged"
    remove

    # Remove additional paths during purge
    remove_path "/var/lib/bunkerweb" "data files"
    remove_path "/etc/bunkerweb" "configuration files"

    echo "[INFO] BunkerWeb successfully purged"
}

# Check for root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] This script must be run as root"
    exit 1
fi

# Detect operating system
DISTRO_ID=""

if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    DISTRO_ID=$(echo "$ID" | tr "[:upper:]" "[:lower:]")
    echo "[INFO] Detected OS from /etc/os-release: $DISTRO_ID"
elif [ "$(uname)" = "FreeBSD" ]; then
    DISTRO_ID="freebsd"
    echo "[INFO] Detected FreeBSD from uname"
else
    echo "[ERROR] Unable to detect operating system"
    exit 1
fi

# Support only FreeBSD systems
if [ "$DISTRO_ID" != "freebsd" ]; then
    echo "[ERROR] Unsupported operating system: $DISTRO_ID"
    echo "[INFO] This script is for FreeBSD only"
    exit 1
fi

# Handle script arguments
case "$1" in
    deinstall)
        remove
        ;;
    POST-DEINSTALL)
        remove
        ;;
    purge)
        purge
        ;;
    *)
        echo "[INFO] Package is being upgraded"
        # Backup important files during upgrade
        remove_path "/var/tmp/variables.env" "temporary environment variables"
        remove_path "/var/tmp/ui.env" "UI environment variables"
        remove_path "/var/tmp/scheduler.env" "Scheduler environment variables"
        remove_path "/var/tmp/api.env" "API environment variables"
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
        if [ -f /etc/bunkerweb/api.env ]; then
            do_and_check_cmd cp -f /etc/bunkerweb/api.env /var/tmp/api.env
        fi
        if [ -f /etc/bunkerweb/api.yml ]; then
            do_and_check_cmd cp -f /etc/bunkerweb/api.yml /var/tmp/api.yml
        fi
        if [ -f /var/lib/bunkerweb/db.sqlite3 ]; then
            do_and_check_cmd cp -f /var/lib/bunkerweb/db.sqlite3 /var/tmp/db.sqlite3
        fi
        do_and_check_cmd touch /var/tmp/bunkerweb_upgrade
        ;;
esac
