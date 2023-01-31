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

# Get the version of the package
VERSION=$(dpkg-query -W -f='${Version}' bunkerweb)

if dpkg --compare-versions "$VERSION" lt "1.5.0"; then
    echo "ℹ️ Copy /var/tmp/bunkerweb/variables.env to /etc/bunkerweb/variables.env"
    do_and_check_cmd cp -f /opt/bunkerweb/variables.env /var/tmp/variables.env
    echo "ℹ️ Copy /var/tmp/bunkerweb/variables.env to /etc/bunkerweb/variables.env"
    do_and_check_cmd cp -f /opt/bunkerweb/ui.env /var/tmp/ui.env
fi