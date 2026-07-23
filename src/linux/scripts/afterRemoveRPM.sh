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

function print_leftover_hint() {
    echo "ℹ️ Logs and upgrade backups are NEVER auto-removed."
    echo "ℹ️   Logs:    rm -rf /var/log/bunkerweb"
    echo "ℹ️   Backups: rm -rf /var/backups/bunkerweb; rm -f /var/tmp/bunkerweb_upgrade"
}

# Perform actions for package removal
function remove() {
    echo "ℹ️ Package is being uninstalled"

    # Tighten any backups left 0644 by pre-fix versions (legacy /var/tmp + current dir).
    chmod 0600 /var/backups/bunkerweb/* \
               /var/tmp/variables.env /var/tmp/ui.env /var/tmp/scheduler.env \
               /var/tmp/api.env /var/tmp/api.yml /var/tmp/db.sqlite3 2>/dev/null || true

    # Stop nginx if it is active
    if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet nginx; then
        echo "ℹ️ Stopping nginx service"
        do_and_check_cmd systemctl stop nginx
    fi

    # Dynamically remove all related systemd services
    remove_systemd_services "bunkerweb"

    # /etc, /var/lib, /var/log, /var/backups/bunkerweb preserved (Fedora Packaging Guidelines).
    remove_path "/usr/share/bunkerweb" "application files"
    remove_path "/var/tmp/bunkerweb" "temporary files"
    remove_path "/var/run/bunkerweb" "runtime files"
    remove_path "/var/cache/bunkerweb" "cache files"
    remove_path "/usr/bin/bwcli" "CLI binary"

    echo "ℹ️ BunkerWeb successfully uninstalled"
    echo "ℹ️ Preserved: /etc/bunkerweb, /var/lib/bunkerweb"
    echo "ℹ️ To purge configs + data run: rm -rf /etc/bunkerweb /var/lib/bunkerweb"
    print_leftover_hint
}

# Check for root privileges
if [ "$(id -u)" -ne 0 ]; then
    echo "❌ This script must be run as root"
    exit 1
fi

# Detect operating system
DISTRO_ID=""

# First try /etc/os-release as it's most commonly available
if [ -f /etc/os-release ]; then
    # Source the file to get variables directly
    # shellcheck disable=SC1091
    . /etc/os-release
    DISTRO_ID=$(echo "$ID" | tr '[:upper:]' '[:lower:]')
    echo "ℹ️ Detected OS from /etc/os-release: $DISTRO_ID"
# Check for Red Hat specific file
elif [ -f /etc/redhat-release ]; then
    DISTRO_ID="redhat"
    echo "ℹ️ Detected Red Hat-based system from /etc/redhat-release"
# Try lsb_release if other methods didn't work
elif command -v lsb_release >/dev/null 2>&1; then
    DISTRO_ID=$(lsb_release -is 2>/dev/null | tr '[:upper:]' '[:lower:]')
    echo "ℹ️ Detected OS from lsb_release: $DISTRO_ID"
else
    echo "❌ Unable to detect operating system"
    exit 1
fi

# Support only Red Hat-based systems
if [[ "$DISTRO_ID" == "redhat" ]] || [[ "$DISTRO_ID" == "centos" ]] ||
   [[ "$DISTRO_ID" == "fedora" ]] || [[ "$DISTRO_ID" == "rocky" ]] ||
   [[ "$DISTRO_ID" == "almalinux" ]] || [[ "$DISTRO_ID" == "rhel" ]]; then
    echo "ℹ️ Running on $DISTRO_ID"
else
    echo "❌ Unsupported operating system: $DISTRO_ID"
    exit 1
fi

# Handle script arguments
case "$1" in
    0)
        # Final uninstall. RPM scriptlets only ever pass 0 (uninstall) or 1 (upgrade);
        # purge is manual on RPM (see print_leftover_hint).
        remove
        ;;
    1)
        echo "ℹ️ Package is being upgraded"
        # Back up config + DB to /var/backups/bunkerweb. /var/tmp is reaped by
        # systemd-tmpfiles after 30d, which silently lost backups on delayed reinstalls.
        backup_dir="/var/backups/bunkerweb"
        do_and_check_cmd mkdir -p "$backup_dir"
        do_and_check_cmd chmod 0700 "$backup_dir"
        remove_path "$backup_dir/variables.env" "environment variables backup"
        remove_path "$backup_dir/ui.env" "UI environment variables backup"
        remove_path "$backup_dir/scheduler.env" "Scheduler environment variables backup"
        remove_path "$backup_dir/api.env" "API environment variables backup"
        remove_path "$backup_dir/api.yml" "API config backup"
        remove_path "$backup_dir/db.sqlite3" "database backup"
        # install -m 0600 (atomic) — backups must not leak credentials.
        if [ -f /etc/bunkerweb/variables.env ]; then
            do_and_check_cmd install -m 0600 -o root -g root /etc/bunkerweb/variables.env "$backup_dir/variables.env"
        fi
        if [ -f /etc/bunkerweb/ui.env ]; then
            do_and_check_cmd install -m 0600 -o root -g root /etc/bunkerweb/ui.env "$backup_dir/ui.env"
        fi
        if [ -f /etc/bunkerweb/scheduler.env ]; then
            do_and_check_cmd install -m 0600 -o root -g root /etc/bunkerweb/scheduler.env "$backup_dir/scheduler.env"
        fi
        if [ -f /etc/bunkerweb/api.env ]; then
            do_and_check_cmd install -m 0600 -o root -g root /etc/bunkerweb/api.env "$backup_dir/api.env"
        fi
        if [ -f /etc/bunkerweb/api.yml ]; then
            do_and_check_cmd install -m 0600 -o root -g root /etc/bunkerweb/api.yml "$backup_dir/api.yml"
        fi
        if [ -f /var/lib/bunkerweb/db.sqlite3 ]; then
            do_and_check_cmd install -m 0600 -o root -g root /var/lib/bunkerweb/db.sqlite3 "$backup_dir/db.sqlite3"
        fi
        do_and_check_cmd touch /var/tmp/bunkerweb_upgrade
        ;;
    *)
        echo "❌ Invalid argument"
        exit 1
        ;;
esac
