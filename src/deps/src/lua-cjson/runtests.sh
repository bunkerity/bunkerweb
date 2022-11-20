#!/bin/bash
set -eo pipefail

PLATFORM="`uname -s`"
[ "$1" ] && VERSION="$1" || VERSION="2.1devel"


# Portable "ggrep -A" replacement.
# Work around Solaris awk record limit of 2559 bytes.
# contextgrep PATTERN POST_MATCH_LINES
contextgrep() {
    cut -c -2500 | awk "/$1/ { count = ($2 + 1) } count > 0 { count--; print }"
}

do_tests() {
    echo
    cd tests
    lua -e 'print("Testing Lua CJSON version " .. require("cjson")._VERSION)'
    ./test.lua | contextgrep 'FAIL|Summary' 3 | grep -v PASS | cut -c -150
    cd ..
}

echo "===== Setting LuaRocks PATH ====="
eval "`luarocks path`"

echo "===== Building UTF-8 test data ====="
( cd tests && ./genutf8.pl; )

echo "===== Cleaning old build data ====="
make clean
rm -f tests/cjson.so

echo "===== Verifying cjson.so is not installed ====="

cd tests
if lua -e 'require "cjson"' 2>/dev/null
then
    cat <<EOT
Please ensure you do not have the Lua CJSON module installed before
running these tests.
EOT
    exit 1
fi
cd ..

echo "===== Testing LuaRocks build ====="
luarocks make --local
do_tests
luarocks remove --local lua-cjson
make clean

echo "===== Testing Makefile build ====="
make "$@"
cp -r lua/cjson cjson.so tests
do_tests
make clean
rm -rf tests/cjson{,.so}


if [ -z "$SKIP_CMAKE" ]; then
    echo "===== Testing Cmake build ====="
    mkdir build
    cd build
    cmake ..
    make
    cd ..
    cp -r lua/cjson build/cjson.so tests
    do_tests
    rm -rf build tests/cjson{,.so}
else
    echo "===== Skipping Cmake build ====="
fi


# vi:ai et sw=4 ts=4:
