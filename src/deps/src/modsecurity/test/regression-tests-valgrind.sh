#!/usr/bin/env bash

valgrind --tool=massif ./regression_tests $*
valgrind --leak-check=full --suppressions=./valgrind_suppressions.txt ./regression_tests $*
