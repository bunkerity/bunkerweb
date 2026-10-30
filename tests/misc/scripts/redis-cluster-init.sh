#!/bin/sh
# One-shot: form a 3-master Redis Cluster out of the nodes started by redis-cluster.yml.
# Nodes are addressed by IP, the same address they announce, so CLUSTER SLOTS and the
# `redis-cli --cluster` bootstrap agree.
set -eu

NODES="${REDIS_CLUSTER_INIT_NODES:?Missing REDIS_CLUSTER_INIT_NODES}"
AUTH=""
if [ -n "${REDIS_PASSWORD:-}" ]; then
  AUTH="-a $REDIS_PASSWORD --no-auth-warning"
fi

for node in $NODES; do
  host="${node%:*}"
  port="${node#*:}"
  i=0
  # shellcheck disable=SC2086
  until redis-cli -h "$host" -p "$port" $AUTH ping 2>/dev/null | grep -q PONG; do
    i=$((i + 1))
    if [ "$i" -ge 60 ]; then
      echo "Redis node $node never answered PING" >&2
      exit 1
    fi
    sleep 1
  done
done

# shellcheck disable=SC2086
exec redis-cli $AUTH --cluster create $NODES --cluster-replicas 0 --cluster-yes
