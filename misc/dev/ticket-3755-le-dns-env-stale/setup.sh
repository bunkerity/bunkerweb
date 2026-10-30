#!/usr/bin/env bash
# Generate the local ACME CA + Pebble server certificate, and the two patched job files
# that point issuance at Pebble instead of Let's Encrypt.
#
# BunkerWeb hardcodes the Let's Encrypt directory URLs and exposes no setting to override
# them, so reaching a local ACME server means patching:
#   * letsencrypt_utils.py  -> the directory constant, used for account bookkeeping
#   * certbot-new.py        -> `certbot certonly` is invoked with no --server at all, so
#                              the constant alone never reaches certbot
# Both copies are regenerated from the repo on every run and each is checked to differ
# from its source by exactly the intended lines, so the rig always tests current code.
set -euo pipefail

cd "$(dirname "$0")"

UTILS_SRC="../../../src/common/core/letsencrypt/jobs/letsencrypt_utils.py"
NEW_SRC="../../../src/common/core/letsencrypt/jobs/certbot-new.py"
PEBBLE_URL="https://pebble:14000/dir"

mkdir -p certs generated

if [ ! -f certs/ca.crt ]; then
    echo "==> Generating local ACME CA and Pebble server certificate"
    # keyUsage/basicConstraints are not optional: OpenSSL refuses a CA without them
    # ("CA cert does not include key usage extension").
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout certs/ca.key -out certs/ca.crt \
        -subj "/CN=BunkerWeb 3755 test CA" \
        -addext "basicConstraints=critical,CA:TRUE" \
        -addext "keyUsage=critical,digitalSignature,keyCertSign,cRLSign" 2>/dev/null

    openssl req -newkey rsa:2048 -nodes \
        -keyout certs/pebble.key -out certs/pebble.csr \
        -subj "/CN=pebble" 2>/dev/null

    openssl x509 -req -in certs/pebble.csr -CA certs/ca.crt -CAkey certs/ca.key \
        -CAcreateserial -days 3650 -out certs/pebble.crt \
        -extfile <(printf "subjectAltName=DNS:pebble,DNS:localhost,IP:10.30.55.14,IP:127.0.0.1\nbasicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n") 2>/dev/null

    rm -f certs/pebble.csr
    chmod 644 certs/*.crt certs/*.key
else
    echo "==> Reusing existing certs/"
fi

echo "==> Patching the ACME directory constant -> ${PEBBLE_URL}"
sed "s#^LETSENCRYPT_PRODUCTION_DIRECTORY = .*#LETSENCRYPT_PRODUCTION_DIRECTORY = \"${PEBBLE_URL}\"#" \
    "${UTILS_SRC}" > generated/letsencrypt_utils.py

if ! grep -q "^LETSENCRYPT_PRODUCTION_DIRECTORY = \"${PEBBLE_URL}\"$" generated/letsencrypt_utils.py; then
    echo "FAILED: the ACME directory constant was not patched, check ${UTILS_SRC}" >&2
    exit 1
fi

echo "==> Patching certbot certonly to pass --server ${PEBBLE_URL}"
sed "s#^        \"--break-my-certs\",\$#        \"--server\",\n        \"${PEBBLE_URL}\",\n        \"--break-my-certs\",#" \
    "${NEW_SRC}" > generated/certbot-new.py

if ! grep -q "^        \"${PEBBLE_URL}\",\$" generated/certbot-new.py; then
    echo "FAILED: --server was not injected, the certonly command in ${NEW_SRC} changed shape" >&2
    exit 1
fi

# Each generated copy must differ from its source only by the intended lines.
check_drift() {
    local src="$1" gen="$2" filter="$3" name="$4"
    if ! diff -q <(grep -vE "${filter}" "${src}") <(grep -vE "${filter}" "${gen}") > /dev/null; then
        echo "FAILED: generated/${name} differs from ${src} beyond the intended patch" >&2
        diff <(grep -vE "${filter}" "${src}") <(grep -vE "${filter}" "${gen}") >&2 || true
        exit 1
    fi
}

check_drift "${UTILS_SRC}" generated/letsencrypt_utils.py '^LETSENCRYPT_PRODUCTION_DIRECTORY = ' letsencrypt_utils.py
check_drift "${NEW_SRC}" generated/certbot-new.py "^        \"(--server|${PEBBLE_URL//\//\\/})\",\$" certbot-new.py

# Pre-fix JobScheduler for docker-compose.baseline.yml, so the bug can be reproduced.
echo "==> Extracting the pre-fix JobScheduler for the baseline overlay"
git -C ../../.. show HEAD:src/scheduler/JobScheduler.py > generated/JobScheduler.head.py
if ! grep -q "os.environ = self.__base_env.copy()" generated/JobScheduler.head.py; then
    echo "NOTE: HEAD no longer contains the os.environ rebind, so the baseline overlay is a no-op." >&2
    echo "      Point it at the commit before the fix to reproduce the bug." >&2
fi

echo "==> Ready. Next: docker compose build && docker compose up -d"
