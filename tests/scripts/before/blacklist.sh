#!/bin/bash

# Download the IP blocklist and get the first IP listed
URL="https://raw.githubusercontent.com/duggytuxy/Data-Shield_IPv4_Blocklist/refs/heads/main/prod_data-shield_ipv4_blocklist.txt"

echo "Downloading IP blocklist..."
FIRST_IP=$(curl -s "$URL" | head -n 1 | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -n 1)

if [ -n "$FIRST_IP" ]; then
    echo "First IP from blocklist: $FIRST_IP"
else
    echo "Error: Could not retrieve or parse the first IP from the blocklist"
    exit 1
fi

export COMMUNITY_DUGGYTUXY_IP="$FIRST_IP"
