#!/bin/sh
set -e
#
# See https://wiki.debian.org/Hardening for details
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
export CFLAGS="-g -O3 -pie -fPIE -fPIC -fstack-protector --param ssp-buffer-size=4 -Wall -Wextra -Wformat -Wformat-security -Werror -Wcast-align -Wshadow -Wpointer-arith -Wcast-qual -Wstack-protector -D_FORTIFY_SOURCE=2 -ansi -pedantic"
make -e
