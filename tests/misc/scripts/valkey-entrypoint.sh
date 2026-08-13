#!/bin/sh
set -e

PORT="${VALKEY_PORT_NUMBER:-6379}"
TLS_ENABLED="${VALKEY_TLS_ENABLED:-yes}"
TLS_PORT="${VALKEY_TLS_PORT_NUMBER:-6380}"
DATA_DIR="${VALKEY_DATA_DIR:-/data}"
ACL_FILE="${VALKEY_ACL_FILE:-/acl/valkey.acl}"
TLS_CERT_FILE="${VALKEY_TLS_CERT_FILE:-/tls/valkey.crt}"
TLS_KEY_FILE="${VALKEY_TLS_KEY_FILE:-/tls/valkey.key}"
TLS_CA_FILE="${VALKEY_TLS_CA_FILE:-/tls/ca.crt}"
TLS_AUTH_CLIENTS="${VALKEY_TLS_AUTH_CLIENTS:-optional}"
EXTRA_FLAGS="${VALKEY_EXTRA_FLAGS:-}"
REPLICA_HOST="${VALKEY_REPLICAOF_HOST:-}"
REPLICA_PORT="${VALKEY_REPLICAOF_PORT:-6379}"
MASTER_PASSWORD="${VALKEY_MASTER_PASSWORD:-}"
MASTER_USERNAME="${VALKEY_MASTER_USERNAME:-}"

# Preserve original user-supplied arguments before we rebuild $@
USER_ARGS="$*"

set -- valkey-server \
  --port "${PORT}" \
  --aclfile "${ACL_FILE}" \
  --dir "${DATA_DIR}"

if [ "${TLS_ENABLED}" = "yes" ]; then
  set -- "$@" \
    --tls-port "${TLS_PORT}" \
    --tls-cert-file "${TLS_CERT_FILE}" \
    --tls-key-file "${TLS_KEY_FILE}" \
    --tls-ca-cert-file "${TLS_CA_FILE}" \
    --tls-auth-clients "${TLS_AUTH_CLIENTS}"
fi

if [ -n "${VALKEY_TLS_CIPHERS:-}" ]; then
  set -- "$@" --tls-ciphers "${VALKEY_TLS_CIPHERS}"
fi

if [ -n "${VALKEY_TLS_PROTOCOLS:-}" ]; then
  set -- "$@" --tls-protocols "${VALKEY_TLS_PROTOCOLS}"
fi

if [ -n "${VALKEY_PASSWORD:-}" ]; then
  set -- "$@" --requirepass "${VALKEY_PASSWORD}"
fi

if [ -n "${REPLICA_HOST}" ]; then
  set -- "$@" --replicaof "${REPLICA_HOST}" "${REPLICA_PORT}"
fi

if [ -n "${MASTER_PASSWORD}" ]; then
  set -- "$@" --masterauth "${MASTER_PASSWORD}"
fi

if [ -n "${MASTER_USERNAME}" ]; then
  set -- "$@" --masteruser "${MASTER_USERNAME}"
fi

if [ -n "${EXTRA_FLAGS}" ]; then
# shellcheck disable=SC2086
  set -- "$@" ${EXTRA_FLAGS}
fi

if [ -n "${USER_ARGS}" ]; then
# shellcheck disable=SC2086
  set -- "$@" ${USER_ARGS}
fi

exec "$@"
