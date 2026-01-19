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

# Decompress deps directory with pigz for fastest decompression
echo "Decompressing deps directory with pigz..."
cd /usr/share/bunkerweb || exit 1
if [ -f "deps.tar.gz" ]; then
    rm -rf deps
    # Use pigz if available, fallback to gzip
    if command -v pigz >/dev/null 2>&1; then
        tar --use-compress-program="pigz -d -p$(nproc)" -xf deps.tar.gz
    else
        tar -xzf deps.tar.gz
    fi
    rm -f deps.tar.gz
    echo "Decompression completed successfully"
else
    echo "No compressed deps directory found, skipping decompression"
fi

# Give all the permissions to the nginx user
echo "Setting ownership for all necessary directories to nginx user and group..."
do_and_check_cmd chown -R root:nginx /usr/share/bunkerweb
do_and_check_cmd chown -R nginx:nginx /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb

chmod 755 /var/log/bunkerweb
chmod 770 /var/cache/bunkerweb/ /var/tmp/bunkerweb/ /var/run/bunkerweb/
# Ensure temp dir enforces group inheritance and no access for others
chmod 2770 /var/tmp/bunkerweb/
chmod 550 -R /usr/share/bunkerweb/
find . \( -path './api' -o -path './scheduler' -o -path './ui' -o -path './cli' -o -path './lua' -o -path './core' -o -path './db' -o -path './gen' -o -path './utils' -o -path './helpers' -o -path './scripts' -o -path './deps' \) -prune -o -type f -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440
find api/ scheduler/ ui/ cli/ lua/ core/ db/ gen/ utils/ helpers/ scripts/ deps/ -type f ! -path 'deps/python/bin/*' ! -name '*.lua' ! -name '*.py' ! -name '*.pyc' ! -name '*.sh' ! -name '*.so' -print0 | xargs -0 -P "$(nproc)" -n 1024 chmod 440
chmod 770 -R db/alembic/

# Function to migrate files from old locations to new ones
function migrate_file() {
    local old_path="$1"
    local new_path="$2"

    if [ -f "$old_path" ]; then
        echo "Old file $old_path found!"
        if [ ! -f /var/tmp/bunkerweb_upgrade ]; then
            touch /var/tmp/bunkerweb_upgrade
        fi
        echo "Copying old file to new location: $new_path..."
        cp "$old_path" "$new_path"
        echo "Removing old file..."
        do_and_check_cmd rm -f "$old_path"
        do_and_check_cmd chown root:nginx "$new_path"
        do_and_check_cmd chmod 660 "$new_path"
        return 0  # Success
    else
        echo "Old file $old_path not found. Skipping copy..."
        return 1  # File not found
    fi
}

# Migrate configuration files from old to new locations
migrate_file "/var/tmp/variables.env" "/etc/bunkerweb/variables.env"
migrate_file "/var/tmp/scheduler.env" "/etc/bunkerweb/scheduler.env"
migrate_file "/var/tmp/ui.env" "/etc/bunkerweb/ui.env"
migrate_file "/var/tmp/api.env" "/etc/bunkerweb/api.env"
migrate_file "/var/tmp/api.yml" "/etc/bunkerweb/api.yml"
migrate_file "/var/tmp/db.sqlite3" "/var/lib/bunkerweb/db.sqlite3"

# Create /var/www/html if needed
if [ ! -d /var/www/html ] ; then
    echo "Creating /var/www/html directory ..."
    do_and_check_cmd mkdir -p /var/www/html
    do_and_check_cmd chmod 750 /var/www/html
    do_and_check_cmd chown root:nginx /var/www/html
else
    echo "/var/www/html directory already exists, skipping copy..."
fi

systemctl daemon-reload

# Always stop and disable nginx service
echo "🛑 Stopping and disabling the nginx service..."
do_and_check_cmd systemctl disable --now nginx

# Manage the BunkerWeb service
echo "Configuring BunkerWeb service..."

