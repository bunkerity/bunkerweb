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
    if [ -d /var/backups/bunkerweb ]; then
        do_and_check_cmd find /var/backups/bunkerweb -maxdepth 1 -type f -exec chmod 0600 {} +
    fi
    chmod 0600 /var/tmp/variables.env /var/tmp/ui.env /var/tmp/scheduler.env \
               /var/tmp/api.env /var/tmp/api.yml /var/tmp/db.sqlite3 2>/dev/null || true

    # Units were stopped by prerm/%preun; vendor files belong to the package manager.
    reload_systemd

    # /etc, /var/lib, /var/log, /var/backups/bunkerweb preserved (Debian Policy §10.8).
    remove_path "/usr/share/bunkerweb" "application files"
    remove_path "/var/tmp/bunkerweb" "temporary files"
    remove_path "/var/run/bunkerweb" "runtime files"
    remove_path "/var/cache/bunkerweb" "cache files"
    remove_path "/usr/bin/bwcli" "CLI binary"

    echo "ℹ️ BunkerWeb successfully uninstalled"
    echo "ℹ️ Preserved (use 'apt-get purge bunkerweb' to delete configs + data): /etc/bunkerweb, /var/lib/bunkerweb"
    print_leftover_hint
}

# Perform actions for package purge
function purge() {
    echo "ℹ️ Package is being purged"
    remove

    # Logs and /var/tmp backups deliberately kept on purge — admin disposes.
    remove_path "/var/lib/bunkerweb" "data files"
    remove_path "/etc/bunkerweb" "configuration files"

    echo "ℹ️ BunkerWeb successfully purged"
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
# Try lsb_release if os-release didn't work
elif command -v lsb_release >/dev/null 2>&1; then
    DISTRO_ID=$(lsb_release -is 2>/dev/null | tr '[:upper:]' '[:lower:]')
    echo "ℹ️ Detected OS from lsb_release: $DISTRO_ID"
# Final fallback - check for Debian/Ubuntu specific files
elif [ -f /etc/debian_version ]; then
    DISTRO_ID="debian"
    echo "ℹ️ Detected Debian-based system from /etc/debian_version"
else
    echo "❌ Unable to detect operating system"
    exit 1
fi

# Support only Debian-based systems
if [[ "$DISTRO_ID" == "debian" ]] || [[ "$DISTRO_ID" == "ubuntu" ]] ||
   [[ "$DISTRO_ID" == *"debian"* ]] || [[ "$DISTRO_ID" == *"ubuntu"* ]]; then
    echo "ℹ️ Running on $DISTRO_ID"
else
    echo "❌ Unsupported operating system: $DISTRO_ID"
    exit 1
fi

# Handle script arguments
case "$1" in
    remove)
        remove
        ;;
    purge)
        purge
        ;;
    upgrade|failed-upgrade)
        # The new pre-install hook owns the current transaction snapshot.
        ;;
    abort-install|abort-upgrade|disappear)
        # Rollback callbacks must not replace a known-good upgrade backup.
        ;;
    *)
        echo "❌ Unsupported postrm argument: $1" >&2
        exit 1
        ;;
esac
