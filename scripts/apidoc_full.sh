#!/bin/sh

# Generate doxygen documentation with a full mbedtls_config.h (this ensures that every
# available flag is documented, and avoids warnings about documentation
# without a corresponding #define).
#
# /!\ This must not be a Makefile target, as it would create a race condition
# when multiple targets are invoked in the same parallel build.
#
# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

set -eu

CONFIG_H='include/mbedtls/mbedtls_config.h'

if [ -r $CONFIG_H ]; then :; else
    echo "$CONFIG_H not found" >&2
    exit 1
fi

CONFIG_BAK=${CONFIG_H}.bak
cp -p $CONFIG_H $CONFIG_BAK

scripts/config.py realfull
make apidoc

mv $CONFIG_BAK $CONFIG_H
