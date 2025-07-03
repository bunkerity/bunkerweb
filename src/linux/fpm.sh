#!/bin/bash

VERSION="$(tr -d '\n' < /usr/share/bunkerweb/VERSION)"
ARCH="$(uname -m)"
sed -i "s/%VERSION%/${VERSION}/g" .fpm
sed -i "s/%ARCH%/${ARCH}/g" .fpm

FPM_OPTS=""
if [ -n "$FPM_DEBUG" ]; then
  echo "[DEBUG] Debug mode activated"
  FPM_OPTS="--verbose --log debug"
fi

if [ -z "$FPM_SKIP_COMPRESSION" ]; then
  if [ "$1" == "deb" ]; then
    echo "[DEBUG] Compression enabled: gzip"
    FPM_OPTS="$FPM_OPTS --deb-compression gz"
  elif [ "$1" == "rpm" ]; then
    echo "[DEBUG] Compression enabled: gzip"
    FPM_OPTS="$FPM_OPTS --rpm-compression gzip"
  fi
else
  echo "[DEBUG] Compression skipped"
fi

# shellcheck disable=SC2086
fpm -t "$1" -p "/data/bunkerweb.$1" $FPM_OPTS
