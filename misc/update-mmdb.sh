#!/bin/bash

# This script downloads the latest GeoLite2 databases from dbip.com and updates the existing ones.

cd ../src/bw/misc || cd src/bw/misc || exit 1

# Download the latest GeoLite2 databases
asn_url="https://download.db-ip.com/free/dbip-asn-lite-$(date +%Y-%m).mmdb.gz"
country_url="https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz"

# ASN database: check availability and download
status="$(curl -sIL -o /dev/null -w "%{http_code}" "$asn_url")"
if [ "$status" = "200" ]; then
    curl -fsSL --retry 3 -o asn.mmdb.gz "$asn_url"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ]; then
        echo "❌ Failed to download the ASN database."
        exit 1
    fi
elif [ "$status" = "404" ]; then
    echo "❌ The ASN database is not available for the current month for the moment."
    exit 1
else
    echo "❌ Failed to fetch the ASN database (HTTP $status)."
    exit 1
fi

# Country database: check availability and download
status="$(curl -sIL -o /dev/null -w "%{http_code}" "$country_url")"
if [ "$status" = "200" ]; then
    curl -fsSL --retry 3 -o country.mmdb.gz "$country_url"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ]; then
        echo "❌ Failed to download the country database."
        exit 1
    fi
elif [ "$status" = "404" ]; then
    echo "❌ The country database is not available for the current month for the moment."
    exit 1
else
    echo "❌ Failed to fetch the country database (HTTP $status)."
    exit 1
fi

# Decompress the downloaded databases

gunzip -f asn.mmdb.gz
# shellcheck disable=SC2181
if [ $? -ne 0 ]; then
    echo "❌ Failed to decompress the ASN database."
    exit 1
fi

gunzip -f country.mmdb.gz
# shellcheck disable=SC2181
if [ $? -ne 0 ]; then
    echo "❌ Failed to decompress the country database."
    exit 1
fi

echo "✅ Updated the GeoLite2 databases."
