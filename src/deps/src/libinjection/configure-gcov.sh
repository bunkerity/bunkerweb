#!/bin/sh
set -e
#
# gprof build
#
make clean
export CC=gcc
export CFLAGS="-ansi -g -O0 -fprofile-arcs -ftest-coverage -Wall -Wextra"
make -e


