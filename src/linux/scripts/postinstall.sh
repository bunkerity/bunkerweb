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

set -o pipefail

# Decompress deps directory with pigz for fastest decompression
echo "Decompressing deps directory with pigz..."
cd /usr/share/bunkerweb || exit 1
if [ -f "deps.tar.gz" ]; then
    deps_stage=$(mktemp -d /usr/share/bunkerweb/.deps.XXXXXX) || exit 1
    # Use pigz if available, fallback to gzip
    if command -v pigz >/dev/null 2>&1; then
        do_and_check_cmd tar --use-compress-program="pigz -d -p$(nproc)" -xf deps.tar.gz -C "$deps_stage"
    else
        do_and_check_cmd tar -xzf deps.tar.gz -C "$deps_stage"
    fi
    [ -d "$deps_stage/deps" ] || { echo "❌ Dependency archive has no deps directory" >&2; exit 1; }
    if [ -d deps ]; then
        do_and_check_cmd mv deps "$deps_stage/previous"
    fi
    if ! mv "$deps_stage/deps" deps; then
        [ ! -d "$deps_stage/previous" ] || mv "$deps_stage/previous" deps
        exit 1
    fi
    do_and_check_cmd rm -rf "$deps_stage"
    do_and_check_cmd rm -f deps.tar.gz
    echo "Decompression completed successfully"
else
    echo "No compressed deps directory found, skipping decompression"
fi

# Give all the permissions to the nginx user
echo "Setting ownership for all necessary directories to nginx user and group..."
do_and_check_cmd chown -R root:nginx /usr/share/bunkerweb
do_and_check_cmd chown -R nginx:nginx /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb /var/run/bunkerweb /var/log/bunkerweb

# Repair locks created as 0600 by older root-run bwcli commands without replacing the inode.
if [ -f /var/lib/bunkerweb/db.lock ]; then
    do_and_check_cmd chmod 0644 /var/lib/bunkerweb/db.lock
fi

do_and_check_cmd chmod 755 /var/log/bunkerweb
# Tighten active logs and archives in place, preserving narrower administrator modes.
do_and_check_cmd find /var/log/bunkerweb -type f -exec chmod u-x,g-wx,o-rwx {} +
do_and_check_cmd chmod 770 /var/cache/bunkerweb/ /var/tmp/bunkerweb/ /var/run/bunkerweb/
# Ensure temp dir enforces group inheritance and no access for others
do_and_check_cmd chmod 2770 /var/tmp/bunkerweb/
do_and_check_cmd chmod 550 -R /usr/share/bunkerweb/
find . \( -path './api' -o -path './scheduler' -o -path './ui' -o -path './cli' -o -path './lua' -o -path './core' -o -path './db' -o -path './gen' -o -path './utils' -o -path './helpers' -o -path './scripts' -o -path './deps' \) -prune -o -type f -print0 | xargs -0 -r -P "$(nproc)" -n 1024 chmod 440 || exit 1
find api/ scheduler/ ui/ cli/ lua/ core/ db/ gen/ utils/ helpers/ scripts/ deps/ -type f ! -path 'deps/python/bin/*' ! -name '*.lua' ! -name '*.py' ! -name '*.pyc' ! -name '*.sh' ! -name '*.so' -print0 | xargs -0 -r -P "$(nproc)" -n 1024 chmod 440 || exit 1

# Retro-tighten 0644 backups left by pre-fix versions.
chmod 0600 /var/tmp/variables.env /var/tmp/ui.env /var/tmp/scheduler.env \
           /var/tmp/api.env /var/tmp/api.yml /var/tmp/db.sqlite3 2>/dev/null || true

# Restore only the snapshot published by this transaction's pre-install hook.
transaction=/var/backups/bunkerweb/transaction
UPGRADE=no
if [ -f "$transaction/upgrade" ]; then
    UPGRADE=$(cat "$transaction/upgrade") || exit 1
    case "$UPGRADE" in
        yes|no) ;;
        *) echo "❌ Invalid upgrade transaction state" >&2; exit 1 ;;
    esac
