#!/bin/sh
./autogen.sh
export CFLAGS="-O2 -pg -ansi"
./configure --enable-static --disable-shared
make clean
make
cd src
make reader
libtool --mode=execute ./reader -s -q ../data/sqli-*.txt ../data/false-*.txt
libtool --mode=execute gprof ./reader gmon.out
