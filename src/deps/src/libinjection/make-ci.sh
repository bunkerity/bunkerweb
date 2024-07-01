#!/bin/sh
# this is the script that runs in CI
set -e

DASH=----------------------
echo $DASH
gcc --version
echo $DASH
make clean
make -e check
make clean

#
# Code coverage
#
export CC=gcc
export CFLAGS="-ansi -g -O0 -fprofile-arcs -ftest-coverage -Wall -Wextra"

echo $DASH
echo "Generating code coverage"
echo "CFLAGS=$CFLAGS"
echo
make -e check
if [ -n "$COVERALLS_REPO_TOKEN" ] ; then
    echo "uploading to coveralls"
    coveralls \
        --gcov-options '\-lp' \
        --exclude-pattern '.*h' \
        --exclude src/reader.c \
        --exclude src/example1.c \
        --exclude src/fptool.c \
        --exclude src/test_speed_sqli.c \
        --exclude src/test_speed_xss.c \
        --exclude src/testdriver.c \
        --exclude src/html5_cli.c \
        --exclude src/sqli_cli.c \
        --exclude python
fi
echo
unset CC
unset CFLAGS

echo
echo $DASH
clang --version
echo $DASH
./configure-clang.sh

echo
echo $DASH
echo "CLANG STATIC ANALYZER"
echo
cd src
make analyze

echo
echo $DASH
cppcheck --version
echo

cppcheck --std=c89 \
         --enable=all \
         --inconclusive \
         --suppress=variableScope \
         --suppress=missingIncludeSystem \
         --quiet \
         --error-exitcode=1 \
         --template='{file}:{line} {id} {severity} {message}' \
         .
echo "passed"

echo $DASH
export CFLAGS="-Wall -Wextra -Werror -pedantic -ansi -g -O1"
export VALGRIND="valgrind --gen-suppressions=no --leak-check=full --show-leak-kinds=all --read-var-info=yes --error-exitcode=1 --track-origins=yes --suppressions=/build/src/alpine.supp"
echo "GCC + VALGRIND"
echo $VALGRIND
echo
make clean
make -e check
unset VALGRIND
unset CFLAGS
echo

echo
echo "Done!"
