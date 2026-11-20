#!/bin/sh
set -eu

PORT="${REDIS_SENTINEL_PORT_NUMBER:-26379}"
MASTER_SET="${REDIS_MASTER_SET:-}"
MASTER_HOST="${REDIS_MASTER_HOST:-}"
MASTER_PORT="${REDIS_MASTER_PORT_NUMBER:-6379}"
QUORUM="${REDIS_SENTINEL_QUORUM:-2}"
DOWN_AFTER="${REDIS_SENTINEL_DOWN_AFTER:-10000}"
FAILOVER_TIMEOUT="${REDIS_SENTINEL_FAILOVER_TIMEOUT:-180000}"
PARALLEL_SYNCS="${REDIS_SENTINEL_PARALLEL_SYNCS:-1}"
ACLFILE="${REDIS_SENTINEL_ACLFILE:-/acl/sentinel.acl}"
TLS_AUTH_CLIENTS="${REDIS_SENTINEL_TLS_AUTH_CLIENTS:-no}"
RESOLVE_HOSTNAMES="${REDIS_SENTINEL_RESOLVE_HOSTNAMES:-yes}"
ANNOUNCE_HOSTNAMES="${REDIS_SENTINEL_ANNOUNCE_HOSTNAMES:-no}"

if [ -z "$MASTER_SET" ] || [ -z "$MASTER_HOST" ]; then
  echo "Missing REDIS_MASTER_SET or REDIS_MASTER_HOST" >&2
  exit 1
fi

CONFIG="/tmp/redis-sentinel.conf"
cat > "$CONFIG" <<CONF
port $PORT
dir /tmp
protected-mode no
sentinel monitor $MASTER_SET $MASTER_HOST $MASTER_PORT $QUORUM
sentinel down-after-milliseconds $MASTER_SET $DOWN_AFTER
sentinel failover-timeout $MASTER_SET $FAILOVER_TIMEOUT
sentinel parallel-syncs $MASTER_SET $PARALLEL_SYNCS
sentinel resolve-hostnames $RESOLVE_HOSTNAMES
sentinel announce-hostnames $ANNOUNCE_HOSTNAMES
CONF

if [ -n "${REDIS_MASTER_PASSWORD:-}" ]; then
  printf 'sentinel auth-pass %s %s\n' "$MASTER_SET" "$REDIS_MASTER_PASSWORD" >> "$CONFIG"
fi

printf 'Starting Redis Sentinel monitoring %s on %s:%s\n' "$MASTER_SET" "$MASTER_HOST" "$MASTER_PORT"
exec redis-sentinel "$CONFIG" --aclfile "$ACLFILE" --tls-auth-clients "$TLS_AUTH_CLIENTS"