elif { [ "${1:-}" = configure ] && [ -n "${2:-}" ]; } || [ -f /var/tmp/bunkerweb_upgrade ]; then
    UPGRADE=yes
fi
if [ "$UPGRADE" = yes ]; then
    do_and_check_cmd touch /var/tmp/bunkerweb_upgrade
else
    do_and_check_cmd rm -f /var/tmp/bunkerweb_upgrade
fi

function was_active() {
    systemctl is-active --quiet "$1" || { [ -f "$transaction/active" ] && grep -qxF "$1" "$transaction/active"; }
}

function migrate_file() {
    local old_path="$1"
    local new_path="$2"

    if [ -f "$old_path" ]; then
        local replacement
        replacement=$(mktemp "${new_path}.XXXXXX") || exit 1
        do_and_check_cmd cp "$old_path" "$replacement"
        do_and_check_cmd chown root:nginx "$replacement"
        do_and_check_cmd chmod 660 "$replacement"
        do_and_check_cmd mv -f "$replacement" "$new_path"
        if [ "$new_path" = /var/lib/bunkerweb/db.sqlite3 ]; then
            do_and_check_cmd rm -f "${new_path}-wal" "${new_path}-shm" "${new_path}-journal"
        fi
    fi
}

if [ "$UPGRADE" = yes ] && [ -f "$transaction/upgrade" ] && [ ! -f "$transaction/restored" ]; then
    for service in bunkerweb bunkerweb-scheduler bunkerweb-ui bunkerweb-api; do
        do_and_check_cmd systemctl stop "$service"
    done
    if [ -f "$transaction/db.sqlite3" ]; then
        check=$(sqlite3 -batch -bail -readonly "$transaction/db.sqlite3" 'PRAGMA quick_check;') || exit 1
        [ "$check" = ok ] || { echo "❌ Invalid SQLite upgrade snapshot: $check" >&2; exit 1; }
    fi
    for name in variables.env scheduler.env ui.env api.env api.yml; do
        migrate_file "$transaction/$name" "/etc/bunkerweb/$name"
    done
    migrate_file "$transaction/db.sqlite3" /var/lib/bunkerweb/db.sqlite3
    # A failed service restart may be retried after services have already written new data.
    do_and_check_cmd touch "$transaction/restored"
fi

# Create /var/www/html if needed
if [ ! -d /var/www/html ] ; then
    echo "Creating /var/www/html directory ..."
    do_and_check_cmd mkdir -p /var/www/html
    do_and_check_cmd chmod 750 /var/www/html
    do_and_check_cmd chown root:nginx /var/www/html
else
    echo "/var/www/html directory already exists, skipping copy..."
fi

do_and_check_cmd systemctl daemon-reload

# Always stop and disable nginx service
echo "🛑 Stopping and disabling the nginx service..."
do_and_check_cmd systemctl disable --now nginx

# Resolve whether the topology was DECLARED this run — either a fresh install or an
# explicit mode/service signal from the installer. On a bare `apt upgrade` (no signal)
# the operator's intent is unknown, so we mutate no persistent state: we neither
# self-heal leftover-enabled units nor stamp an install-type marker, and let the
# upgrade-time detector keep inferring. This is the single gate behind Part A (marker)
# and the enabled-but-stopped leg of Part C (self-heal).
FRESH_INSTALL="no"
[ ! -f /var/tmp/bunkerweb_upgrade ] && FRESH_INSTALL="yes"
RESOLVED_INSTALL_TYPE=""
EXPLICIT_TOPOLOGY="no"
if [ "${WORKER_MODE:-no}" = "yes" ] && [ "${MANAGER_MODE:-no}" != "yes" ]; then
    RESOLVED_INSTALL_TYPE="worker"; EXPLICIT_TOPOLOGY="yes"
