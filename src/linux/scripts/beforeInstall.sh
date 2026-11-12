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

if [ -d /etc/nginx ]; then
    output_path="/etc/nginx_backup_$(date +%s)"
    echo "ℹ️ Copy /etc/nginx to $output_path"
    do_and_check_cmd cp -R /etc/nginx "$output_path"
fi

# If version is older that 1.5.12 included then create another file
if [ -f /usr/share/bunkerweb/VERSION ]; then
    version=$(cat /usr/share/bunkerweb/VERSION)
    if command -v dpkg >/dev/null 2>&1 && dpkg --compare-versions "$version" le "1.5.12"; then
        do_and_check_cmd touch /var/tmp/bunkerweb_enable_scheduler
    fi
fi

# fpm embeds this script in preinst/%pre, before old postrm/%postun can run.
case "${1:-}" in
    upgrade) upgrade=yes ;;
    install) upgrade=no; [ -n "${2:-}" ] && upgrade=yes ;;
    [0-9]*) upgrade=no; [ "$1" -gt 1 ] && upgrade=yes ;;
    *) exit 0 ;;
esac

umask 077
backup_dir=/var/backups/bunkerweb
do_and_check_cmd mkdir -p "$backup_dir"
do_and_check_cmd chown root:root "$backup_dir"
do_and_check_cmd chmod 0700 "$backup_dir"
stage=$(mktemp -d "$backup_dir/.transaction.XXXXXX") || exit 1
echo "$upgrade" > "$stage/upgrade" || exit 1

if [ "$upgrade" = yes ]; then
    # Record all states before stopping any unit; stop wrappers may stop sibling units.
    if command -v systemctl >/dev/null 2>&1; then
        for service in bunkerweb bunkerweb-scheduler bunkerweb-ui bunkerweb-api; do
            if systemctl is-active --quiet "$service"; then
                echo "$service" >> "$stage/active" || exit 1
            fi
        done
        for service in bunkerweb bunkerweb-scheduler bunkerweb-ui bunkerweb-api; do
            do_and_check_cmd systemctl stop "$service"
        done
    fi
    for name in variables.env scheduler.env ui.env api.env api.yml; do
        if [ -f "/etc/bunkerweb/$name" ]; then
            do_and_check_cmd install -m 0600 -o root -g root "/etc/bunkerweb/$name" "$stage/$name"
        fi
    done
    if [ -f /var/lib/bunkerweb/db.sqlite3 ]; then
        # SQLite's online backup includes committed WAL pages; no application Python is needed.
        do_and_check_cmd sqlite3 -batch -bail -readonly /var/lib/bunkerweb/db.sqlite3 ".timeout 5000" ".backup '$stage/db.sqlite3'"
        check=$(sqlite3 -batch -bail -readonly "$stage/db.sqlite3" 'PRAGMA quick_check;') || exit 1
        if [ "$check" != ok ]; then
            echo "❌ Invalid SQLite upgrade snapshot: $check" >&2
            exit 1
        fi
        do_and_check_cmd chmod 0600 "$stage/db.sqlite3"
    fi
fi

# Publish only a complete, validated snapshot. Quarantine flat backups before the
# old package's immutable postrm/%postun can overwrite them on the first transition.
previous=$(mktemp -d "$backup_dir/previous.XXXXXX") || exit 1
if [ -d "$backup_dir/transaction" ]; then
    do_and_check_cmd mv "$backup_dir/transaction" "$previous/transaction"
fi
for name in variables.env scheduler.env ui.env api.env api.yml db.sqlite3; do
    if [ -f "$backup_dir/$name" ]; then
        do_and_check_cmd chmod 0600 "$backup_dir/$name"
        do_and_check_cmd mv "$backup_dir/$name" "$previous/$name"
    fi
    if [ -f "/var/tmp/$name" ]; then
        do_and_check_cmd chmod 0600 "/var/tmp/$name"
        do_and_check_cmd mv "/var/tmp/$name" "$previous/legacy-$name"
    fi
done
do_and_check_cmd mv "$stage" "$backup_dir/transaction"
