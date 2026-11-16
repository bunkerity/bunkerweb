#!/bin/bash
# Copies every fixture of tests/core/cors/www/<host>/ into /var/www/html/<host>/ and into /var/www/html/ itself, the
# web root the PHP-backed actions of cors.yml read. The harness's own provisioning (`provision_www_root` in
# tests/scripts/utils.sh) copies only index.php and logo.png into each host directory, so
# `credentials.php` is not there and the `upstream_fixture` actions would answer 404.
#
# Additive and idempotent, and done the way `provision_www_root` does it on a host without
# passwordless sudo: as root in a throwaway container, with the repository fixture and the web root
# mounted. The web root belongs to www-data:nginx (33:101), mode 644 for files.
set -Eeuo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
www="/var/www/html"

if [ "$(id -u)" -eq 0 ]; then
	runner=(bash -c)
elif sudo -n true 2>/dev/null; then
	# sudo-rs ignores -E and drops the environment, so SRC and WWW travel as arguments of env
	runner=(sudo env "SRC=$here/www" "WWW=$www" bash -c)
else
	runner=()
fi

script='set -e
: "${SRC:?}" "${WWW:?}"
for dir in "$SRC"/*/ ; do
    host="$(basename "$dir")"
    mkdir -p "$WWW/$host"
    cp "$dir"* "$WWW/$host/"
    # fastcgi_params sets SCRIPT_FILENAME to REMOTE_PHP_PATH/$fastcgi_script_name and the spec sets REMOTE_PHP_PATH
    # to the web root itself, so php-fpm resolves app1.example.com/credentials.php to $WWW/credentials.php.
    cp "$dir"* "$WWW/"
    chown -R 33:101 "$WWW/$host"
    find "$WWW/$host" -type f -exec chmod 644 {} +
done
chown 33:101 "$WWW"/*.php
chmod 644 "$WWW"/*.php'

if [ "${#runner[@]}" -gt 0 ]; then
	SRC="$here/www" WWW="$www" "${runner[@]}" "$script"
else
	docker run --rm -e SRC=/src -e WWW="$www" -v "$here/www":/src:ro -v "$www":"$www" bash:5 bash -c "$script"
fi

[ -f "$www/app1.example.com/credentials.php" ] && [ -f "$www/credentials.php" ] || {
	echo "cors fixture: credentials.php was not provisioned" >&2
	exit 1
}
echo "cors fixture provisioned"
