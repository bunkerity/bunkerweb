#!/usr/bin/env bash

valgrind --tool=massif ./unit-tests $*
valgrind --leak-check=full --suppressions=./valgrind_suppressions.txt ./unit-tests $*
