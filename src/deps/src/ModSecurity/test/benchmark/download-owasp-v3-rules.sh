#!/bin/bash


git clone https://github.com/SpiderLabs/owasp-modsecurity-crs.git owasp-v3
cd owasp-v3
git checkout v3.0.2 -b tag3.0.2
cd -

echo 'Include "owasp-v3/crs-setup.conf.example"' >> basic_rules.conf
echo 'Include "owasp-v3/rules/*.conf"' >> basic_rules.conf

echo "Done."

