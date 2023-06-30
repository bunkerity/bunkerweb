#!/bin/sh
#
# XSS Sample Tests
#
set -e
${VALGRIND} ./reader -m 21 ../data/false_*.txt
