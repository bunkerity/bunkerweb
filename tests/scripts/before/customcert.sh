#!/bin/bash

USER_ID="$(id -u)"
GROUP_ID="$(id -g)"

# /tmp/output may be root-owned (created by a prior sudo run or Docker bind-mount).
# Use a throwaway container to create it and own it as the current user, so the
# rest of this script runs sudo-free regardless of how it was created.
docker run --rm -v /tmp/output:/tmp/output alpine:latest \
    sh -c "mkdir -p /tmp/output && chown -R ${USER_ID}:${GROUP_ID} /tmp/output"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to create /tmp/output directory ❌"
    return 1
fi

echo "🔏 Generating certificate for www.example.com ..."
bash -c "openssl req -nodes -x509 -newkey ec -pkeyopt ec_paramgen_curve:secp384r1 -keyout /tmp/output/privatekey.key -out /tmp/output/certificate.pem -days 365 -subj /CN=www.example.com/"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to generate certificate for www.example.com ❌"
    return 1
fi

bash -c "chmod 777 /tmp/output/privatekey.key /tmp/output/certificate.pem"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to change permissions for certificate files ❌"
    return 1
fi

CUSTOM_SSL_CERT_DATA=$(base64 < /tmp/output/certificate.pem)
export CUSTOM_SSL_CERT_DATA

CUSTOM_SSL_KEY_DATA=$(base64 < /tmp/output/privatekey.key)
export CUSTOM_SSL_KEY_DATA
