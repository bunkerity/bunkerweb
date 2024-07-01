#!/bin/sh
set -e
#
# gprof build
#
make clean
export CFLAGS="-O2 -pg -ansi"
make -e

