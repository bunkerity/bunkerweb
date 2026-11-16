#!/bin/sh
# SQLi false-positive samples: at most 21 may be flagged
# srcdir is set by the automake test harness; default for manual runs.
exec ${VALGRIND} ./reader -m 21 "${srcdir:-.}"/../data/false_*.txt