elif [ "${MANAGER_MODE:-no}" = "yes" ] && [ "${WORKER_MODE:-no}" != "yes" ]; then
    RESOLVED_INSTALL_TYPE="manager"; EXPLICIT_TOPOLOGY="yes"
elif [ "${SERVICE_API:-no}" = "yes" ] && [ "${SERVICE_BUNKERWEB:-yes}" = "no" ] && [ "${SERVICE_SCHEDULER:-yes}" = "no" ] && [ "${SERVICE_UI:-yes}" = "no" ]; then
    RESOLVED_INSTALL_TYPE="api"; EXPLICIT_TOPOLOGY="yes"
elif [ "${SERVICE_BUNKERWEB:-yes}" = "no" ] && [ "${SERVICE_SCHEDULER:-no}" = "yes" ] && [ "${SERVICE_UI:-yes}" = "no" ]; then
    RESOLVED_INSTALL_TYPE="scheduler"; EXPLICIT_TOPOLOGY="yes"
elif [ "${SERVICE_BUNKERWEB:-yes}" = "no" ] && [ "${SERVICE_UI:-no}" = "yes" ] && [ "${SERVICE_SCHEDULER:-yes}" = "no" ]; then
    RESOLVED_INSTALL_TYPE="ui"; EXPLICIT_TOPOLOGY="yes"
else
    RESOLVED_INSTALL_TYPE="full"
fi
TOPOLOGY_DECLARED="no"
{ [ "$FRESH_INSTALL" = "yes" ] || [ "$EXPLICIT_TOPOLOGY" = "yes" ]; } && TOPOLOGY_DECLARED="yes"

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
        if was_active bunkerweb; then
            echo "📋 Reloading the BunkerWeb service after upgrade..."
            do_and_check_cmd systemctl restart bunkerweb
        fi
    # Fresh installation scenario
    else
        echo "🚀 Enabling and starting the BunkerWeb service..."
        do_and_check_cmd systemctl enable --now bunkerweb
    fi
# Disable BunkerWeb if it shouldn't be running but is still active, or — only when the
# topology was declared this run — enabled-but-stopped. Clearing leftovers keeps the
# host's systemd state consistent with its real topology so upgrade-time detection
# stays correct; we never touch enabled-but-stopped units on a bare upgrade.
elif was_active bunkerweb || { [ "$TOPOLOGY_DECLARED" = "yes" ] && systemctl is-enabled --quiet bunkerweb 2>/dev/null; }; then
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
        if was_active bunkerweb-scheduler; then
            echo "📋 Restarting the BunkerWeb Scheduler service after upgrade..."
            do_and_check_cmd systemctl restart bunkerweb-scheduler
        fi
    fi
# Disable scheduler if it shouldn't be running but is still active, or — only when the
# topology was declared this run — enabled-but-stopped. An enabled-but-stopped scheduler
# left over from a prior full install would otherwise make this worker look like a full
# stack on the next upgrade; but on a bare upgrade we leave the operator's units alone.
elif was_active bunkerweb-scheduler || { [ "$TOPOLOGY_DECLARED" = "yes" ] && systemctl is-enabled --quiet bunkerweb-scheduler 2>/dev/null; }; then
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
        if was_active bunkerweb-ui; then
            echo "📋 Restarting the BunkerWeb UI service after upgrade..."
            do_and_check_cmd systemctl restart bunkerweb-ui
        fi
    fi
# Disable UI if it shouldn't be running but is still active, or — only when the topology
# was declared this run — enabled-but-stopped.
elif was_active bunkerweb-ui || { [ "$TOPOLOGY_DECLARED" = "yes" ] && systemctl is-enabled --quiet bunkerweb-ui 2>/dev/null; }; then
    echo "🛑 Disabling and stopping the BunkerWeb UI service..."
    do_and_check_cmd systemctl disable --now bunkerweb-ui
