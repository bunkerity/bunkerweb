#!/bin/sh

# deterministic helper for @inspectFile stress runs
if [ "$1" = "herewego" ]; then
    echo 0
    exit 0
fi

echo 1
exit 0
