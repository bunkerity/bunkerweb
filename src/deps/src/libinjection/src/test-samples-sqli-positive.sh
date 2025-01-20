#!/bin/sh
#
# XSS Sample Tests
#
set -e
${VALGRIND} ./reader -q -i -m 18 ../data/sqli-*.txt

