#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration="${1^}"
type="${2:-}"
args="$*"

service=""

i=0
for arg in $args ; do
  if [ "$arg" == "$integration" ] || [ "$arg" == "$type" ] ; then
    continue
  fi

  if [ "$arg" == "--follow" ] ; then
    export FOLLOW="yes"
  else
    service="$arg"
  fi
  i=$((i+1))
  if [ $i -gt 1 ] ; then
    break
  fi
done

if [ -n "$service" ] ; then
  log "LOG" "ℹ️ " "Logging \"$service\" for integration \"$integration\" ..."
  log_stack "$service"
else
  log "LOG" "ℹ️ " "Logging BunkerWeb stack for integration \"$integration\" ..."
  log_stack
fi

unset FOLLOW
