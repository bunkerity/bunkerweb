#!/bin/bash

git clone -c advice.detachedHead=false --depth 1 --branch v4.3.0 https://github.com/coreruleset/coreruleset.git owasp-v4

echo 'Include "owasp-v4/crs-setup.conf.example"' >> basic_rules.conf
echo 'Include "owasp-v4/rules/*.conf"' >> basic_rules.conf

echo "Done."

