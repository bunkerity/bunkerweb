#!/bin/bash

git clone -c advice.detachedHead=false --depth 1 --branch v3.0.2 https://github.com/coreruleset/coreruleset.git owasp-v3

echo 'Include "owasp-v3/crs-setup.conf.example"' >> basic_rules.conf
echo 'Include "owasp-v3/rules/*.conf"' >> basic_rules.conf

echo "Done."

