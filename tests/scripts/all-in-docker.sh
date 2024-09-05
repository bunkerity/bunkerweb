#!/bin/bash -eu

# all-in-docker.sh
#
# Purpose
# -------
# This runs all.sh (except for armcc) in a Docker container.
#
# WARNING: the Dockerfile used by this script is no longer maintained! See
# https://github.com/Mbed-TLS/mbedtls-test/blob/master/README.md#quick-start
# for the set of Docker images we use on the CI.
#
# Notes for users
# ---------------
# See docker_env.sh for prerequisites and other information.
#
# See also all.sh for notes about invocation of that script.

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

source tests/scripts/docker_env.sh

# Run tests that are possible with openly available compilers
run_in_docker tests/scripts/all.sh \
    --no-armcc \
    $@
