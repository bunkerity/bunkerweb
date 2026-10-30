#!/bin/bash

# Check CrowdSec connectivity
output=$(cscli metrics 2>&1)
if echo "$output" | grep -q "connection refused"; then
	exit 1
fi

exit 0
