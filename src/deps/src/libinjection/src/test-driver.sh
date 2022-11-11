#!/bin/sh
set -u

TEST=$1
LOG="${TEST}.log"
rm -f $LOG
"./$TEST" >$LOG 2>&1
aexit=$?
if [ "$aexit" -eq "0" ]; then
   echo "PASS: $TEST"
else
   echo "FAIL: $TEST"
   cat $LOG
   exit 1
fi