# Determine if BunkerWeb should be enabled based on modes
# Logic: enable if (standalone mode) OR (worker mode only) AND service not disabled
if {
    # Standalone mode (no manager or worker specified)
    { [ -z "$MANAGER_MODE" ] && [ -z "$WORKER_MODE" ]; } ||
    # Worker mode only (manager disabled or unset, worker enabled)
    { [ -z "$MANAGER_MODE" ] || [ "${MANAGER_MODE:-yes}" = "no" ] && [ "${WORKER_MODE:-no}" != "no" ]; }
} && [ "$SERVICE_BUNKERWEB" != "no" ]; then
    # Upgrade scenario
    if [ -f /var/tmp/bunkerweb_upgrade ]; then
        if systemctl is-active --quiet bunkerweb; then
            echo "📋 Reloading the BunkerWeb service after upgrade..."
            do_and_check_cmd systemctl restart bunkerweb
        fi
    # Fresh installation scenario
    else
        echo "🚀 Enabling and starting the BunkerWeb service..."
        do_and_check_cmd systemctl enable --now bunkerweb
    fi
# Disable BunkerWeb if it shouldn't be running but is active
elif systemctl is-active --quiet bunkerweb; then
    echo "🛑 Disabling and stopping the BunkerWeb service..."
    do_and_check_cmd systemctl disable --now bunkerweb
else
    echo "ℹ️ BunkerWeb service is not enabled in the current configuration."
fi

# Manage the BunkerWeb Scheduler service
echo "Configuring BunkerWeb Scheduler service..."

# Enable scheduler if: (standalone mode OR manager-only mode) AND service not disabled
if {
    # Standalone mode (no manager or worker specified)
    { [ -z "$MANAGER_MODE" ] && [ -z "$WORKER_MODE" ]; } ||
    # Manager-only mode (manager enabled, worker disabled)
    { [ "${MANAGER_MODE:-yes}" != "no" ] && [ "${WORKER_MODE:-no}" = "no" ]; }
} && [ "$SERVICE_SCHEDULER" != "no" ]; then
    # Fresh installation or explicit scheduler enablement
    if [[ -f /var/tmp/bunkerweb_enable_scheduler || ! -f /var/tmp/bunkerweb_upgrade ]]; then
        echo "🚀 Enabling and starting the BunkerWeb Scheduler service..."
        do_and_check_cmd systemctl enable --now bunkerweb-scheduler

        # Clean up scheduler enablement flag if it exists
        if [ -f /var/tmp/bunkerweb_enable_scheduler ]; then
            echo "ℹ️ Removing scheduler enablement flag..."
            do_and_check_cmd rm -f /var/tmp/bunkerweb_enable_scheduler
        fi
    # Upgrade scenario
    else
        # Restart the scheduler service only if it's already running
        if systemctl is-active --quiet bunkerweb-scheduler; then
            echo "📋 Restarting the BunkerWeb Scheduler service after upgrade..."
            do_and_check_cmd systemctl restart bunkerweb-scheduler
        fi
    fi
# Disable scheduler if it shouldn't be running but is active
elif systemctl is-active --quiet bunkerweb-scheduler; then
    echo "🛑 Disabling and stopping the BunkerWeb Scheduler service..."
    do_and_check_cmd systemctl disable --now bunkerweb-scheduler
else
    echo "ℹ️ BunkerWeb Scheduler service is not enabled in the current configuration."
fi

# Manage the BunkerWeb UI service
echo "Configuring BunkerWeb UI service..."

# Determine if BunkerWeb UI should be enabled based on modes
# Logic: Enable UI if (standalone mode OR manager-only mode) AND UI service not disabled
if {
    # Standalone mode (no manager or worker specified)
    { [ -z "$MANAGER_MODE" ] && [ -z "$WORKER_MODE" ]; } ||
    # Manager-only mode (manager enabled, worker disabled)
    { [ "${MANAGER_MODE:-yes}" != "no" ] && [ "${WORKER_MODE:-no}" = "no" ]; }
} && [ "$SERVICE_UI" != "no" ]; then
    # Fresh installation or explicit UI enablement
    if [ ! -f /var/tmp/bunkerweb_upgrade ]; then
        if [ "${UI_WIZARD:-yes}" != "no" ]; then
            echo "🧙 Setting up BunkerWeb UI with wizard..."

            # Create default configuration for new installations
            if [ ! -f /etc/bunkerweb/variables.env ] || grep -q "IS_LOADING=yes" /etc/bunkerweb/variables.env; then
                cat > /etc/bunkerweb/variables.env << EOF
