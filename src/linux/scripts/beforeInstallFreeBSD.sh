#!/bin/sh

# FreeBSD beforeInstall script for BunkerWeb

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

if [ -d /etc/nginx ]; then
    output_path="/etc/nginx_backup"
    if [ ! -d "$output_path" ]; then
        echo "[INFO] Copy /etc/nginx to $output_path"
        do_and_check_cmd cp -R /etc/nginx "$output_path"
    else
        echo "[INFO] Backup directory $output_path already exists, skipping backup"
    fi
fi

# If version is older than or equal to 1.5.12 then create another file
if [ -f /usr/share/bunkerweb/VERSION ] && grep -Eq "^(0|1\\.[0-4])(\\..*)?$|^1\\.5\\.([0-9]|1[0-2])$" /usr/share/bunkerweb/VERSION; then
    do_and_check_cmd touch /var/tmp/bunkerweb_enable_scheduler
fi

# Create nginx user and group if they do not exist (FreeBSD specific)
if ! pw groupshow nginx >/dev/null 2>&1; then
    echo "[INFO] Creating nginx group..."
    pw groupadd nginx
fi

if ! pw usershow nginx >/dev/null 2>&1; then
    echo "[INFO] Creating nginx user..."
    pw useradd nginx -g nginx -d /nonexistent -s /usr/sbin/nologin -c "nginx user"
fi
