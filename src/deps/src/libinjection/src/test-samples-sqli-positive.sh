#!/bin/sh
# SQLi samples: at most 18 may be missed
# srcdir is set by the automake test harness; default for manual runs.
exec ${VALGRIND} ./reader -q -i -m 18 "${srcdir:-.}"/../data/sqli-*.txt
