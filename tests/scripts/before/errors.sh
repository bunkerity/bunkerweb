#!/bin/bash

# `/var/www/html` is provisioned root-owned (`provision_www_root` chowns it to 33:101 so php-fpm
# and nginx can read it), so writing the custom error pages needs root. This script used to
# escalate only when `IN_CICD` was set, which meant every local run died on
# `tee: /var/www/html/errors/403.html: Permission denied` before a single request was sent -- and
# the run reported it as a failed spec, three lines under an unrelated image rebuild.
#
# Same three-way escalation `provision_www_root` uses, and for the same reason: a workstation
# usually has no passwordless sudo, and an unattended arm cannot answer a password prompt.
# Everything runs as ONE root script rather than one per host: the container fallback costs a
# process spawn each time, and there are a dozen hosts.

hosts="$(grep '127.0.0.1 .*\.example\.com' tests/misc/conf/dnsmasq.hosts | awk '{print $2}' | sort -u | tr '\n' ' ')"

error_page="$(mktemp)"
cat > "$error_page" <<'HTML'
<html>
  <body>
    <h1>It Works!</h1>
  </body>
</html>
HTML

script="set -e
mkdir -p /var/www/html/errors
cp '$error_page' /var/www/html/errors/403.html
chmod -R 777 /var/www/html/errors
for host in $hosts ; do
    mkdir -p \"/var/www/html/\$host/errors\"
    cp '$error_page' \"/var/www/html/\$host/errors/403.html\"
    chmod -R 777 \"/var/www/html/\$host/errors\"
done"

if [ "$(id -u)" -eq 0 ] ; then
    bash -c "$script"
elif sudo -n true 2>/dev/null ; then
    sudo -E bash -c "$script"
else
    docker run --rm -v /var/www/html:/var/www/html -v "$error_page":"$error_page":ro bash:5 bash -c "$script"
fi
ret=$?

rm -f "$error_page"

if [ $ret -ne 0 ] ; then
    echo "⭕ Failed to create custom error file ❌"
    return 1
    # shellcheck disable=SC2317
    exit 1
fi
