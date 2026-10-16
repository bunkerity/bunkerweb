#!/bin/sh
set -eu

PORT="${REDIS_PORT_NUMBER:-6379}"
TLS_ENABLED="${REDIS_TLS_ENABLED:-no}"
TLS_PORT="${REDIS_TLS_PORT_NUMBER:-$PORT}"
TLS_AUTH_CLIENTS="${REDIS_TLS_AUTH_CLIENTS:-yes}"
DATA_DIR="${REDIS_DATA_DIR:-/data}"
REPLICATION_MODE="${REDIS_REPLICATION_MODE:-}"

mkdir -p "$DATA_DIR"

set -- "--port" "$PORT" "--dir" "$DATA_DIR" "--protected-mode" "no"

if [ -n "${REDIS_PASSWORD:-}" ]; then
  set -- "$@" "--requirepass" "$REDIS_PASSWORD"
fi

if [ -n "${REDIS_ACLFILE:-}" ]; then
  set -- "$@" "--aclfile" "$REDIS_ACLFILE"
fi

if [ "$REPLICATION_MODE" = "slave" ]; then
  : "${REDIS_MASTER_HOST:?Missing REDIS_MASTER_HOST for replica mode}"
  : "${REDIS_MASTER_PORT_NUMBER:?Missing REDIS_MASTER_PORT_NUMBER for replica mode}"
  set -- "$@" "--replicaof" "$REDIS_MASTER_HOST" "$REDIS_MASTER_PORT_NUMBER"
  if [ -n "${REDIS_MASTER_PASSWORD:-}" ]; then
    set -- "$@" "--masterauth" "$REDIS_MASTER_PASSWORD"
  fi
  if [ -n "${REDIS_REPLICA_ANNOUNCE_IP:-}" ]; then
    : "${REDIS_REPLICA_ANNOUNCE_PORT_BASE:?Missing REDIS_REPLICA_ANNOUNCE_PORT_BASE}"
    replica_name="$(hostname)"
    replica_index="${replica_name##*-}"
    set -- "$@" \
      "--replica-announce-ip" "$REDIS_REPLICA_ANNOUNCE_IP" \
      "--replica-announce-port" "$((REDIS_REPLICA_ANNOUNCE_PORT_BASE + replica_index))"
  fi
fi

# Redis Cluster node: the announce IP is the node's fixed address on bw-universe, which is what
# CLUSTER SLOTS hands back to every client. The cluster itself is formed by redis-cluster-init.sh.
cluster_flag=$(printf '%s' "${REDIS_CLUSTER_ENABLED:-no}" | tr '[:upper:]' '[:lower:]')
if [ "$cluster_flag" = "yes" ]; then
  : "${REDIS_CLUSTER_ANNOUNCE_IP:?Missing REDIS_CLUSTER_ANNOUNCE_IP for cluster mode}"
  set -- "$@" \
    "--cluster-enabled" "yes" \
    "--cluster-config-file" "$DATA_DIR/nodes.conf" \
    "--cluster-node-timeout" "5000" \
    "--cluster-announce-ip" "$REDIS_CLUSTER_ANNOUNCE_IP" \
    "--save" ""
  if [ -n "${REDIS_PASSWORD:-}" ]; then
    set -- "$@" "--masterauth" "$REDIS_PASSWORD"
  fi
fi

tls_flag=$(printf '%s' "$TLS_ENABLED" | tr '[:upper:]' '[:lower:]')
if [ "$tls_flag" = "yes" ]; then
  : "${REDIS_TLS_CERT_FILE:?Missing REDIS_TLS_CERT_FILE}"
  : "${REDIS_TLS_KEY_FILE:?Missing REDIS_TLS_KEY_FILE}"
  : "${REDIS_TLS_CA_FILE:?Missing REDIS_TLS_CA_FILE}"

  set -- "$@" \
    "--tls-port" "$TLS_PORT" \
    "--tls-cert-file" "$REDIS_TLS_CERT_FILE" \
    "--tls-key-file" "$REDIS_TLS_KEY_FILE" \
    "--tls-ca-cert-file" "$REDIS_TLS_CA_FILE" \
    "--tls-auth-clients" "$TLS_AUTH_CLIENTS"
fi

printf 'Starting Redis with args:'
for arg in "$@"; do
  printf ' %s' "$arg"
done
printf '\n'

exec redis-server "$@"
