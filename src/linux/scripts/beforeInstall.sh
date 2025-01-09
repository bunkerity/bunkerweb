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
    if dpkg --compare-versions "$version" le "1.5.12"; then
        do_and_check_cmd touch /var/tmp/bunkerweb_enable_scheduler
    fi
fi
