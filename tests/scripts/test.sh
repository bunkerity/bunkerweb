#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration="${1^}"
type="${2:-}"
release="${3:-}"
category="${4:-}"

if [ -z "$release" ] ; then
    log "TEST" "❌" "Please provide a release as 3rd argument"
    exit 1
elif [ -z "$category" ] ; then
    log "TEST" "❌" "Please provide a category as 4th argument"
    exit 1
fi

./tests/scripts/build.sh "$integration" "$type" "$release" "$category"
ret=$?
# shellcheck disable=SC2181
if [ $ret -ne 0 ] ; then
  exit $ret
fi

./tests/scripts/run.sh "$integration" "$type" "$release" "$category"
ret=$?
# shellcheck disable=SC2181
if [ $ret -ne 0 ] ; then
  exit $ret
fi

log "TEST" "✅" "All tests passed"
exit 0
