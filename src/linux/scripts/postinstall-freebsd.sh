#!/bin/sh

# FreeBSD postinstall script for BunkerWeb
# Uses rc.d init system instead of systemd

# Function to run a command and check its return code
do_and_check_cmd() {
    "$@"
    ret=$?
    if [ $ret -ne 0 ]; then
        echo "[ERROR] Command failed: $*"
        exit $ret
    fi
    return 0
}

# Decompress deps directory with pigz for fastest decompression
echo "Decompressing deps directory..."
cd /usr/share/bunkerweb || exit 1
if [ -f "deps.tar.gz" ]; then
    rm -rf deps
    # Use pigz if available, fallback to gzip
    if command -v pigz >/dev/null 2>&1; then
        tar --use-compress-program="pigz -d" -xf deps.tar.gz
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
do_and_check_cmd mkdir -p /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb
# Ensure a generic python3 entrypoint exists for components that invoke /usr/bin/env python3.
if [ ! -x /usr/local/bin/python3 ]; then
    for pybin in /usr/local/bin/python3.13 /usr/local/bin/python3.12 /usr/local/bin/python3.11 /usr/local/bin/python3.10 /usr/bin/python3; do
        if [ -x "$pybin" ]; then
            do_and_check_cmd ln -sf "$pybin" /usr/local/bin/python3
            break
        fi
    done
fi
# FreeBSD nginx package uses /usr/local/etc/nginx, while BunkerWeb defaults to /etc/nginx.
# Keep both paths aligned so existing templates and scripts continue to work.
if [ ! -e /etc/nginx ] && [ -d /usr/local/etc/nginx ]; then
    do_and_check_cmd ln -s /usr/local/etc/nginx /etc/nginx
fi
do_and_check_cmd chown -R root:nginx /usr/share/bunkerweb
do_and_check_cmd chown -R nginx:nginx /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb

# Allow nginx worker to trigger only rc reload via sudo in API /reload fallback.
if [ -d /usr/local/etc/sudoers.d ]; then
    cat > /usr/local/etc/sudoers.d/bunkerweb-nginx-reload << 'EOF'
nginx ALL=(root) NOPASSWD: /usr/sbin/service bunkerweb reload
EOF
    chmod 440 /usr/local/etc/sudoers.d/bunkerweb-nginx-reload
fi

chmod 755 /var/log/bunkerweb
chmod 770 /var/cache/bunkerweb/ /var/tmp/bunkerweb/ /var/run/bunkerweb/
# Ensure temp dir enforces group inheritance and no access for others
chmod 2770 /var/tmp/bunkerweb/
chmod -R 550 /usr/share/bunkerweb/
find . \( -path "./api" -o -path "./scheduler" -o -path "./ui" -o -path "./cli" -o -path "./lua" -o -path "./core" -o -path "./db" -o -path "./gen" -o -path "./utils" -o -path "./helpers" -o -path "./scripts" -o -path "./deps" \) -prune -o -type f -print0 | xargs -0 chmod 440
find api/ scheduler/ ui/ cli/ lua/ core/ db/ gen/ utils/ helpers/ scripts/ deps/ -type f ! -path "deps/python/bin/*" ! -name "*.lua" ! -name "*.py" ! -name "*.pyc" ! -name "*.sh" ! -name "*.so" -print0 | xargs -0 chmod 440
if [ -d db/alembic/ ]; then
    chmod -R 770 db/alembic/
fi

