#!/bin/sh
# XSS samples: at most 20 may be missed
# srcdir is set by the automake test harness; default for manual runs.
exec ${VALGRIND} ./reader -t -i -x -m 20 "${srcdir:-.}"/../data/xss*
