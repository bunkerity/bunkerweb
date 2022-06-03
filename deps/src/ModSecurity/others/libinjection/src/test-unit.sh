#!/bin/sh
set -e
cd ../tests
pwd

find . -name 'test*.txt' | xargs ${VALGRIND} ../src/testdriver