# Function to migrate files from old locations to new ones
migrate_file() {
    old_path="$1"
    new_path="$2"

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
        return 0
    else
        echo "Old file $old_path not found. Skipping copy..."
        return 1
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
if [ ! -d /var/www/html ]; then
    echo "Creating /var/www/html directory ..."
    do_and_check_cmd mkdir -p /var/www/html
    do_and_check_cmd chmod 750 /var/www/html
    do_and_check_cmd chown root:nginx /var/www/html
else
    echo "/var/www/html directory already exists, skipping copy..."
fi

# FreeBSD: Install rc.d scripts
echo "Installing rc.d service scripts..."
for script in bunkerweb bunkerweb_scheduler bunkerweb_ui bunkerweb_api; do
    if [ -f "/usr/share/bunkerweb/rc.d/${script}" ]; then
        do_and_check_cmd cp "/usr/share/bunkerweb/rc.d/${script}" "/usr/local/etc/rc.d/${script}"
        do_and_check_cmd chmod 555 "/usr/local/etc/rc.d/${script}"
    fi
done

# Parse selected keys from variables.env in a POSIX-sh friendly way.
get_env_value() {
    key="$1"
    env_file="$2"

    [ -f "$env_file" ] || return 0
    awk -F "=" -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "$env_file"
}

MANAGER_MODE=$(get_env_value "MANAGER_MODE" "/etc/bunkerweb/variables.env")
WORKER_MODE=$(get_env_value "WORKER_MODE" "/etc/bunkerweb/variables.env")
SERVICE_BUNKERWEB=$(get_env_value "SERVICE_BUNKERWEB" "/etc/bunkerweb/variables.env")
SERVICE_SCHEDULER=$(get_env_value "SERVICE_SCHEDULER" "/etc/bunkerweb/variables.env")
SERVICE_UI=$(get_env_value "SERVICE_UI" "/etc/bunkerweb/variables.env")
SERVICE_API=$(get_env_value "SERVICE_API" "/etc/bunkerweb/variables.env")
UI_WIZARD=$(get_env_value "UI_WIZARD" "/etc/bunkerweb/variables.env")

# FreeBSD: Stop nginx if running
if service nginx status >/dev/null 2>&1; then
    echo "[STOP] Stopping nginx service..."
    service nginx stop || true
fi

# Helper functions for FreeBSD service management
service_is_enabled() {
    service_name="$1"
    rc_conf_file="/etc/rc.conf.d/${service_name}"

    if [ -f "$rc_conf_file" ]; then
        enabled_value=$(sysrc -f "$rc_conf_file" -n "${service_name}_enable" 2>/dev/null || true)
        echo "$enabled_value" | grep -qi "yes"
        return $?
    fi

    sysrc -n "${service_name}_enable" 2>/dev/null | grep -qi "yes"
}

service_is_running() {
    service "$1" status >/dev/null 2>&1
}

service_enable() {
    service_name="$1"
    rc_conf_file="/etc/rc.conf.d/${service_name}"
    mkdir -p /etc/rc.conf.d
    sysrc -f "$rc_conf_file" "${service_name}_enable=YES" >/dev/null 2>&1
}

service_disable() {
    service_name="$1"
    rc_conf_file="/etc/rc.conf.d/${service_name}"
    mkdir -p /etc/rc.conf.d
    sysrc -f "$rc_conf_file" "${service_name}_enable=NO" >/dev/null 2>&1
}

service_start() {
    # Avoid running long-lived foreground commands during pkg transactions.
    # rc.d services can be started manually right after installation.
    echo "[INFO] Skipping automatic start of $1 during package installation."
    echo "[INFO] Start it manually with: service $1 start"
    return 0
}

service_stop() {
    service "$1" stop 2>/dev/null || true
}

service_restart() {
    # Avoid blocking package upgrades in post-install hooks.
    echo "[INFO] Skipping automatic restart of $1 during package installation."
    echo "[INFO] Restart it manually with: service $1 restart"
    return 0
}

# Manage the BunkerWeb service
echo "Configuring BunkerWeb service..."

# Logic: enable if (standalone mode) OR (worker mode only) AND service not disabled
if {
    # Standalone mode (no manager or worker specified)
    { [ -z "$MANAGER_MODE" ] && [ -z "$WORKER_MODE" ]; } ||
    # Worker mode only (manager disabled or unset, worker enabled)
    { [ -z "$MANAGER_MODE" ] || { [ "${MANAGER_MODE:-yes}" = "no" ] && [ "${WORKER_MODE:-no}" != "no" ]; }; }
} && [ "$SERVICE_BUNKERWEB" != "no" ]; then
    # Upgrade scenario
    if [ -f /var/tmp/bunkerweb_upgrade ]; then
        if service_is_running bunkerweb; then
            echo "[INFO] Restarting the BunkerWeb service after upgrade..."
            do_and_check_cmd service_restart bunkerweb
        fi
    # Fresh installation scenario
    else
        echo "[INFO] Enabling and starting the BunkerWeb service..."
        do_and_check_cmd service_enable bunkerweb
        do_and_check_cmd service_start bunkerweb
    fi
# Disable BunkerWeb if it should not be running but is active
elif service_is_running bunkerweb; then
    echo "[STOP] Disabling and stopping the BunkerWeb service..."
    service_stop bunkerweb
    service_disable bunkerweb
else
    echo "[INFO] BunkerWeb service is not enabled in the current configuration."
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
    if [ -f /var/tmp/bunkerweb_enable_scheduler ] || [ ! -f /var/tmp/bunkerweb_upgrade ]; then
        echo "[INFO] Enabling and starting the BunkerWeb Scheduler service..."
        do_and_check_cmd service_enable bunkerweb_scheduler
        do_and_check_cmd service_start bunkerweb_scheduler

        # Clean up scheduler enablement flag if it exists
        if [ -f /var/tmp/bunkerweb_enable_scheduler ]; then
            echo "[INFO] Removing scheduler enablement flag..."
            do_and_check_cmd rm -f /var/tmp/bunkerweb_enable_scheduler
        fi
    # Upgrade scenario
    else
        # Restart the scheduler service only if it is already running
        if service_is_running bunkerweb_scheduler; then
            echo "[INFO] Restarting the BunkerWeb Scheduler service after upgrade..."
            do_and_check_cmd service_restart bunkerweb_scheduler
        fi
    fi
# Disable scheduler if it should not be running but is active
elif service_is_running bunkerweb_scheduler; then
    echo "[STOP] Disabling and stopping the BunkerWeb Scheduler service..."
    service_stop bunkerweb_scheduler
    service_disable bunkerweb_scheduler
else
    echo "[INFO] BunkerWeb Scheduler service is not enabled in the current configuration."
fi

# Manage the BunkerWeb UI service
echo "Configuring BunkerWeb UI service..."

# Determine if BunkerWeb UI should be enabled based on modes
if {
    # Standalone mode (no manager or worker specified)
    { [ -z "$MANAGER_MODE" ] && [ -z "$WORKER_MODE" ]; } ||
    # Manager-only mode (manager enabled, worker disabled)
    { [ "${MANAGER_MODE:-yes}" != "no" ] && [ "${WORKER_MODE:-no}" = "no" ]; }
} && [ "$SERVICE_UI" != "no" ]; then
    # Fresh installation or explicit UI enablement
    if [ ! -f /var/tmp/bunkerweb_upgrade ]; then
        if [ "${UI_WIZARD:-yes}" != "no" ]; then
            echo "[INFO] Setting up BunkerWeb UI with wizard..."

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

            # Create empty UI environment file if it does not exist
            if [ ! -f /etc/bunkerweb/ui.env ]; then
                touch /etc/bunkerweb/ui.env
            fi

            # Set proper permissions
            do_and_check_cmd chown root:nginx /etc/bunkerweb/ui.env /etc/bunkerweb/variables.env
            do_and_check_cmd chmod 660 /etc/bunkerweb/ui.env /etc/bunkerweb/variables.env

            echo "[INFO] Enabling and starting the BunkerWeb UI service..."
            do_and_check_cmd service_enable bunkerweb_ui
            do_and_check_cmd service_start bunkerweb_ui

            echo "[INFO] The setup wizard is enabled."
            echo "[INFO] Start the UI service, then complete initial configuration at: https://your-ip-address-or-fqdn/setup"
            echo ""
            echo "[WARN]  Note: Make sure that your firewall settings allow access to this URL."
            echo ""
        elif [ "$SERVICE_UI" = "yes" ]; then
            echo "[INFO] Enabling and starting the BunkerWeb UI service..."
            do_and_check_cmd service_enable bunkerweb_ui
            do_and_check_cmd service_start bunkerweb_ui
        else
            echo "[INFO] BunkerWeb UI service is not enabled in the current configuration."
        fi
    # Upgrade scenario
    else
        # Restart the UI service only if it is already running
        if service_is_running bunkerweb_ui; then
            echo "[INFO] Restarting the BunkerWeb UI service after upgrade..."
            do_and_check_cmd service_restart bunkerweb_ui
        fi
    fi
# Disable UI if it should not be running but is active
elif service_is_running bunkerweb_ui; then
    echo "[STOP] Disabling and stopping the BunkerWeb UI service..."
    service_stop bunkerweb_ui
    service_disable bunkerweb_ui
else
    echo "[INFO] BunkerWeb UI service is not enabled in the current configuration."
fi

# Manage the BunkerWeb API service
echo "Configuring BunkerWeb API service..."

# Enable API only when explicitly requested (via env or flag)
if [ "${SERVICE_API:-no}" = "yes" ]; then
    # Fresh installation or explicit API enablement
    if [ ! -f /var/tmp/bunkerweb_upgrade ]; then
        echo "[INFO] Enabling and starting the BunkerWeb API service..."
        do_and_check_cmd service_enable bunkerweb_api
        do_and_check_cmd service_start bunkerweb_api
    else
        # Restart API only if already running
        if service_is_running bunkerweb_api; then
            echo "[INFO] Restarting the BunkerWeb API service after upgrade..."
            do_and_check_cmd service_restart bunkerweb_api
        fi
    fi
elif service_is_running bunkerweb_api; then
    echo "[STOP] Disabling and stopping the BunkerWeb API service..."
    service_stop bunkerweb_api
    service_disable bunkerweb_api
else
    echo "[INFO] BunkerWeb API service is not enabled in the current configuration."
fi

if [ -f /var/tmp/bunkerweb_upgrade ]; then
    rm -f /var/tmp/bunkerweb_upgrade
    echo "BunkerWeb has been successfully upgraded!"
else
    echo "BunkerWeb has been successfully installed!"
fi

echo ""
echo "For more information on BunkerWeb, visit:"
echo "  * Official website: https://www.bunkerweb.io"
echo "  * Documentation: https://docs.bunkerweb.io"
echo "  * Community Support: https://discord.bunkerity.com"
echo "  * Commercial Support: https://panel.bunkerweb.io/store/support"
echo "[INFO] Thank you for using BunkerWeb!"

echo ""
echo "[INFO]  FreeBSD Notes:"
echo "  * Services are managed via rc.d: service bunkerweb start|stop|restart"
echo "  * Enable services in /etc/rc.conf.d: sysrc -f /etc/rc.conf.d/bunkerweb bunkerweb_enable=YES"
echo "  * Configuration files are in /etc/bunkerweb/"
echo ""
echo "[INFO]  External Database Clients:"
echo "  * If you plan on using an external database (MariaDB, MySQL, or PostgreSQL),"
echo "    install the client package that matches your database server version."
echo "    You can list available clients with:"
echo "      pkg search mariadb"
echo "      pkg search mysql"
echo "      pkg search postgresql"
