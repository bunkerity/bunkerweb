#!/bin/sh
#
# Code coverage from data only (not unit tests)
#
./configure-gcov.sh
cd src
make reader
rm -f libinjection.info
rm -rf lcov-html
mkdir lcov-html
libtool --mode=execute ./reader -q ../data/sqli-*.txt
libtool --mode=execute ./reader -q -x ../data/xss-*.txt
lcov -b . --directory . --capture --output-file libinjection.info
lcov -b . --directory . --remove libinjection.info '/usr/include*' -o libinjection.info
lcov -b . --directory . --remove libinjection.info 'reader.c' -o libinjection.info
genhtml --branch-coverage -o lcov-html libinjection.info
