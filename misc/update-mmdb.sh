#!/bin/bash

# This script downloads the latest GeoLite2 databases from dbip.com and updates the existing ones.

cd ../src/bw/misc || cd src/bw/misc || exit 1

# Download the latest GeoLite2 databases

curl -o asn.mmdb.gz "https://download.db-ip.com/free/dbip-asn-lite-$(date +%Y-%m).mmdb.gz"
# shellcheck disable=SC2181
if [ $? -ne 0 ]; then
    echo "❌ Failed to download the ASN database."
    exit 1
fi

content_head="$(head -n 2 asn.mmdb.gz)"
if [[ "$content_head" =~ "404 Not Found" ]]; then
    echo "❌ The ASN database is not available for the current month for the moment."
    exit 1
fi

curl -o country.mmdb.gz "https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz"
# shellcheck disable=SC2181
if [ $? -ne 0 ]; then
    echo "❌ Failed to download the country database."
    exit 1
fi

content_head="$(head -n 2 country.mmdb.gz)"
if [[ "$content_head" =~ "404 Not Found" ]]; then
    echo "❌ The country database is not available for the current month for the moment."
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
