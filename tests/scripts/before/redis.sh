#!/bin/bash

PREFIX=""
if [[ -n "$IN_CICD" ]]; then
    PREFIX="sudo "
fi

echo "🧰 Generating redis certs ..."

bash -c "${PREFIX}rm -rf /tmp/redis-tls"

mkdir /tmp/redis-tls

openssl genrsa -out /tmp/redis-tls/ca.key 2048
openssl req \
    -x509 -new -nodes -sha256 \
    -key /tmp/redis-tls/ca.key \
    -days 365 \
    -subj /CN=redis/ \
    -out /tmp/redis-tls/ca.crt

openssl req \
    -x509 -nodes -newkey rsa:2048 \
    -keyout /tmp/redis-tls/redis.key \
    -out /tmp/redis-tls/redis.pem \
    -days 365 \
    -subj /CN=redis/

bash -c "${PREFIX}chmod -R 777 /tmp/redis-tls"

echo "🧰 Certs generated ✅"
