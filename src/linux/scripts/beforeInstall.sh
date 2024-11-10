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

# Check the os running
if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    OS=$NAME
    if [[ "$OS" == "Ubuntu" || "$OS" == "Debian" ]]; then
        # Get the version of the package
        VERSION=$(dpkg-query -W -f='${Version}' bunkerweb)
        if dpkg --compare-versions "$VERSION" lt "1.5.11" && [ -f /var/tmp/variables.env ] && [ -f /var/tmp/ui.env ]; then
            echo "ℹ️ Copy /var/tmp/variables.env to /etc/bunkerweb/variables.env"
            do_and_check_cmd cp -f /var/tmp/variables.env /etc/bunkerweb/variables.env
            echo "ℹ️ Copy /var/tmp/ui.env to /etc/bunkerweb/ui.env"
            do_and_check_cmd cp -f /var/tmp/ui.env /etc/bunkerweb/ui.env
        fi
    elif [[ "$OS" == "Red Hat Enterprise Linux" || "$OS" == "Fedora" ]]; then
        # Get the version of the package
        VERSION=$(rpm -q --queryformat '%{VERSION}' bunkerweb)
        if [ "$(printf '%s\n' "$VERSION" "$(echo '1.5.11' | tr -d ' ')" | sort -V | head -n 1)" = "$VERSION" ] && [ -f /var/tmp/variables.env ] && [ -f /var/tmp/ui.env ]; then
            echo "ℹ️ Copy /var/tmp/variables.env to /etc/bunkerweb/variables.env"
            do_and_check_cmd cp -f /var/tmp/variables.env /etc/bunkerweb/variables.env
            echo "ℹ️ Copy /var/tmp/ui.env to /etc/bunkerweb/ui.env"
            do_and_check_cmd cp -f /var/tmp/ui.env /etc/bunkerweb/ui.env
        fi
    fi
    if [ -f /var/tmp/db.sqlite3 ]; then
        echo "ℹ️ Copy /var/tmp/db.sqlite3 to /var/lib/bunkerweb/db.sqlite3"
        do_and_check_cmd cp -f /var/tmp/db.sqlite3 /var/lib/bunkerweb/db.sqlite3
    fi
    if [ -d /etc/nginx ]; then
        output_path="/etc/nginx_backup_$(date +%s)"
        echo "ℹ️ Copy /etc/nginx to $output_path"
        do_and_check_cmd cp -R /etc/nginx $output_path
    fi
else
    echo "❌ Error: /etc/os-release not found"
    exit 1
fi
