#!/bin/sh
#
# Code coverage for data only (not unit tests)
#
./autogen.sh
./configure --enable-gcov
make
cd src
make testdriver
rm -f libinjection.info
rm -rf lcov-html
mkdir lcov-html
lcov -b . --directory . --zerocounters
../libtool --mode=execute ./testdriver ../tests/test-*.txt
lcov -b . --directory . --capture --output-file libinjection.info
lcov -b . --directory . --remove libinjection.info '/usr/include*' -o libinjection.info
lcov -b . --directory . --remove libinjection.info 'testdriver' -o libinjection.info
genhtml --branch-coverage -o lcov-html libinjection.info