else
    echo "ℹ️ BunkerWeb UI service is not enabled in the current configuration."
fi

# Manage the BunkerWeb API service
echo "Configuring BunkerWeb API service..."

# Enable API only when explicitly requested (via env or flag)
if [ "${SERVICE_API:-no}" = "yes" ] || { [ "$UPGRADE" = yes ] && [ "$TOPOLOGY_DECLARED" = no ] && [ -z "${SERVICE_API+x}" ]; }; then
    # Fresh installation or explicit API enablement
    if [ ! -f /var/tmp/bunkerweb_upgrade ]; then
        echo "🚀 Enabling and starting the BunkerWeb API service..."
        do_and_check_cmd systemctl enable --now bunkerweb-api
    else
        # Restart API only if already running
        if was_active bunkerweb-api; then
            echo "📋 Restarting the BunkerWeb API service after upgrade..."
            do_and_check_cmd systemctl restart bunkerweb-api
        fi
    fi
elif was_active bunkerweb-api || { [ "$TOPOLOGY_DECLARED" = "yes" ] && systemctl is-enabled --quiet bunkerweb-api 2>/dev/null; }; then
    echo "🛑 Disabling and stopping the BunkerWeb API service..."
    do_and_check_cmd systemctl disable --now bunkerweb-api
else
    echo "ℹ️ BunkerWeb API service is not enabled in the current configuration."
fi

# Record the resolved install type so future upgrades detect it deterministically
# instead of inferring from systemd unit state. Only written when the topology was
# declared this run (fresh install, or explicit mode/service signal) — a bare
# `apt upgrade` carries no intent, so we must NOT stamp the standalone "full" default
# onto a legacy worker/scheduler/ui/api host and have it override inference forever.
INSTALL_TYPE_MARKER="/usr/share/bunkerweb/INSTALL_TYPE"
if [ "$TOPOLOGY_DECLARED" = "yes" ] && [ -n "$RESOLVED_INSTALL_TYPE" ]; then
    echo "$RESOLVED_INSTALL_TYPE" > "$INSTALL_TYPE_MARKER" 2>/dev/null \
        && chmod 0644 "$INSTALL_TYPE_MARKER" 2>/dev/null \
        || echo "ℹ️ Note: could not persist install-type marker at $INSTALL_TYPE_MARKER"
fi

# Old postrm/%postun may have written flat snapshots after pre-install. Keep them for
# recovery, but never let them become the next transaction's restore source.
backup_dir=/var/backups/bunkerweb
do_and_check_cmd mkdir -p "$backup_dir"
do_and_check_cmd chmod 0700 "$backup_dir"
completed=$(mktemp -d "$backup_dir/completed.XXXXXX") || exit 1
for name in variables.env scheduler.env ui.env api.env api.yml db.sqlite3; do
    for legacy in "$backup_dir/$name" "/var/tmp/$name"; do
        if [ -f "$legacy" ]; then
            do_and_check_cmd chmod 0600 "$legacy"
            # Keep current and /var/tmp snapshots distinct when both exist.
            if [ "$legacy" = "$backup_dir/$name" ]; then
                do_and_check_cmd mv "$legacy" "$completed/$name"
            else
                do_and_check_cmd mv "$legacy" "$completed/legacy-$name"
            fi
        fi
    done
done
if [ -d "$transaction" ]; then
    do_and_check_cmd mv "$transaction" "$completed/transaction"
fi

if [ "$UPGRADE" = yes ]; then
    do_and_check_cmd rm -f /var/tmp/bunkerweb_upgrade
    echo "BunkerWeb has been successfully upgraded! 🎉"
else
    echo "BunkerWeb has been successfully installed! 🎉"
fi

echo ""
echo "For more information on BunkerWeb, visit:"
echo "  * Official website: https://www.bunkerweb.io"
echo "  * Documentation: https://docs.bunkerweb.io/1.6/"
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
