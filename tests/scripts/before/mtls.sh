#!/bin/bash

USER_ID="$(id -u)"
GROUP_ID="$(id -g)"

# /tmp/output may be root-owned (created by a prior sudo run or Docker bind-mount).
# Use a throwaway container to (re)create the mtls subdir and own it as the current
# user, so the rest of this script runs sudo-free regardless of how it was created.
docker run --rm -v /tmp/output:/tmp/output alpine:latest \
    sh -c "rm -rf /tmp/output/mtls && mkdir -p /tmp/output/mtls && chown -R ${USER_ID}:${GROUP_ID} /tmp/output/mtls"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to create /tmp/output/mtls directory ❌"
    return 1
fi

echo "🔏 Generating CA for mTLS tests ..."
bash -c "openssl ecparam -name secp384r1 -genkey -noout -out /tmp/output/mtls/ca.key"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to generate CA private key ❌"
    return 1
fi

bash -c "openssl req -x509 -new -nodes -days 730 -key /tmp/output/mtls/ca.key -out /tmp/output/mtls/ca.pem -subj \"/CN=BunkerWeb mTLS Test CA\""
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to generate CA certificate for mTLS tests ❌"
    return 1
fi

echo "🔏 Generating client key for mTLS tests ..."
bash -c "openssl genrsa -out /tmp/output/mtls/client.key 2048"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to generate client private key ❌"
    return 1
fi

echo "🔏 Generating client certificate signing request ..."
bash -c "openssl req -new -key /tmp/output/mtls/client.key -out /tmp/output/mtls/client.csr -subj \"/CN=mtls-client\""
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to generate client CSR ❌"
    return 1
fi

echo "🔏 Signing client certificate with the test CA ..."
bash -c "openssl x509 -req -in /tmp/output/mtls/client.csr -CA /tmp/output/mtls/ca.pem -CAkey /tmp/output/mtls/ca.key -CAcreateserial -out /tmp/output/mtls/client.crt -days 365 -sha256"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to sign client certificate ❌"
    return 1
fi

# Untrusted (self-signed, NOT signed by the test CA) client cert. Used to prove the
# difference between verify modes: rejected under 'on'/'optional', accepted under
# 'optional_no_ca' (which skips CA validation).
echo "🔏 Generating an untrusted (self-signed) client certificate for optional_no_ca tests ..."
bash -c "openssl req -x509 -nodes -newkey rsa:2048 -keyout /tmp/output/mtls/client-untrusted.key -out /tmp/output/mtls/client-untrusted.crt -days 365 -sha256 -subj \"/CN=mtls-untrusted\""
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to generate untrusted client certificate ❌"
    return 1
fi

bash -c "chmod 644 /tmp/output/mtls/ca.pem /tmp/output/mtls/client.crt /tmp/output/mtls/client.key /tmp/output/mtls/client-untrusted.crt /tmp/output/mtls/client-untrusted.key"
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "🔏 Failed to set permissions on generated certificates ❌"
    return 1
fi

echo "🔏 Generated mTLS materials ✅"
