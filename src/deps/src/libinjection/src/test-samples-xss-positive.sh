#!/bin/sh
#
# XSS Sample Tests
#
set -e
${VALGRIND} ./reader -t -i -x -m 20 ../data/xss*
