#!/bin/sh
set -e

PORT="${VALKEY_PORT_NUMBER:-6379}"
TLS_ENABLED="${VALKEY_TLS_ENABLED:-yes}"
TLS_PORT="${VALKEY_TLS_PORT_NUMBER:-6380}"

valkey-cli -p "${PORT}" ping >/dev/null

if [ "${TLS_ENABLED}" != "no" ]; then
  valkey-cli --tls --insecure -p "${TLS_PORT}" ping >/dev/null
fi
