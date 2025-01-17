#!/bin/sh
#
# Run fuzzer(s)
#
./autogen.sh
CC=clang CXX=clang++ ./configure --enable-sanitizers --enable-fuzzers
make
./src/fuzz/fuzzer -max_total_time="${MAX_TOTAL_TIME:-300}" -print_pcs=1 -workers="${FUZZY_WORKERS:-0}" -jobs="${FUZZY_JOBS:-0}" ./src/fuzz/corpus
