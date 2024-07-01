#!/usr/bin/env python
#
# This script reads all the rule files passed on the command line,
# and outputs them, with each (multi-line) directive joined as a
# single line.
#
# This can be used to work around a bug in Apache < 2.4.11 in
# parsing long configuration directives.
#
# Usage:
#
#   util/join-multiline-rules/join.py rules/*.conf > rules/rules.conf.joined
#
# This produces a single 'rules.conf.joined' file that can be included
# in buggy Apache versions. It is recommended to keep this file in the
# rules/ directory (because it refers to .data files in that directory)
# but give it a name not ending in .conf (so the file will not be
# included in *.conf and you can re-run the command multiple times
# without including its own output).
#
# Example:
#
#   SecRule &TX:BLOCKING_PARANOIA_LEVEL "@eq 0" \
#      "id:901120,\
#      phase:1,\
#      pass,\
#      nolog,\
#      setvar:tx.blocking_paranoia_level=1"
#
# will be outputted as:
#
#   SecRule &TX:BLOCKING_PARANOIA_LEVEL "@eq 0" "id:901120,phase:1,pass,nolog,setvar:tx.blocking_paranoia_level=1"
#

import fileinput, sys

for line in fileinput.input():
    line = line.strip()
    if line == '':
        sys.stdout.write("\n")
        continue

    if line[-1] == '\\':
        sys.stdout.write(line[0:-1])
    else:
        sys.stdout.write(line)
        sys.stdout.write("\n")
