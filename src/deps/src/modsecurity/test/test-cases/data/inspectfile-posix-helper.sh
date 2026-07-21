#!/bin/sh

if [ "$1" = "match" ]; then
    echo 0
    exit 0
fi

if [ "$1" = "nomatch" ]; then
    echo 1
    exit 0
fi

if [ "$1" = "stderr-only" ]; then
    echo 0 1>&2
    exit 0
fi

exit 7
