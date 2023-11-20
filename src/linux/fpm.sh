#!/bin/bash

VERSION="$(tr -d '\n' < /usr/share/bunkerweb/VERSION)"
ARCH="$(uname -m)"
sed -i "s/%VERSION%/${VERSION}/g" .fpm
sed -i "s/%ARCH%/${ARCH}/g" .fpm

fpm -t "$1" -p "/data/bunkerweb.$1"