DNS_RESOLVERS=9.9.9.9 149.112.112.112 8.8.8.8 8.8.4.4
HTTP_PORT=80
HTTPS_PORT=443
API_LISTEN_IP=127.0.0.1
MULTISITE=yes
UI_HOST=http://127.0.0.1:7000
SERVER_NAME=
EOF
            fi

            # Create empty UI environment file if it doesn't exist
            if [ ! -f /etc/bunkerweb/ui.env ]; then
                touch /etc/bunkerweb/ui.env
            fi

            # Set proper permissions
            do_and_check_cmd chown root:nginx /etc/bunkerweb/ui.env /etc/bunkerweb/variables.env
            do_and_check_cmd chmod 660 /etc/bunkerweb/ui.env /etc/bunkerweb/variables.env

            echo "🚀 Enabling and starting the BunkerWeb UI service..."
            do_and_check_cmd systemctl enable --now bunkerweb-ui

            echo "🧙 The setup wizard has been activated automatically."
            echo "📝 Please complete the initial configuration at: https://your-ip-address-or-fqdn/setup"
            echo ""
            echo "⚠️  Note: Make sure that your firewall settings allow access to this URL."
            echo ""
        elif [ "$SERVICE_UI" = "yes" ]; then
            echo "🚀 Enabling and starting the BunkerWeb UI service..."
            do_and_check_cmd systemctl enable --now bunkerweb-ui
        else
            echo "ℹ️ BunkerWeb UI service is not enabled in the current configuration."
        fi
    # Upgrade scenario
    else
        # Restart the UI service only if it's already running
        if systemctl is-active --quiet bunkerweb-ui; then
            echo "📋 Restarting the BunkerWeb UI service after upgrade..."
            do_and_check_cmd systemctl restart bunkerweb-ui
        fi
    fi
# Disable UI if it shouldn't be running but is active
elif systemctl is-active --quiet bunkerweb-ui; then
    echo "🛑 Disabling and stopping the BunkerWeb UI service..."
    do_and_check_cmd systemctl disable --now bunkerweb-ui
else
    echo "ℹ️ BunkerWeb UI service is not enabled in the current configuration."
fi

# Manage the BunkerWeb API service
echo "Configuring BunkerWeb API service..."

# Enable API only when explicitly requested (via env or flag)
if [ "${SERVICE_API:-no}" = "yes" ]; then
    # Fresh installation or explicit API enablement
    if [ ! -f /var/tmp/bunkerweb_upgrade ]; then
        echo "🚀 Enabling and starting the BunkerWeb API service..."
        do_and_check_cmd systemctl enable --now bunkerweb-api
    else
        # Restart API only if already running
        if systemctl is-active --quiet bunkerweb-api; then
            echo "📋 Restarting the BunkerWeb API service after upgrade..."
            do_and_check_cmd systemctl restart bunkerweb-api
        fi
    fi
elif systemctl is-active --quiet bunkerweb-api; then
    echo "🛑 Disabling and stopping the BunkerWeb API service..."
    do_and_check_cmd systemctl disable --now bunkerweb-api
else
    echo "ℹ️ BunkerWeb API service is not enabled in the current configuration."
fi

if [ -f /var/tmp/bunkerweb_upgrade ]; then
    rm -f /var/tmp/bunkerweb_upgrade
    echo "BunkerWeb has been successfully upgraded! 🎉"
else
    echo "BunkerWeb has been successfully installed! 🎉"
fi

echo ""
echo "For more information on BunkerWeb, visit:"
echo "  * Official website: https://www.bunkerweb.io"
echo "  * Documentation: https://docs.bunkerweb.io"
echo "  * Community Support: https://discord.bunkerity.com"
echo "  * Commercial Support: https://panel.bunkerweb.io/store/support"
echo "🛡 Thank you for using BunkerWeb!"

# Detect if OS is RHEL-based for warning
RHEL_OS=""
if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    DISTRO_ID=$(echo "$ID" | tr '[:upper:]' '[:lower:]')
    case "$DISTRO_ID" in
        rhel|centos|fedora|rocky|almalinux|redhat)
            RHEL_OS=1
            ;;
    esac
elif [ -f /etc/redhat-release ]; then
    RHEL_OS=1
fi

if [ "$RHEL_OS" = "1" ]; then
cat << EOF
⚠️  WARNING for RHEL users:
If you plan on using an external database (MariaDB, MySQL, or PostgreSQL), you must install the appropriate client package (e.g., mariadb, mysql, or postgresql client) on your system for the BunkerWeb Scheduler to connect properly.
EOF
fi
