#!/bin/bash -eu

# basic-in-docker.sh
#
# Purpose
# -------
# This runs sanity checks and library tests in a Docker container. The tests
# are run for both clang and gcc. The testing includes a full test run
# in the default configuration, partial test runs in the reference
# configurations, and some dependency tests.
#
# WARNING: the Dockerfile used by this script is no longer maintained! See
# https://github.com/Mbed-TLS/mbedtls-test/blob/master/README.md#quick-start
# for the set of Docker images we use on the CI.
#
# Notes for users
# ---------------
# See docker_env.sh for prerequisites and other information.

# Copyright The Mbed TLS Contributors
# SPDX-License-Identifier: Apache-2.0 OR GPL-2.0-or-later

source tests/scripts/docker_env.sh

run_in_docker tests/scripts/all.sh 'check_*'

for compiler in clang gcc; do
    run_in_docker -e CC=${compiler} cmake -D CMAKE_BUILD_TYPE:String="Check" .
    run_in_docker -e CC=${compiler} make
    run_in_docker -e CC=${compiler} make test
    run_in_docker programs/test/selftest
    run_in_docker -e OSSL_NO_DTLS=1 tests/compat.sh
    run_in_docker tests/ssl-opt.sh -e '\(DTLS\|SCSV\).*openssl'
    run_in_docker tests/scripts/test-ref-configs.pl
    run_in_docker tests/scripts/depends.py curves
    run_in_docker tests/scripts/depends.py kex
done
