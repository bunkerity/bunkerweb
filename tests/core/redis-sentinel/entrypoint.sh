#!/bin/bash
set -e

command="redis-server"

if [ "$REDIS_SSL" = "yes" ]; then
  mkdir /tls

  openssl genrsa -out /tls/ca.key 4096
  openssl req \
    -x509 -new -nodes -sha256 \
    -key /tls/ca.key \
    -days 365 \
    -subj /CN=bw-redis/ \
    -out /tls/ca.crt

  openssl req \
    -x509 -nodes -newkey rsa:4096 \
    -keyout /tls/redis.key \
    -out /tls/redis.pem \
    -days 365 \
    -subj /CN=bw-redis/

  chmod -R 640 /tls

  command+=" --tls-port ${REDIS_PORT:-6379} --port 0 --tls-cert-file /tls/redis.pem --tls-key-file /tls/redis.key --tls-ca-cert-file /tls/ca.crt --tls-auth-clients no"
else
  command+=" --port ${REDIS_PORT:-6379}"
fi

$command
