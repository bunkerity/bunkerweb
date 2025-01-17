#!/bin/sh

CPPCHECK=cppcheck
CPPCHECK_FLAGS=--quiet --enable=all --inconclusive --error-exitcode=2 \
        --std=c89 --std=posix --std=c++11 \
        --suppress=variableScope  \
        --template '{file}:{line} {severity} {id} {message}'

${CPPCHECK} ${CPPCHECK_FLAGS}
