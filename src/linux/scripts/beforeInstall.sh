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
    . /etc/os-release
    OS=$NAME
    if [[ "$OS" == "Ubuntu" || "$OS" == "Debian" ]]; then
        # Get the version of the package
        VERSION=$(dpkg-query -W -f='${Version}' bunkerweb)
        if dpkg --compare-versions "$VERSION" lt "1.5.0"; then
            echo "ℹ️ Copy /var/tmp/bunkerweb/variables.env to /etc/bunkerweb/variables.env"
            do_and_check_cmd cp -f /opt/bunkerweb/variables.env /var/tmp/variables.env
            echo "ℹ️ Copy /var/tmp/bunkerweb/variables.env to /etc/bunkerweb/variables.env"
            do_and_check_cmd cp -f /opt/bunkerweb/ui.env /var/tmp/ui.env
        fi
    elif [[ "$OS" == "CentOS Linux" || "$OS" == "Fedora" ]]; then
        # Get the version of the package
        VERSION=$(rpm -q --queryformat '%{VERSION}' bunkerweb)
        if [ "$(printf '%s\n' "$VERSION" "$(echo '1.5.0' | tr -d ' ')" | sort -V | head -n 1)" = "$VERSION" ]; then
            echo "ℹ️ Copy /var/tmp/bunkerweb/variables.env to /etc/bunkerweb/variables.env"
            do_and_check_cmd cp -f /opt/bunkerweb/variables.env /var/tmp/variables.env
            echo "ℹ️ Copy /var/tmp/bunkerweb/variables.env to /etc/bunkerweb/variables.env"
            do_and_check_cmd cp -f /opt/bunkerweb/ui.env /var/tmp/ui.env
        fi
    fi
else
    echo "❌ Error: /etc/os-release not found"
    exit 1
fi