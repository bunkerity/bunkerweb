#!/bin/sh
# Golden-file tests (tokenizer, folding, SQLi, HTML5), TAP output
# srcdir is set by the automake test harness; default for manual runs.
exec ${VALGRIND} ./testdriver "${srcdir:-.}"/../tests/test-*.txt
