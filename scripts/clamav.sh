#!/bin/sh

output=$(clamscan -i --no-summary "$1" 2> /dev/null)

if echo "$output" | grep -q ".* FOUND$" ; then
	echo "0 clamscan: $output"
else
	echo "1 clamscan: ok"
fi
