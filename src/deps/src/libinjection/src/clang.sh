#!/bin/sh

#
# adjust as needed for your clang setup
#
# -Wno-padded padding can change by OS/version this check is really
#   for embedded systems so it's ok to skip
#
# -Wno-covered-switch-default Don't warn if we have a switch that
#  covers all of an enum AND we have a default.  enums are only loosely
#  typed, it's good to have a default: assert(0) in case someone does
#  a bad cast, etc also this conflicts with GCC checks.
#
make clean
export CC=clang
export CFLAGS="-g -O3 -Werror -Weverything -Wno-padded -Wno-covered-switch-default"
make -e test
