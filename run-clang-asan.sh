#!/bin/sh
#
# Code coverage for data only (not unit tests)
#
./autogen.sh
./configure-clang-asan.sh
make
cd src
make testdriver
rm -f libinjection.info
libtool --mode=execute ./testdriver ../tests/test-*.txt
