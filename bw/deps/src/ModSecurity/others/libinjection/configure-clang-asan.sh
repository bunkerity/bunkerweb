#!/bin/sh
set -e
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
# -Wdisabled-macro-expansion triggered on some linux libc headers involving
#  stdout and stdin definitions
#
make clean
export CC=clang
export CFLAGS="-g -ansi -fpic -O3 -Weverything -Wno-unused-macros -Wno-padded -Wno-covered-switch-default -Wno-disabled-macro-expansion -Werror -fsanitize=address"
make -e check
